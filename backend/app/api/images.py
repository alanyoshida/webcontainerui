import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from app.deps import get_current_user, get_db, require_admin
from app.services.background import spawn
from app.services.errors import ConflictError, NotFoundError, ValidationFailedError
from app.services.image_pull import run_pull
from app.services.images import (
    create_image,
    disable_image,
    get_image,
    list_catalog_for_admin,
    list_catalog_for_user,
    retry_pull,
    set_image_icon,
)
from app.services.sessions import AuthenticatedUser

admin_router = APIRouter(dependencies=[Depends(require_admin)])
catalog_router = APIRouter()


class CreateImageRequest(BaseModel):
    display_name: str
    repository: str
    tag: str
    shm_size_mb: int | None = None
    mem_limit_mb: int | None = None
    cpu_limit: float | None = None
    harden_desktop: bool = False


class ImageResponse(BaseModel):
    id: int
    display_name: str
    repository: str
    tag: str
    shm_size_mb: int
    mem_limit_mb: int
    cpu_limit: float
    harden_desktop: bool
    enabled: bool
    pull_state: str
    pull_progress: str | None
    pull_error: str | None
    icon_url: str | None
    created_at: str


def _to_response(row: sqlite3.Row) -> ImageResponse:
    icon_path = row["icon_path"]
    return ImageResponse(
        id=row["id"],
        display_name=row["display_name"],
        repository=row["repository"],
        tag=row["tag"],
        shm_size_mb=row["shm_size_mb"],
        mem_limit_mb=row["mem_limit_mb"],
        cpu_limit=row["cpu_limit"],
        harden_desktop=bool(row["harden_desktop"]),
        enabled=bool(row["enabled"]),
        pull_state=row["pull_state"],
        pull_progress=row["pull_progress"],
        pull_error=row["pull_error"],
        icon_url=f"/uploads/{icon_path}" if icon_path else None,
        created_at=row["created_at"],
    )


@admin_router.post("/images", response_model=ImageResponse, status_code=status.HTTP_201_CREATED)
async def create_image_endpoint(
    body: CreateImageRequest, request: Request, db: sqlite3.Connection = Depends(get_db)
) -> ImageResponse:
    # async def (não def): precisa rodar na thread do event loop para que
    # `spawn` consiga agendar a tarefa de fundo com `asyncio.create_task`.
    # A inserção no SQLite é breve e síncrona mesmo assim (D5).
    settings = request.app.state.settings
    try:
        image_id = create_image(
            db,
            body.display_name,
            body.repository,
            body.tag,
            settings=settings,
            shm_size_mb=body.shm_size_mb,
            mem_limit_mb=body.mem_limit_mb,
            cpu_limit=body.cpu_limit,
            harden_desktop=body.harden_desktop,
        )
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    spawn(
        request.app,
        run_pull(settings.db_path, request.app.state.runtime, image_id, body.repository, body.tag),
    )

    return _to_response(get_image(db, image_id))


@admin_router.post("/images/{image_id}/retry-pull", response_model=ImageResponse)
async def retry_pull_endpoint(
    image_id: int, request: Request, db: sqlite3.Connection = Depends(get_db)
) -> ImageResponse:
    try:
        retry_pull(db, image_id)
        row = get_image(db, image_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    settings = request.app.state.settings
    spawn(
        request.app,
        run_pull(settings.db_path, request.app.state.runtime, image_id, row["repository"], row["tag"]),
    )

    return _to_response(row)


@admin_router.post("/images/{image_id}/icon", response_model=ImageResponse)
async def upload_image_icon_endpoint(
    image_id: int,
    request: Request,
    file: UploadFile,
    db: sqlite3.Connection = Depends(get_db),
) -> ImageResponse:
    settings = request.app.state.settings
    content = await file.read()
    try:
        set_image_icon(db, image_id, content, settings=settings)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationFailedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _to_response(get_image(db, image_id))


@admin_router.post("/images/{image_id}/disable", status_code=status.HTTP_204_NO_CONTENT)
def disable_image_endpoint(image_id: int, db: sqlite3.Connection = Depends(get_db)) -> None:
    disable_image(db, image_id)


@admin_router.get("/images", response_model=list[ImageResponse])
def list_images_admin_endpoint(db: sqlite3.Connection = Depends(get_db)) -> list[ImageResponse]:
    return [_to_response(row) for row in list_catalog_for_admin(db)]


@catalog_router.get("/catalog", response_model=list[ImageResponse])
def list_catalog_endpoint(
    user: AuthenticatedUser = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)
) -> list[ImageResponse]:
    return [_to_response(row) for row in list_catalog_for_user(db, user.id)]

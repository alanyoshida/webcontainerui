import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from app.deps import get_current_user, get_db, require_admin
from app.services.audit_log import audit
from app.services.agent_images import (
    build_hash_for,
    default_agent_images_dir,
    find_agent_image,
    run_build,
)
from app.services.background import spawn
from app.services.errors import ConflictError, NotFoundError, ValidationFailedError
from app.services.image_pull import run_pull
from app.services.images import (
    create_image,
    disable_image,
    get_image,
    list_catalog_for_admin,
    list_catalog_for_user,
    reopen_for_retry,
    reopen_for_update,
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
    image_version: str | None
    provision_kind: str
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
        image_version=row["image_version"],
        provision_kind=row["provision_kind"],
        created_at=row["created_at"],
    )


@admin_router.post("/images", response_model=ImageResponse, status_code=status.HTTP_201_CREATED)
async def create_image_endpoint(
    body: CreateImageRequest,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
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
    audit("admin.image.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None,
          target=f"{body.repository}:{body.tag}", outcome="success", detail="op=criar")

    return _to_response(get_image(db, image_id))


@admin_router.post("/images/{image_id}/retry-pull", response_model=ImageResponse)
async def retry_pull_endpoint(
    image_id: int,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> ImageResponse:
    try:
        row = get_image(db, image_id)
        # Valida o contexto antes de reabrir: uma entrada de build sem
        # definição conhecida não deve ficar presa em "pulling".
        spec = (
            find_agent_image(row["repository"], row["tag"])
            if row["provision_kind"] == "build"
            else None
        )
        if row["provision_kind"] == "build" and spec is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="contexto de build desconhecido para esta imagem",
            )
        reopen_for_retry(db, image_id)
        row = get_image(db, image_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    settings = request.app.state.settings
    runtime = request.app.state.runtime

    if spec is not None:
        base_dir = default_agent_images_dir()
        spawn(
            request.app,
            run_build(
                settings.db_path,
                runtime,
                image_id,
                row["repository"],
                row["tag"],
                context_dir=str(base_dir / spec.context_subdir),
                build_hash=build_hash_for(spec, base_dir),
            ),
        )
    else:
        spawn(
            request.app,
            run_pull(settings.db_path, runtime, image_id, row["repository"], row["tag"]),
        )

    audit("admin.image.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None,
          target=f"{row['repository']}:{row['tag']}", outcome="success", detail="op=retry")
    return _to_response(row)


@admin_router.post("/images/{image_id}/update-image", response_model=ImageResponse)
async def update_image_endpoint(
    image_id: int,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> ImageResponse:
    """Re-baixa a referência de uma entrada pronta do catálogo.

    Só entradas de pull participam: imagens de build têm ciclo próprio de
    rebuild (retry-pull). Pré-condição `ready` distinta da recuperação de
    falha — são semânticas diferentes, com respostas HTTP diferentes.
    """
    try:
        row = get_image(db, image_id)
        if row["provision_kind"] != "pull":
            raise ConflictError("atualização de imagem só vale para entradas de pull")
        reopen_for_update(db, image_id)
        row = get_image(db, image_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    settings = request.app.state.settings
    spawn(
        request.app,
        run_pull(settings.db_path, request.app.state.runtime, image_id, row["repository"], row["tag"]),
    )
    audit("admin.image.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None,
          target=f"{row['repository']}:{row['tag']}", outcome="success", detail="op=atualizar")

    return _to_response(row)


@admin_router.post("/images/{image_id}/icon", response_model=ImageResponse)
async def upload_image_icon_endpoint(
    image_id: int,
    request: Request,
    file: UploadFile,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> ImageResponse:
    settings = request.app.state.settings
    # Lê no máximo um byte além do limite configurado: o corpo da
    # requisição nunca é materializado inteiro na memória antes da
    # validação de tamanho em `set_image_icon`, mesmo que o cliente envie
    # um arquivo arbitrariamente grande.
    max_bytes = settings.max_icon_upload_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    try:
        set_image_icon(db, image_id, content, settings=settings)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationFailedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    audit("admin.image.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None, target=f"imagem {image_id}",
          outcome="success", detail="op=capa")

    return _to_response(get_image(db, image_id))


@admin_router.post("/images/{image_id}/disable", status_code=status.HTTP_204_NO_CONTENT)
def disable_image_endpoint(
    image_id: int,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    disable_image(db, image_id)
    audit("admin.image.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None, target=f"imagem {image_id}",
          outcome="success", detail="op=desabilitar")


@admin_router.get("/images", response_model=list[ImageResponse])
def list_images_admin_endpoint(db: sqlite3.Connection = Depends(get_db)) -> list[ImageResponse]:
    return [_to_response(row) for row in list_catalog_for_admin(db)]


@catalog_router.get("/catalog", response_model=list[ImageResponse])
def list_catalog_endpoint(
    user: AuthenticatedUser = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)
) -> list[ImageResponse]:
    return [_to_response(row) for row in list_catalog_for_user(db, user.id)]

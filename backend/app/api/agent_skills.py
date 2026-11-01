"""Rotas administrativas da biblioteca de skills e do vínculo com imagens.

Todas exigem papel de administrador (mesma regra do catálogo de imagens e
da biblioteca de documentos AGENTS.md). Vincular/desvincular dispara
rebuild imediato da imagem em segundo plano (ver agent_images.rebuild_agent_image),
no mesmo padrão de `spawn` usado por `create_image_endpoint`/
`retry_pull_endpoint` em `api/images.py`.
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.deps import get_db, require_admin
from app.services.audit_log import audit
from app.services.sessions import AuthenticatedUser
from app.services.agent_images import rebuild_agent_image
from app.services.agent_skills import (
    create_skill,
    delete_skill,
    get_skill,
    link_skill,
    linked_skill_ids,
    list_images_with_skills,
    list_skills,
    unlink_skill,
    update_skill,
)
from app.services.background import spawn
from app.services.errors import ConflictError, NotFoundError, ValidationFailedError
from app.services.images import mark_pull_started

router = APIRouter(dependencies=[Depends(require_admin)])


class CreateSkillRequest(BaseModel):
    display_name: str
    repo_owner: str
    repo_name: str
    subpath: str = ""


class UpdateSkillRequest(BaseModel):
    display_name: str | None = None
    repo_owner: str | None = None
    repo_name: str | None = None
    subpath: str | None = None


class SkillResponse(BaseModel):
    id: int
    display_name: str
    repo_owner: str
    repo_name: str
    subpath: str
    linked_images: int
    updated_at: str | None


class ImageSkillsResponse(BaseModel):
    id: int
    display_name: str
    repository: str
    tag: str
    skill_ids: list[int]
    pull_state: str
    pull_progress: str | None
    pull_error: str | None


def _to_response(row: sqlite3.Row) -> SkillResponse:
    return SkillResponse(
        id=row["id"],
        display_name=row["display_name"],
        repo_owner=row["repo_owner"],
        repo_name=row["repo_name"],
        subpath=row["subpath"],
        linked_images=row["linked_images"],
        updated_at=row["updated_at"],
    )


@router.get("/agent-skills", response_model=list[SkillResponse])
def list_skills_endpoint(db: sqlite3.Connection = Depends(get_db)) -> list[SkillResponse]:
    return [_to_response(row) for row in list_skills(db)]


@router.post("/agent-skills", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
def create_skill_endpoint(
    body: CreateSkillRequest,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> SkillResponse:
    try:
        skill_id = create_skill(
            db, body.display_name, body.repo_owner, body.repo_name, body.subpath
        )
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValidationFailedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    audit("admin.skill.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None, target=body.display_name,
          outcome="success", detail="op=criar")
    return _to_response(get_skill(db, skill_id))


@router.patch("/agent-skills/{skill_id}", response_model=SkillResponse)
def update_skill_endpoint(
    skill_id: int,
    body: UpdateSkillRequest,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> SkillResponse:
    try:
        update_skill(
            db,
            skill_id,
            display_name=body.display_name,
            repo_owner=body.repo_owner,
            repo_name=body.repo_name,
            subpath=body.subpath,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValidationFailedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    audit("admin.skill.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None, target=f"skill {skill_id}",
          outcome="success", detail="op=editar")
    return _to_response(get_skill(db, skill_id))


@router.delete("/agent-skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill_endpoint(
    skill_id: int,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    try:
        delete_skill(db, skill_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit("admin.skill.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None, target=f"skill {skill_id}",
          outcome="success", detail="op=excluir")


def _image_response(row: sqlite3.Row, skill_ids: list[int]) -> ImageSkillsResponse:
    return ImageSkillsResponse(
        id=row["id"],
        display_name=row["display_name"],
        repository=row["repository"],
        tag=row["tag"],
        skill_ids=skill_ids,
        pull_state=row["pull_state"],
        pull_progress=row["pull_progress"],
        pull_error=row["pull_error"],
    )


@router.get("/agent-skills/images", response_model=list[ImageSkillsResponse])
def list_image_links_endpoint(
    db: sqlite3.Connection = Depends(get_db),
) -> list[ImageSkillsResponse]:
    return [
        _image_response(row, linked_skill_ids(db, row["id"]))
        for row in list_images_with_skills(db)
    ]


async def _link_or_unlink(
    request: Request,
    db: sqlite3.Connection,
    image_id: int,
    skill_id: int,
    *,
    link: bool,
    admin: AuthenticatedUser,
) -> ImageSkillsResponse:
    try:
        if link:
            link_skill(db, image_id, skill_id)
        else:
            unlink_skill(db, image_id, skill_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationFailedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    skill_ids = linked_skill_ids(db, image_id)

    # Marca "pulling" já aqui (não só dentro do `run_build` em segundo
    # plano): a task spawnada abaixo só roda no próximo ponto de `await`,
    # então sem isso a resposta e o primeiro poll do admin ainda veriam o
    # estado antigo (ex: "ready") por alguns instantes.
    mark_pull_started(db, image_id)
    image_row = db.execute(
        "SELECT id, display_name, repository, tag, pull_state, pull_progress, pull_error"
        " FROM images WHERE id = ?",
        (image_id,),
    ).fetchone()

    settings = request.app.state.settings
    runtime = request.app.state.runtime
    spawn(request.app, rebuild_agent_image(settings, runtime, image_id))
    audit("admin.skill.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None, target=f"imagem {image_id}",
          outcome="success", detail=f"op={'vincular' if link else 'desvincular'} skill {skill_id}")

    return _image_response(image_row, skill_ids)


@router.post("/agent-skills/images/{image_id}/skills/{skill_id}", response_model=ImageSkillsResponse)
async def link_skill_endpoint(
    image_id: int,
    skill_id: int,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> ImageSkillsResponse:
    return await _link_or_unlink(request, db, image_id, skill_id, link=True, admin=admin)


@router.delete("/agent-skills/images/{image_id}/skills/{skill_id}", response_model=ImageSkillsResponse)
async def unlink_skill_endpoint(
    image_id: int,
    skill_id: int,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> ImageSkillsResponse:
    return await _link_or_unlink(request, db, image_id, skill_id, link=False, admin=admin)

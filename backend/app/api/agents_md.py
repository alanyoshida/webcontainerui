"""Rotas administrativas da biblioteca de documentos AGENTS.md.

Todas exigem papel de administrador (mesma regra do catálogo de imagens).
As rotas de escrita devolvem as falhas de propagacao para instancias vivas
no formato da regeneracao de chave SSH, para o admin ver quais instancias
ficaram desatualizadas.
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.deps import get_db, require_admin
from app.services.audit_log import audit
from app.services.sessions import AuthenticatedUser
from app.services.agents_md import (
    create_document,
    delete_document,
    get_document,
    list_documents,
    propagate_document_to_live_instances,
    remove_document_from_live_instances,
    set_image_document,
    update_document,
)
from app.services.errors import ConflictError, NotFoundError, ValidationFailedError

router = APIRouter(dependencies=[Depends(require_admin)])


class CreateDocumentRequest(BaseModel):
    name: str
    content: str


class UpdateDocumentRequest(BaseModel):
    name: str | None = None
    content: str | None = None


class LinkDocumentRequest(BaseModel):
    document_id: int | None = None


class DocumentResponse(BaseModel):
    id: int
    name: str
    content: str
    linked_images: int
    updated_at: str | None


class UpdateDocumentResponse(BaseModel):
    document: DocumentResponse
    propagation_failures: list[str]


class LinkDocumentResponse(BaseModel):
    image_id: int
    document_id: int | None
    propagation_failures: list[str]


class ImageLinkResponse(BaseModel):
    id: int
    display_name: str
    repository: str
    tag: str
    document_id: int | None


def _to_response(row: sqlite3.Row) -> DocumentResponse:
    return DocumentResponse(
        id=row["id"],
        name=row["name"],
        content=row["content"],
        linked_images=row["linked_images"],
        updated_at=row["updated_at"],
    )


@router.get("/agents-md", response_model=list[DocumentResponse])
def list_documents_endpoint(db: sqlite3.Connection = Depends(get_db)) -> list[DocumentResponse]:
    return [_to_response(row) for row in list_documents(db)]


@router.post("/agents-md", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document_endpoint(
    body: CreateDocumentRequest,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> DocumentResponse:
    settings = request.app.state.settings
    try:
        document_id = create_document(db, body.name, body.content, settings=settings)
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValidationFailedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    audit("admin.document.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None, target=body.name,
          outcome="success", detail="op=criar")
    return _to_response(get_document(db, document_id))


@router.patch("/agents-md/{document_id}", response_model=UpdateDocumentResponse)
async def update_document_endpoint(
    document_id: int,
    body: UpdateDocumentRequest,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> UpdateDocumentResponse:
    settings = request.app.state.settings
    try:
        update_document(
            db,
            document_id,
            name=body.name,
            content=body.content,
            settings=settings,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValidationFailedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit("admin.document.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None, target=f"documento {document_id}",
          outcome="success", detail="op=editar")
    document = get_document(db, document_id)
    failures = await propagate_document_to_live_instances(
        db, request.app.state.runtime, settings, document_id
    )
    return UpdateDocumentResponse(
        document=_to_response(document),
        propagation_failures=[f["instance_id"] for f in failures],
    )


@router.delete("/agents-md/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_endpoint(
    document_id: int,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    try:
        delete_document(db, document_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    audit("admin.document.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None, target=f"documento {document_id}",
          outcome="success", detail="op=excluir")


@router.get("/agents-md/images", response_model=list[ImageLinkResponse])
def list_image_links_endpoint(db: sqlite3.Connection = Depends(get_db)) -> list[ImageLinkResponse]:
    return [
        ImageLinkResponse(
            id=row["id"],
            display_name=row["display_name"],
            repository=row["repository"],
            tag=row["tag"],
            document_id=row["agents_md_id"],
        )
        for row in db.execute("SELECT * FROM images ORDER BY id")
    ]


@router.put("/agents-md/images/{image_id}", response_model=LinkDocumentResponse)
async def link_document_endpoint(
    image_id: int,
    body: LinkDocumentRequest,
    request: Request,
    admin: AuthenticatedUser = Depends(require_admin),
    db: sqlite3.Connection = Depends(get_db),
) -> LinkDocumentResponse:
    previous_id = db.execute(
        "SELECT agents_md_id FROM images WHERE id = ?", (image_id,)
    ).fetchone()

    try:
        set_image_document(db, image_id, body.document_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    runtime = request.app.state.runtime
    settings = request.app.state.settings
    failures: list[str] = []
    if body.document_id is not None:
        propagadas = await propagate_document_to_live_instances(
            db, runtime, settings, body.document_id
        )
        failures = [f["instance_id"] for f in propagadas]
    elif previous_id is not None:
        removidas = await remove_document_from_live_instances(db, runtime, image_id)
        failures = [f["instance_id"] for f in removidas]

    audit("admin.document.changed", actor_id=admin.id, actor_email=admin.email,
          ip=request.client.host if request.client else None, target=f"imagem {image_id}",
          outcome="success", detail=f"op=vincular documento {body.document_id}")
    return LinkDocumentResponse(
        image_id=image_id,
        document_id=body.document_id,
        propagation_failures=failures,
    )
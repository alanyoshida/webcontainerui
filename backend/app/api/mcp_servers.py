"""Rotas administrativas da biblioteca de servidores MCP.

Todas exigem papel de administrador (mesma regra de `agents_md` e
`agent_skills`). Editar, remover e vincular/desvincular propagam na hora
para as instâncias vivas das imagens afetadas (MCP é só configuração, sem
rebuild — ver design.md) e devolvem tanto `propagation_failures` (erro de
runtime) quanto `schema_validation_errors` (quebra de contrato do arquivo
da ferramenta, com o campo por MCP) para o admin corrigir ciente.
"""

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.config import Settings
from app.deps import get_db, require_admin
from app.services.errors import ConflictError, NotFoundError, ValidationFailedError
from app.services.mcp_servers import (
    create_mcp_server,
    decrypt_dict,
    delete_mcp_server,
    get_mcp_server,
    has_secret,
    link_mcp_server,
    linked_mcp_server_ids,
    list_images_with_mcp_servers,
    list_mcp_servers,
    propagate_mcp_servers_to_live_instances,
    unlink_mcp_server,
    update_mcp_server,
)

router = APIRouter(dependencies=[Depends(require_admin)])


class CreateMcpServerRequest(BaseModel):
    display_name: str
    transport: str
    command: str | None = None
    args: list[str] | None = None
    url: str | None = None
    env: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    enabled: bool = True


class UpdateMcpServerRequest(BaseModel):
    display_name: str | None = None
    transport: str | None = None
    command: str | None = None
    args: list[str] | None = None
    url: str | None = None
    env: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    enabled: bool | None = None


class McpServerResponse(BaseModel):
    id: int
    display_name: str
    transport: str
    command: str | None
    args: list[str]
    url: str | None
    env_keys: list[str]
    headers_keys: list[str]
    enabled: bool
    linked_images: int
    updated_at: str | None


class UpdateMcpServerResponse(BaseModel):
    server: McpServerResponse
    propagation_failures: list[dict]
    schema_validation_errors: list[dict]


class DeleteMcpServerResponse(BaseModel):
    propagation_failures: list[dict]
    schema_validation_errors: list[dict]


class ImageMcpServersResponse(BaseModel):
    id: int
    display_name: str
    repository: str
    tag: str
    mcp_server_ids: list[int]
    propagation_failures: list[dict]
    schema_validation_errors: list[dict]


def _secret_keys(row: sqlite3.Row, field: str, settings: Settings) -> list[str]:
    """Chaves (nunca valores) do segredo cifrado — o admin vê o que existe
    cadastrado sem reexibir o valor (mesmo trade-off da chave SSH). Uma
    linha com blob ilegível não pode derrubar a listagem inteira: devolve
    sem as chaves, mesmo tratamento de isolamento por MCP do resto do
    módulo."""
    if not has_secret(row, field):
        return []
    try:
        return sorted(decrypt_dict(settings, row[f"{field}_encrypted"]))
    except Exception:  # noqa: BLE001 - blob corrompido é isolado, não fatal
        return []


def _args_of(row: sqlite3.Row) -> list[str]:
    try:
        args = json.loads(row["args_json"]) if row["args_json"] else []
    except (TypeError, ValueError):
        return []
    return args if isinstance(args, list) else []


def _to_response(row: sqlite3.Row, settings: Settings) -> McpServerResponse:
    return McpServerResponse(
        id=row["id"],
        display_name=row["display_name"],
        transport=row["transport"],
        command=row["command"],
        args=_args_of(row),
        url=row["url"],
        env_keys=_secret_keys(row, "env", settings),
        headers_keys=_secret_keys(row, "headers", settings),
        enabled=bool(row["enabled"]),
        linked_images=row["linked_images"],
        updated_at=row["updated_at"],
    )


def _linked_image_ids(db: sqlite3.Connection, mcp_server_id: int) -> list[int]:
    return [
        row[0]
        for row in db.execute(
            "SELECT image_id FROM image_mcp_servers WHERE mcp_server_id = ? ORDER BY image_id",
            (mcp_server_id,),
        )
    ]


async def _propagate(request: Request, db: sqlite3.Connection, image_ids: list[int]) -> tuple[list[dict], list[dict]]:
    """Propaga cada imagem afetada e junta os relatórios. Best-effort:
    nunca levanta por falha individual (padrão de `agents_md`)."""
    settings = request.app.state.settings
    runtime = request.app.state.runtime
    propagation_failures: list[dict] = []
    schema_validation_errors: list[dict] = []
    for image_id in image_ids:
        failures, validation = await propagate_mcp_servers_to_live_instances(
            db, runtime, settings, image_id
        )
        propagation_failures.extend(failures)
        schema_validation_errors.extend(validation)
    return propagation_failures, schema_validation_errors


@router.get("/mcp-servers", response_model=list[McpServerResponse])
def list_mcp_servers_endpoint(
    request: Request, db: sqlite3.Connection = Depends(get_db)
) -> list[McpServerResponse]:
    settings: Settings = request.app.state.settings
    return [_to_response(row, settings) for row in list_mcp_servers(db)]


@router.post("/mcp-servers", response_model=McpServerResponse, status_code=status.HTTP_201_CREATED)
def create_mcp_server_endpoint(
    body: CreateMcpServerRequest, request: Request, db: sqlite3.Connection = Depends(get_db)
) -> McpServerResponse:
    settings: Settings = request.app.state.settings
    try:
        mcp_id = create_mcp_server(
            db,
            body.display_name,
            body.transport,
            settings=settings,
            command=body.command,
            args=body.args,
            url=body.url,
            env=body.env,
            headers=body.headers,
            enabled=body.enabled,
        )
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValidationFailedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_response(get_mcp_server(db, mcp_id), settings)


@router.patch("/mcp-servers/{mcp_server_id}", response_model=UpdateMcpServerResponse)
async def update_mcp_server_endpoint(
    mcp_server_id: int,
    body: UpdateMcpServerRequest,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
) -> UpdateMcpServerResponse:
    settings: Settings = request.app.state.settings
    try:
        update_mcp_server(
            db,
            mcp_server_id,
            settings=settings,
            display_name=body.display_name,
            transport=body.transport,
            command=body.command,
            args=body.args,
            url=body.url,
            env=body.env,
            headers=body.headers,
            enabled=body.enabled,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValidationFailedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    propagation_failures, schema_validation_errors = await _propagate(
        request, db, _linked_image_ids(db, mcp_server_id)
    )
    return UpdateMcpServerResponse(
        server=_to_response(get_mcp_server(db, mcp_server_id), settings),
        propagation_failures=propagation_failures,
        schema_validation_errors=schema_validation_errors,
    )


@router.delete("/mcp-servers/{mcp_server_id}", response_model=DeleteMcpServerResponse)
async def delete_mcp_server_endpoint(
    mcp_server_id: int, request: Request, db: sqlite3.Connection = Depends(get_db)
) -> DeleteMcpServerResponse:
    # As imagens afetadas precisam ser coletadas antes do cascade do delete
    # (tarefa 3.2: remover não recusa por vínculo — desvincula e propaga).
    image_ids = _linked_image_ids(db, mcp_server_id)
    try:
        delete_mcp_server(db, mcp_server_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    propagation_failures, schema_validation_errors = await _propagate(request, db, image_ids)
    return DeleteMcpServerResponse(
        propagation_failures=propagation_failures,
        schema_validation_errors=schema_validation_errors,
    )


@router.get("/mcp-servers/images", response_model=list[ImageMcpServersResponse])
def list_image_links_endpoint(db: sqlite3.Connection = Depends(get_db)) -> list[ImageMcpServersResponse]:
    return [
        ImageMcpServersResponse(
            id=row["id"],
            display_name=row["display_name"],
            repository=row["repository"],
            tag=row["tag"],
            mcp_server_ids=linked_mcp_server_ids(db, row["id"]),
            propagation_failures=[],
            schema_validation_errors=[],
        )
        for row in list_images_with_mcp_servers(db)
    ]


async def _link_or_unlink(
    request: Request,
    db: sqlite3.Connection,
    image_id: int,
    mcp_server_id: int,
    *,
    link: bool,
) -> ImageMcpServersResponse:
    try:
        if link:
            link_mcp_server(db, image_id, mcp_server_id)
        else:
            unlink_mcp_server(db, image_id, mcp_server_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationFailedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    propagation_failures, schema_validation_errors = await propagate_mcp_servers_to_live_instances(
        db, request.app.state.runtime, request.app.state.settings, image_id
    )
    row = db.execute(
        "SELECT id, display_name, repository, tag FROM images WHERE id = ?", (image_id,)
    ).fetchone()
    return ImageMcpServersResponse(
        id=row["id"],
        display_name=row["display_name"],
        repository=row["repository"],
        tag=row["tag"],
        mcp_server_ids=linked_mcp_server_ids(db, image_id),
        propagation_failures=propagation_failures,
        schema_validation_errors=schema_validation_errors,
    )


@router.post(
    "/mcp-servers/images/{image_id}/servers/{mcp_server_id}", response_model=ImageMcpServersResponse
)
async def link_mcp_server_endpoint(
    image_id: int,
    mcp_server_id: int,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
) -> ImageMcpServersResponse:
    return await _link_or_unlink(request, db, image_id, mcp_server_id, link=True)


@router.delete(
    "/mcp-servers/images/{image_id}/servers/{mcp_server_id}", response_model=ImageMcpServersResponse
)
async def unlink_mcp_server_endpoint(
    image_id: int,
    mcp_server_id: int,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
) -> ImageMcpServersResponse:
    return await _link_or_unlink(request, db, image_id, mcp_server_id, link=False)

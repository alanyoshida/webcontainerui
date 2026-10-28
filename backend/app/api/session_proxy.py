"""Encaminhamento HTTP e WebSocket de `/i/{instance_id}/...` até o container.

A autorização aqui é manual (sem `Depends`), de propósito: HTTP e
WebSocket precisam da mesma verificação de sessão e propriedade, mas
respondem de formas diferentes a uma recusa (status HTTP vs. fechar o
canal), e mantê-las lado a lado deixa isso explícito.
"""

import asyncio
import base64
import sqlite3

import httpx
import websockets
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from websockets.exceptions import WebSocketException

from app.deps import SESSION_COOKIE_NAME, get_db, get_db_ws
from app.services.errors import NotFoundError
from app.services.instances import get_owned_instance
from app.services.sessions import AuthenticatedUser, resolve_session

router = APIRouter()

# Fechamentos no intervalo 4000-4999 (reservado a uso de aplicação pela
# RFC 6455), espelhando os status HTTP equivalentes do lado REST.
WS_CLOSE_UNAUTHENTICATED = 4401
WS_CLOSE_NOT_FOUND = 4404
WS_CLOSE_NOT_RUNNING = 4409
WS_CLOSE_UPSTREAM_UNAVAILABLE = 4502

# Sessões de desktop são conexões de longa duração; o Nginx interno do
# container já usa 3600s (ver Reverse Proxy em design.md), e o cliente
# httpx por padrão corta em 5s — sem isto, uma sessão legitimamente
# ociosa (ou um download de resposta mais lento) seria encerrada.
UPSTREAM_TIMEOUT_SECONDS = 3600.0


def default_backend_base_url(row: sqlite3.Row) -> str:
    return f"http://{row['container_name']}:3000"


def _resolver(connection: Request | WebSocket):
    return getattr(connection.app.state, "backend_resolver", default_backend_base_url)


def _basic_auth_header(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return f"Basic {token}"


def _authenticate(db: sqlite3.Connection, token: str | None) -> AuthenticatedUser | None:
    if token is None:
        return None
    return resolve_session(db, token)


@router.api_route(
    "/i/{instance_id}/{rest:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    include_in_schema=False,  # encaminhamento bruto, não um endpoint REST documentável
)
async def proxy_http(
    instance_id: str, rest: str, request: Request, db: sqlite3.Connection = Depends(get_db)
):
    user = _authenticate(db, request.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="não autenticado")

    try:
        row = get_owned_instance(db, instance_id, user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="não encontrada") from exc

    if row["state"] != "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="instância não está em execução"
        )

    request.app.state.activity_tracker.touch(instance_id)

    base_url = _resolver(request)(row)
    target = f"{base_url}/i/{instance_id}/{rest}"
    if request.url.query:
        target += f"?{request.url.query}"

    # Cabeçalhos do cliente são descartados aqui: a credencial que importa
    # é a da instância, nunca a que o cliente eventualmente enviar.
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "authorization")}
    headers["authorization"] = _basic_auth_header(row["inner_user"], row["inner_password"])

    # Corpo encaminhado por fluxo só quando pode haver um de fato: iterar
    # `request.stream()` para um método sem corpo força transfer-encoding
    # chunked e trava esperando um corpo que a transport ASGI nunca manda,
    # o que basta para o `httpx.AsyncClient` estourar em timeout.
    has_body = request.method in ("POST", "PUT", "PATCH")
    body_content = request.stream() if has_body else None

    client = httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT_SECONDS)
    try:
        upstream_request = client.build_request(
            request.method, target, headers=headers, content=body_content
        )
        upstream_response = await client.send(upstream_request, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="instância indisponível"
        ) from exc

    response_headers = {
        k: v for k, v in upstream_response.headers.items() if k.lower() != "content-length"
    }

    async def body_iterator():
        try:
            async for chunk in upstream_response.aiter_raw():
                yield chunk
        finally:
            await upstream_response.aclose()
            await client.aclose()

    return StreamingResponse(
        body_iterator(), status_code=upstream_response.status_code, headers=response_headers
    )


@router.websocket("/i/{instance_id}/{rest:path}")
async def proxy_websocket(
    websocket: WebSocket, instance_id: str, rest: str, db: sqlite3.Connection = Depends(get_db_ws)
) -> None:
    user = _authenticate(db, websocket.cookies.get(SESSION_COOKIE_NAME))
    if user is None:
        await websocket.close(code=WS_CLOSE_UNAUTHENTICATED)
        return

    try:
        row = get_owned_instance(db, instance_id, user.id)
    except NotFoundError:
        await websocket.close(code=WS_CLOSE_NOT_FOUND)
        return

    if row["state"] != "running":
        await websocket.close(code=WS_CLOSE_NOT_RUNNING)
        return

    base_url = _resolver(websocket)(row)
    ws_target = base_url.replace("http://", "ws://", 1) + f"/i/{instance_id}/{rest}"
    headers = {"authorization": _basic_auth_header(row["inner_user"], row["inner_password"])}
    tracker = websocket.app.state.activity_tracker

    try:
        # ping_interval=None: isto é um relay transparente, não um
        # cliente com opinião própria sobre vivacidade — uma sessão
        # ociosa não deve ser encerrada pela nossa política, só pela
        # inatividade tratada em D8/ActivityTracker.
        async with websockets.connect(
            ws_target, additional_headers=headers, ping_interval=None
        ) as upstream:
            await websocket.accept()
            await _relay(websocket, upstream, tracker, instance_id)
    except (OSError, WebSocketException):
        # upstream inalcançável: se a conexão com o cliente ainda não foi
        # aceita, o close abaixo é o handshake sendo recusado.
        await websocket.close(code=WS_CLOSE_UPSTREAM_UNAVAILABLE)


async def _relay(client_ws: WebSocket, upstream_ws, tracker, instance_id: str) -> None:
    async def client_to_upstream():
        try:
            while True:
                message = await client_ws.receive()
                if message["type"] == "websocket.disconnect":
                    break
                tracker.touch(instance_id)
                if "text" in message and message["text"] is not None:
                    await upstream_ws.send(message["text"])
                elif "bytes" in message and message["bytes"] is not None:
                    await upstream_ws.send(message["bytes"])
        except WebSocketDisconnect:
            pass

    async def upstream_to_client():
        async for message in upstream_ws:
            tracker.touch(instance_id)
            if isinstance(message, bytes):
                await client_ws.send_bytes(message)
            else:
                await client_ws.send_text(message)

    done, pending = await asyncio.wait(
        [asyncio.create_task(client_to_upstream()), asyncio.create_task(upstream_to_client())],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
    for task in done:
        task.exception()  # consome exceções para não ficarem "nunca aguardadas"

import sqlite3
from collections.abc import Generator
from typing import Any

from fastapi import Depends, HTTPException, Request, WebSocket, status

from app.db import connect
from app.services.sessions import AuthenticatedUser, resolve_session

SESSION_COOKIE_NAME = "wcui_session"


def _open_db(app: Any) -> Generator[sqlite3.Connection, None, None]:
    """Abre uma conexão de vida curta, fechando ao final (D5).

    Compartilhada entre `get_db` e `get_db_ws`: o schema já existe
    (aplicado no lifespan), então só se abre a conexão aqui.
    """
    conn = connect(app.state.settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


def get_db(request: Request) -> Generator[sqlite3.Connection, None, None]:
    yield from _open_db(request.app)


def get_db_ws(websocket: WebSocket) -> Generator[sqlite3.Connection, None, None]:
    """Equivalente de `get_db` para rotas WebSocket.

    FastAPI resolve `Depends` por tipo exato do parâmetro (`Request` vs.
    `WebSocket`), então uma rota websocket precisa da sua própria
    dependência em vez de reusar `get_db` diretamente.
    """
    yield from _open_db(websocket.app)


def get_current_user(
    request: Request, db: sqlite3.Connection = Depends(get_db)
) -> AuthenticatedUser:
    """Exige sessão válida. Toda rota não pública deve depender disto.

    A resposta para ausência de cookie, token revogado, expirado ou de
    usuário desabilitado é sempre a mesma: 401 sem detalhe adicional.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="não autenticado")
    user = resolve_session(db, token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="não autenticado")
    return user


def require_admin(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="requer administrador")
    return user

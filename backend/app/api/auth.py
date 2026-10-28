import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.deps import SESSION_COOKIE_NAME, get_current_user, get_db
from app.services.passwords import hash_password, verify_password
from app.services.sessions import (
    AuthenticatedUser,
    create_session,
    revoke_session,
)

router = APIRouter()

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="credenciais inválidas"
)

# Hash de referência usado quando o e-mail não existe, para que o tempo de
# resposta não varie entre "e-mail inexistente" e "senha incorreta" — a
# diferença de custo entre pular o Argon2 e executá-lo é o que permitiria
# distinguir os dois casos além do corpo da resposta.
_DUMMY_HASH = hash_password("senha-de-referencia-sem-significado")


class LoginRequest(BaseModel):
    email: str
    password: str


class SessionUserResponse(BaseModel):
    id: int
    email: str
    is_admin: bool


@router.post("/login", response_model=SessionUserResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: sqlite3.Connection = Depends(get_db),
) -> SessionUserResponse:
    row = db.execute(
        "SELECT id, email, password_hash, is_admin, disabled_at FROM users WHERE email = ?",
        (body.email,),
    ).fetchone()

    if row is None:
        verify_password(body.password, _DUMMY_HASH)
        raise _INVALID_CREDENTIALS

    if row["disabled_at"] is not None:
        raise _INVALID_CREDENTIALS

    if not verify_password(body.password, row["password_hash"]):
        raise _INVALID_CREDENTIALS

    settings = request.app.state.settings
    token = create_session(db, row["id"], settings.session_ttl_hours)

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )
    return SessionUserResponse(id=row["id"], email=row["email"], is_admin=bool(row["is_admin"]))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is not None:
        revoke_session(db, token)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


@router.get("/me", response_model=SessionUserResponse)
def me(user: AuthenticatedUser = Depends(get_current_user)) -> SessionUserResponse:
    return SessionUserResponse(id=user.id, email=user.email, is_admin=user.is_admin)

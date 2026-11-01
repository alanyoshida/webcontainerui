import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.deps import SESSION_COOKIE_NAME, get_current_user, get_db
from app.services.audit_log import audit
from app.services.login_throttle import LoginThrottle
from app.services.passwords import hash_password, verify_password
from app.services.sessions import (
    AuthenticatedUser,
    create_session,
    resolve_session,
    revoke_session,
)

router = APIRouter()

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="credenciais inválidas"
)


def _throttle_keys(body: "LoginRequest", request: Request) -> tuple[str, str]:
    """Chaves do limitador para esta tentativa: a conta (e-mail normalizado,
    para não bifurcar o contador com variações de caixa) e a origem (IP do
    cliente — atrás de proxy confiável, o IP real via X-Forwarded-For)."""
    client_host = request.client.host if request.client is not None else "desconhecido"
    return (f"email:{body.email.strip().lower()}", f"ip:{client_host}")

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


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


@router.post("/login", response_model=SessionUserResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: sqlite3.Connection = Depends(get_db),
) -> SessionUserResponse:
    # Limite consultado antes de qualquer acesso ao banco ou Argon2: a recusa
    # é idêntica para conta existente e inexistente (anti-enumeração) e poupa
    # a CPU do hash, que é o vetor de exaustão apontado no pentest.
    throttle: LoginThrottle = request.app.state.login_throttle
    keys = _throttle_keys(body, request)
    retry_after = throttle.retry_after_seconds(*keys)
    if retry_after is not None:
        audit(
            "auth.login.throttled",
            actor_email=body.email,
            ip=_client_ip(request),
            outcome="denied",
            detail=f"retry_after={retry_after}s",
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="muitas tentativas de login; tente novamente mais tarde",
            headers={"Retry-After": str(retry_after)},
        )

    row = db.execute(
        "SELECT id, email, password_hash, is_admin, disabled_at FROM users WHERE email = ?",
        (body.email,),
    ).fetchone()

    if row is None:
        verify_password(body.password, _DUMMY_HASH)
        throttle.record_failure(*keys)
        audit("auth.login", actor_email=body.email, ip=_client_ip(request), outcome="failure")
        raise _INVALID_CREDENTIALS

    # O hash é verificado antes da checagem de desabilitação: o Argon2 roda
    # em todo ramo de falha (hash dummy cobre e-mail inexistente), para que
    # o tempo de resposta não distinga conta desabilitada de senha errada
    # (anti-enumeração por timing, achado B1 do pentest).
    if not verify_password(body.password, row["password_hash"]):
        throttle.record_failure(*keys)
        audit("auth.login", actor_email=body.email, ip=_client_ip(request), outcome="failure")
        raise _INVALID_CREDENTIALS

    if row["disabled_at"] is not None:
        throttle.record_failure(*keys)
        audit("auth.login", actor_email=body.email, ip=_client_ip(request), outcome="failure")
        raise _INVALID_CREDENTIALS

    settings = request.app.state.settings
    token = create_session(db, row["id"], settings.session_ttl_hours)
    # Sucesso zera a chave da conta; a de origem permanece, para conter o
    # spraying de várias contas de um mesmo IP.
    throttle.record_success(keys[0])
    audit(
        "auth.login",
        actor_id=row["id"],
        actor_email=row["email"],
        ip=_client_ip(request),
        outcome="success",
    )

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
        # resolve antes de revogar: sessão revogada não autentica mais
        user = resolve_session(db, token)
        revoke_session(db, token)
        if user is not None:
            audit(
                "auth.logout",
                actor_id=user.id,
                actor_email=user.email,
                ip=_client_ip(request),
                outcome="success",
            )
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


@router.get("/me", response_model=SessionUserResponse)
def me(user: AuthenticatedUser = Depends(get_current_user)) -> SessionUserResponse:
    return SessionUserResponse(id=user.id, email=user.email, is_admin=user.is_admin)

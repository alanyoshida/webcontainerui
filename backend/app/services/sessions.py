import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.db import DbConnection, as_datetime, format_ts, utcnow


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    email: str
    is_admin: bool


def create_session(conn: DbConnection, user_id: int, ttl_hours: int) -> str:
    """Cria uma sessão para o usuário e devolve o token em texto plano.

    Apenas o hash do token é persistido; o texto plano só existe nesta
    chamada, para ser devolvido ao cliente no cookie.
    """
    token = secrets.token_urlsafe(32)
    expires_at = utcnow() + timedelta(hours=ttl_hours)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (:token_hash, :user_id, :expires_at)",
        {"token_hash": _hash_token(token), "user_id": user_id, "expires_at": format_ts(expires_at)},
    )
    return token


def resolve_session(conn: DbConnection, token: str) -> AuthenticatedUser | None:
    """Devolve o usuário autenticado pelo token, ou None.

    Recusa sessão revogada, expirada, ou de usuário desabilitado — os três
    tratados como "não autenticado", sem distinção visível ao chamador.
    """
    row = conn.execute(
        """SELECT s.expires_at, s.revoked_at, u.id, u.email, u.is_admin, u.disabled_at
           FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token_hash = :token_hash""",
        {"token_hash": _hash_token(token)},
    ).fetchone()
    if row is None:
        return None
    if row["revoked_at"] is not None:
        return None
    if row["disabled_at"] is not None:
        return None
    if as_datetime(row["expires_at"]) <= utcnow():
        return None
    return AuthenticatedUser(id=row["id"], email=row["email"], is_admin=bool(row["is_admin"]))


def revoke_session(conn: DbConnection, token: str) -> None:
    conn.execute(
        "UPDATE sessions SET revoked_at = :now WHERE token_hash = :token_hash AND revoked_at IS NULL",
        {"now": format_ts(utcnow()), "token_hash": _hash_token(token)},
    )


def revoke_all_sessions_for_user(conn: DbConnection, user_id: int) -> None:
    conn.execute(
        "UPDATE sessions SET revoked_at = :now WHERE user_id = :user_id AND revoked_at IS NULL",
        {"now": format_ts(utcnow()), "user_id": user_id},
    )


def purge_sessions(conn: DbConnection, grace_hours: int) -> int:
    """Remove sessões expiradas ou revogadas há mais que a carência.

    A carência preserva o rastro recente de revogação/expiração para
    depuração e auditoria; sessões ativas nunca são tocadas (elas não
    autenticam desde a expiração/revogação — a purga só limpa linha morta).
    Devolve o número de linhas removidas.
    """
    cutoff = utcnow() - timedelta(hours=grace_hours)
    cur = conn.execute(
        """DELETE FROM sessions
           WHERE expires_at < :cutoff
              OR (revoked_at IS NOT NULL AND revoked_at < :cutoff)""",
        {"cutoff": format_ts(cutoff)},
    )
    return cur.rowcount

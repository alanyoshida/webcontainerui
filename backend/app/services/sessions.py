import hashlib
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(sep=" ", timespec="seconds")


def _parse(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    email: str
    is_admin: bool


def create_session(conn: sqlite3.Connection, user_id: int, ttl_hours: int) -> str:
    """Cria uma sessão para o usuário e devolve o token em texto plano.

    Apenas o hash do token é persistido; o texto plano só existe nesta
    chamada, para ser devolvido ao cliente no cookie.
    """
    token = secrets.token_urlsafe(32)
    expires_at = _now() + timedelta(hours=ttl_hours)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (_hash_token(token), user_id, _iso(expires_at)),
    )
    return token


def resolve_session(conn: sqlite3.Connection, token: str) -> AuthenticatedUser | None:
    """Devolve o usuário autenticado pelo token, ou None.

    Recusa sessão revogada, expirada, ou de usuário desabilitado — os três
    tratados como "não autenticado", sem distinção visível ao chamador.
    """
    row = conn.execute(
        """SELECT s.expires_at, s.revoked_at, u.id, u.email, u.is_admin, u.disabled_at
           FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token_hash = ?""",
        (_hash_token(token),),
    ).fetchone()
    if row is None:
        return None
    if row["revoked_at"] is not None:
        return None
    if row["disabled_at"] is not None:
        return None
    if _parse(row["expires_at"]) <= _now():
        return None
    return AuthenticatedUser(id=row["id"], email=row["email"], is_admin=bool(row["is_admin"]))


def revoke_session(conn: sqlite3.Connection, token: str) -> None:
    conn.execute(
        "UPDATE sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
        (_iso(_now()), _hash_token(token)),
    )


def revoke_all_sessions_for_user(conn: sqlite3.Connection, user_id: int) -> None:
    conn.execute(
        "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
        (_iso(_now()), user_id),
    )

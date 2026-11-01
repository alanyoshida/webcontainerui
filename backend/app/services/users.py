import sqlite3

from app.services.errors import ConflictError, ValidationFailedError
from app.services.passwords import hash_password
from app.services.sessions import revoke_all_sessions_for_user


def create_user(
    conn: sqlite3.Connection,
    email: str,
    password: str,
    *,
    password_min_length: int,
    is_admin: bool = False,
) -> int:
    if len(password) < password_min_length:
        raise ValidationFailedError(
            f"a senha deve ter ao menos {password_min_length} caracteres"
        )
    try:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, is_admin) VALUES (?, ?, ?)",
            (email, hash_password(password), int(is_admin)),
        )
    except sqlite3.IntegrityError as exc:
        raise ConflictError(f"e-mail já em uso: {email}") from exc
    return cur.lastrowid


def disable_user(conn: sqlite3.Connection, user_id: int, *, requester_id: int) -> None:
    """Desabilita a conta e revoga todas as sessões existentes dela.

    O registro do usuário é preservado; apenas o acesso é bloqueado. Um
    administrador não pode desabilitar a própria conta.
    """
    if requester_id == user_id:
        raise ConflictError("um administrador não pode desabilitar a própria conta")
    conn.execute(
        "UPDATE users SET disabled_at = datetime('now') WHERE id = ? AND disabled_at IS NULL",
        (user_id,),
    )
    revoke_all_sessions_for_user(conn, user_id)


def list_users(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, email, is_admin, disabled_at FROM users ORDER BY email"
    ).fetchall()

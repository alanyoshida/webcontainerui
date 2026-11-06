
from app.db import DbConnection, INTEGRITY_ERRORS, format_ts, utcnow
from app.services.errors import ConflictError, ValidationFailedError
from app.services.passwords import hash_password
from app.services.sessions import revoke_all_sessions_for_user


def create_user(
    conn: DbConnection,
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
            "INSERT INTO users (email, password_hash, is_admin)"
            " VALUES (:email, :password_hash, :is_admin) RETURNING id",
            {"email": email, "password_hash": hash_password(password), "is_admin": bool(is_admin)},
        )
    except INTEGRITY_ERRORS as exc:
        raise ConflictError(f"e-mail já em uso: {email}") from exc
    return cur.fetchone()["id"]


def disable_user(conn: DbConnection, user_id: int, *, requester_id: int) -> None:
    """Desabilita a conta e revoga todas as sessões existentes dela.

    O registro do usuário é preservado; apenas o acesso é bloqueado. Um
    administrador não pode desabilitar a própria conta.
    """
    if requester_id == user_id:
        raise ConflictError("um administrador não pode desabilitar a própria conta")
    conn.execute(
        "UPDATE users SET disabled_at = :now WHERE id = :user_id AND disabled_at IS NULL",
        {"now": format_ts(utcnow()), "user_id": user_id},
    )
    revoke_all_sessions_for_user(conn, user_id)


def list_users(conn: DbConnection) -> list:
    return conn.execute(
        "SELECT id, email, is_admin, disabled_at FROM users ORDER BY email"
    ).fetchall()

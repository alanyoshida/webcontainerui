import sqlite3

from app.config import Settings
from app.services.users import create_user


def ensure_admin(conn: sqlite3.Connection, settings: Settings) -> None:
    """Provisiona o primeiro administrador, se configurado e o banco estiver vazio.

    Com banco já contendo qualquer usuário, não cria nem sobrescreve nada
    — mesmo que a conta configurada ainda não exista, para que uma
    segunda inicialização nunca seja surpresa.
    """
    if not settings.bootstrap_admin:
        return

    (user_count,) = conn.execute("SELECT COUNT(*) FROM users").fetchone()
    if user_count > 0:
        return

    create_user(
        conn,
        settings.admin_email,
        settings.admin_password,
        password_min_length=settings.password_min_length,
        is_admin=True,
    )

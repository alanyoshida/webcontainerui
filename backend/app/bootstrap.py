from app.config import Settings
from app.db import DbConnection
from app.services.users import create_user


def ensure_admin(conn: DbConnection, settings: Settings) -> None:
    """Provisiona o primeiro administrador, se configurado e o banco estiver vazio.

    Com banco já contendo qualquer usuário, não cria nem sobrescreve nada
    — mesmo que a conta configurada ainda não exista, para que uma
    segunda inicialização nunca seja surpresa.
    """
    if not settings.bootstrap_admin:
        return

    row = conn.execute("SELECT COUNT(*) AS total FROM users").fetchone()
    if row["total"] > 0:
        return

    create_user(
        conn,
        settings.admin_email,
        settings.admin_password,
        password_min_length=settings.password_min_length,
        is_admin=True,
    )

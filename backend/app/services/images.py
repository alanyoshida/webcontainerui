import sqlite3

from app.config import Settings
from app.services.errors import ConflictError, NotFoundError


def create_image(
    conn: sqlite3.Connection,
    display_name: str,
    repository: str,
    tag: str,
    *,
    settings: Settings,
    shm_size_mb: int | None = None,
    mem_limit_mb: int | None = None,
    cpu_limit: float | None = None,
    harden_desktop: bool = False,
) -> int:
    """Registra a entrada do catálogo com estado inicial `pulling`.

    Limites de recurso omitidos recebem o padrão de `settings`. O download
    propriamente dito não ocorre aqui — quem registra agenda `run_pull` em
    segundo plano e usa este id para atualizar o progresso.
    """
    try:
        cur = conn.execute(
            """INSERT INTO images
                   (display_name, repository, tag, shm_size_mb, mem_limit_mb,
                    cpu_limit, harden_desktop, pull_state)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pulling')""",
            (
                display_name,
                repository,
                tag,
                shm_size_mb or settings.default_shm_size_mb,
                mem_limit_mb or settings.default_mem_limit_mb,
                cpu_limit or settings.default_cpu_limit,
                int(harden_desktop),
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise ConflictError(f"imagem já registrada: {repository}:{tag}") from exc
    return cur.lastrowid


def get_image(conn: sqlite3.Connection, image_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"imagem não encontrada: {image_id}")
    return row


def mark_pull_progress(conn: sqlite3.Connection, image_id: int, progress: str) -> None:
    conn.execute("UPDATE images SET pull_progress = ? WHERE id = ?", (progress, image_id))


def mark_pull_ready(conn: sqlite3.Connection, image_id: int) -> None:
    conn.execute(
        "UPDATE images SET pull_state = 'ready', pull_error = NULL WHERE id = ?",
        (image_id,),
    )


def mark_pull_failed(conn: sqlite3.Connection, image_id: int, error: str) -> None:
    conn.execute(
        "UPDATE images SET pull_state = 'failed', pull_error = ? WHERE id = ?",
        (error, image_id),
    )


def retry_pull(conn: sqlite3.Connection, image_id: int) -> None:
    """Reabre uma entrada em falha para novo download, sem recriá-la."""
    cur = conn.execute(
        """UPDATE images SET pull_state = 'pulling', pull_progress = NULL, pull_error = NULL
           WHERE id = ? AND pull_state = 'failed'""",
        (image_id,),
    )
    if cur.rowcount == 0:
        raise NotFoundError(f"imagem não está em falha: {image_id}")


def disable_image(conn: sqlite3.Connection, image_id: int) -> None:
    conn.execute("UPDATE images SET enabled = 0 WHERE id = ?", (image_id,))


def list_catalog_for_admin(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM images ORDER BY id").fetchall()


def list_catalog_for_user(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    """Imagens habilitadas, prontas e permitidas a algum grupo do usuário.

    A permissão é resolvida por junção (D5 em design.md), não
    materializada: refletir uma mudança de grupo não exige nenhuma
    atualização em cascata.
    """
    return conn.execute(
        """SELECT DISTINCT i.*
           FROM images i
           JOIN group_images gi ON gi.image_id = i.id
           JOIN user_groups ug ON ug.group_id = gi.group_id
           WHERE ug.user_id = ?
             AND i.enabled = 1
             AND i.pull_state = 'ready'
           ORDER BY i.id""",
        (user_id,),
    ).fetchall()

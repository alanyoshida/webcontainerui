import sqlite3
import uuid

from app.config import Settings
from app.services.errors import ConflictError, NotFoundError, ValidationFailedError

# Assinaturas (magic bytes) dos formatos de imagem aceitos como capa.
# Checagem por conteúdo, não pela extensão do nome enviado pelo cliente —
# um nome ".png" não garante que o conteúdo seja realmente um PNG.
_IMAGE_SIGNATURES: dict[bytes, str] = {
    b"\x89PNG\r\n\x1a\n": ".png",
    b"\xff\xd8\xff": ".jpg",
    b"GIF87a": ".gif",
    b"GIF89a": ".gif",
}


def _sniff_image_extension(content: bytes) -> str | None:
    for signature, extension in _IMAGE_SIGNATURES.items():
        if content.startswith(signature):
            return extension
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    return None


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
    port: int | None = None,
    provision_kind: str = "pull",
) -> int:
    """Registra a entrada do catálogo com estado inicial `pulling`.

    Limites de recurso omitidos recebem o padrão de `settings`; a porta
    omitida recebe 3000 (o valor que o proxy já assumia). O provisionamento
    propriamente dito não ocorre aqui — quem registra agenda `run_pull` ou
    um build em segundo plano e usa este id para atualizar o progresso.
    """
    try:
        cur = conn.execute(
            """INSERT INTO images
                   (display_name, repository, tag, shm_size_mb, mem_limit_mb,
                    cpu_limit, harden_desktop, pull_state, port, provision_kind)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pulling', ?, ?)""",
            (
                display_name,
                repository,
                tag,
                shm_size_mb or settings.default_shm_size_mb,
                mem_limit_mb or settings.default_mem_limit_mb,
                cpu_limit or settings.default_cpu_limit,
                int(harden_desktop),
                port if port is not None else 3000,
                provision_kind,
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


def mark_pull_started(conn: sqlite3.Connection, image_id: int) -> None:
    """Reabre a entrada para provisionamento e limpa o erro/progresso anterior."""
    conn.execute(
        """UPDATE images SET pull_state = 'pulling', pull_progress = NULL,
               pull_error = NULL
           WHERE id = ?""",
        (image_id,),
    )


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


def reopen_for_retry(conn: sqlite3.Connection, image_id: int) -> None:
    """Reabre uma entrada em falha para novo provisionamento, sem recriá-la.

    Não decide entre download e build: quem chama consulta
    `provision_kind` e agenda a operação correspondente.
    """
    cur = conn.execute(
        """UPDATE images SET pull_state = 'pulling', pull_progress = NULL, pull_error = NULL
           WHERE id = ? AND pull_state = 'failed'""",
        (image_id,),
    )
    if cur.rowcount == 0:
        raise NotFoundError(f"imagem não está em falha: {image_id}")


def disable_image(conn: sqlite3.Connection, image_id: int) -> None:
    conn.execute("UPDATE images SET enabled = 0 WHERE id = ?", (image_id,))


def set_image_icon(
    conn: sqlite3.Connection,
    image_id: int,
    content: bytes,
    *,
    settings: Settings,
) -> None:
    """Valida, grava e associa a imagem de capa enviada, substituindo a anterior.

    A entrada permanece com a imagem de capa anterior (se havia) quando a
    validação de tipo ou tamanho recusa o upload — nada é escrito nesse caso.
    """
    max_bytes = settings.max_icon_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise ValidationFailedError(
            f"imagem de capa maior que o limite de {settings.max_icon_upload_mb}MB"
        )

    extension = _sniff_image_extension(content)
    if extension is None:
        raise ValidationFailedError("arquivo enviado não é uma imagem reconhecida")

    row = get_image(conn, image_id)
    previous_icon_path = row["icon_path"]

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    new_filename = f"{image_id}-{uuid.uuid4().hex}{extension}"
    (settings.uploads_dir / new_filename).write_bytes(content)

    conn.execute("UPDATE images SET icon_path = ? WHERE id = ?", (new_filename, image_id))

    if previous_icon_path:
        _delete_icon_file(settings, previous_icon_path)


def _delete_icon_file(settings: Settings, icon_path: str) -> None:
    file_path = settings.uploads_dir / icon_path
    try:
        file_path.unlink()
    except FileNotFoundError:
        pass


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

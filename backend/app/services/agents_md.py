"""Biblioteca de documentos AGENTS.md gerenciada pelo administrador.

Cada entrada do catálogo pode ser vinculada a no máximo um documento, e o
conteúdo é injetado nas instâncias como `/config/AGENTS.md` (ver
`instances.py`). Este módulo só cuida do CRUD, da resolução do vínculo e da
montagem do tar a injetar — injeção e propagação vivem em `instances.py`,
no mesmo padrão da identidade SSH (`ssh_identity.py` para gerar,
`instances.py` para aplicar).
"""

import io
import sqlite3
import tarfile
import time

from app.config import Settings
from app.services.errors import ConflictError, NotFoundError, ValidationFailedError

_DOCUMENT_SELECT = """
    SELECT d.id, d.name, d.content, d.created_at, d.updated_at,
           (SELECT COUNT(*) FROM images i
             WHERE i.agents_md_id = d.id) AS linked_images
    FROM agent_md_documents d
"""


def list_documents(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(_DOCUMENT_SELECT + " ORDER BY d.name").fetchall()


def get_document(conn: sqlite3.Connection, document_id: int) -> sqlite3.Row:
    row = conn.execute(
        _DOCUMENT_SELECT + " WHERE d.id = ?", (document_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError(f"documento AGENTS.md não encontrado: {document_id}")
    return row


def get_document_for_image(conn: sqlite3.Connection, image_id: int) -> sqlite3.Row | None:
    """Documento vinculado à imagem, se houver. None significa sem vínculo."""
    return conn.execute(
        _DOCUMENT_SELECT + " WHERE d.id = (SELECT agents_md_id FROM images WHERE id = ?)",
        (image_id,),
    ).fetchone()


def _validate_content(content: str, settings: Settings) -> None:
    if not content.strip():
        raise ValidationFailedError("conteúdo do documento não pode ser vazio")
    if len(content.encode("utf-8")) > settings.max_agents_md_bytes:
        raise ValidationFailedError(
            f"conteúdo maior que o limite de {settings.max_agents_md_bytes} bytes"
        )


def create_document(
    conn: sqlite3.Connection, name: str, content: str, *, settings: Settings
) -> int:
    if not name.strip():
        raise ValidationFailedError("nome do documento não pode ser vazio")
    _validate_content(content, settings)
    try:
        cur = conn.execute(
            "INSERT INTO agent_md_documents (name, content, updated_at) VALUES (?, ?, datetime('now'))",
            (name, content),
        )
    except sqlite3.IntegrityError as exc:
        raise ConflictError(f"documento AGENTS.md já existe: {name}") from exc
    return cur.lastrowid


def update_document(
    conn: sqlite3.Connection,
    document_id: int,
    *,
    name: str | None = None,
    content: str | None = None,
    settings: Settings,
) -> None:
    """Edita nome e/ou conteúdo. Só toca nas colunas recebidas."""
    row = conn.execute(
        "SELECT id FROM agent_md_documents WHERE id = ?", (document_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError(f"documento AGENTS.md não encontrado: {document_id}")

    if name is not None:
        name = name.strip()
        if not name:
            raise ValidationFailedError("nome do documento não pode ser vazio")
    if content is not None:
        _validate_content(content, settings)

    if name is not None:
        try:
            conn.execute(
                "UPDATE agent_md_documents SET name = ?, updated_at = datetime('now')"
                " WHERE id = ?",
                (name, document_id),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"documento AGENTS.md já existe: {name}") from exc
    if content is not None:
        conn.execute(
            "UPDATE agent_md_documents SET content = ?, updated_at = datetime('now')"
            " WHERE id = ?",
            (content, document_id),
        )


def delete_document(conn: sqlite3.Connection, document_id: int) -> None:
    """Remove o documento, recusado enquanto alguma imagem o referenciar."""
    linked = conn.execute(
        "SELECT COUNT(*) FROM images WHERE agents_md_id = ?", (document_id,)
    ).fetchone()[0]
    if linked:
        raise ConflictError(
            f"documento AGENTS.md vinculado a {linked} imagem(ns): desvincule antes de remover"
        )
    cur = conn.execute(
        "DELETE FROM agent_md_documents WHERE id = ?", (document_id,)
    )
    if cur.rowcount == 0:
        raise NotFoundError(f"documento AGENTS.md não encontrado: {document_id}")


def set_image_document(
    conn: sqlite3.Connection, image_id: int, document_id: int | None
) -> None:
    """Define (ou remove, com None) o vínculo da imagem com um documento."""
    from app.services.images import get_image  # import local: evita ciclo

    get_image(conn, image_id)  # 404 se a imagem não existe
    if document_id is not None:
        exists = conn.execute(
            "SELECT 1 FROM agent_md_documents WHERE id = ?", (document_id,)
        ).fetchone()
        if exists is None:
            raise NotFoundError(f"documento AGENTS.md não encontrado: {document_id}")
    conn.execute(
        "UPDATE images SET agents_md_id = ? WHERE id = ?", (document_id, image_id)
    )


def linked_image_ids(conn: sqlite3.Connection, document_id: int) -> list[int]:
    return [
        row[0]
        for row in conn.execute(
            "SELECT id FROM images WHERE agents_md_id = ? ORDER BY id", (document_id,)
        )
    ]


def _live_instances_of_image(conn: sqlite3.Connection, image_id: int) -> list[sqlite3.Row]:
    """Instâncias com container criado e em execução da imagem informada.

    A propagação e a remoção só alcançam instâncias vivas: uma parada não
    tem processo rodando para receber `put_archive`/`exec`, e recebe o
    documento novo no próximo start via `_inject_agents_md`.
    """
    return conn.execute(
        """SELECT id AS instance_id, container_id FROM instances
           WHERE image_id = ? AND deleted_at IS NULL
             AND container_id IS NOT NULL AND state = 'running'""",
        (image_id,),
    ).fetchall()


async def propagate_document_to_live_instances(
    conn: sqlite3.Connection,
    runtime,
    settings: Settings,
    document_id: int,
) -> list[dict]:
    """Reescreve o documento em todas as instâncias vivas das imagens que o
    vinculam (spec agents-md: "Salvar documento reescreve nas instâncias
    vivas"). Best-effort por instância, como
    `propagate_ssh_identity_to_live_instances`: falha isolada não derruba o
    restante e é devolvida para o chamador reportar ao admin."""
    from app.runtime.errors import ContainerNotFoundError, RuntimeOperationError

    document = get_document(conn, document_id)
    failures: list[dict] = []
    for image_id in linked_image_ids(conn, document_id):
        image = conn.execute(
            "SELECT provision_kind FROM images WHERE id = ?", (image_id,)
        ).fetchone()
        uid, gid = _owner_uid_gid(settings, image)
        tar_bytes = build_agents_md_archive(document["content"], uid=uid, gid=gid)
        for instance in _live_instances_of_image(conn, image_id):
            try:
                await runtime.put_archive(
                    instance["container_id"], "/config", tar_bytes
                )
            except (ContainerNotFoundError, RuntimeOperationError) as exc:
                failures.append(
                    {"instance_id": instance["instance_id"], "error": str(exc)}
                )
    return failures


async def remove_document_from_live_instances(
    conn: sqlite3.Connection,
    runtime,
    image_id: int,
) -> list[dict]:
    """Remove o arquivo `/config/AGENTS.md` das instâncias vivas da imagem
    (spec agents-md: "Desvincular remove o documento das instâncias
    vivas"). Best-effort por instância, como a propagação."""
    from app.runtime.errors import ContainerNotFoundError, RuntimeOperationError

    failures: list[dict] = []
    for instance in _live_instances_of_image(conn, image_id):
        try:
            await runtime.exec(instance["container_id"], ["rm", "-f", "/config/AGENTS.md"])
        except (ContainerNotFoundError, RuntimeOperationError) as exc:
            failures.append(
                {"instance_id": instance["instance_id"], "error": str(exc)}
            )
    return failures


def _owner_uid_gid(settings: Settings, image: sqlite3.Row) -> tuple[int, int]:
    """Mesma regra de `_ssh_owner_uid_gid` em `instances.py`: root para
    imagens de agente (`provision_kind == 'build'`), PUID/PGID para webtop."""
    if image["provision_kind"] == "build":
        return 0, 0
    return settings.puid, settings.pgid


def build_agents_md_archive(content: str, *, uid: int, gid: int) -> bytes:
    """Monta o tar a injetar via `put_archive` com o documento em
    `/config/AGENTS.md` (0644, legível por qualquer ferramenta dentro do
    container), com o dono (`uid`/`gid`) informado pelo chamador — root para
    imagens de agente, PUID/PGID para webtop, mesma regra da identidade SSH.
    """
    payload = content.encode("utf-8")
    if not payload.endswith(b"\n"):
        payload += b"\n"

    buffer = io.BytesIO()
    now = int(time.time())
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        info = tarfile.TarInfo(name="AGENTS.md")
        info.size = len(payload)
        info.mode = 0o644
        info.uid = uid
        info.gid = gid
        info.mtime = now
        tar.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()
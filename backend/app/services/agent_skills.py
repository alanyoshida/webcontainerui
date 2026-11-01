"""Biblioteca de skills gerenciada pelo administrador.

Cada skill referencia um repositório do GitHub (no formato distribuído pelo
skills.sh: `owner/repo`, com um caminho opcional quando o repositório
empacota várias skills) e pode ser vinculada a N imagens de agente de
código — só a imagens com `provision_kind == 'build'`, as únicas que este
sistema constrói via Dockerfile. O vínculo dispara rebuild imediato da
imagem (ver `api/agent_skills.py`); a resolução da lista de skills para o
build em si vive em `agent_images.py`, no mesmo padrão de `ssh_identity.py`
(gera) / `instances.py` (aplica) usado pela identidade SSH.
"""

import sqlite3

from app.services.errors import ConflictError, NotFoundError, ValidationFailedError

_SKILL_SELECT = """
    SELECT s.id, s.display_name, s.repo_owner, s.repo_name, s.subpath,
           s.created_at, s.updated_at,
           (SELECT COUNT(*) FROM image_skills i WHERE i.skill_id = s.id) AS linked_images
    FROM agent_skills s
"""


def list_skills(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(_SKILL_SELECT + " ORDER BY s.display_name").fetchall()


def get_skill(conn: sqlite3.Connection, skill_id: int) -> sqlite3.Row:
    row = conn.execute(_SKILL_SELECT + " WHERE s.id = ?", (skill_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"skill não encontrada: {skill_id}")
    return row


def _validate_repo(repo_owner: str, repo_name: str) -> None:
    if not repo_owner.strip() or not repo_name.strip():
        raise ValidationFailedError("owner/repo da skill não pode ser vazio")


def create_skill(
    conn: sqlite3.Connection,
    display_name: str,
    repo_owner: str,
    repo_name: str,
    subpath: str = "",
) -> int:
    if not display_name.strip():
        raise ValidationFailedError("nome de exibição da skill não pode ser vazio")
    _validate_repo(repo_owner, repo_name)
    try:
        cur = conn.execute(
            """INSERT INTO agent_skills (display_name, repo_owner, repo_name, subpath)
               VALUES (?, ?, ?, ?)""",
            (display_name, repo_owner, repo_name, subpath),
        )
    except sqlite3.IntegrityError as exc:
        raise ConflictError(f"skill já cadastrada: {display_name}") from exc
    return cur.lastrowid


def update_skill(
    conn: sqlite3.Connection,
    skill_id: int,
    *,
    display_name: str | None = None,
    repo_owner: str | None = None,
    repo_name: str | None = None,
    subpath: str | None = None,
) -> None:
    """Edita só as colunas recebidas, como `agents_md.update_document`."""
    row = conn.execute("SELECT id FROM agent_skills WHERE id = ?", (skill_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"skill não encontrada: {skill_id}")

    if display_name is not None:
        display_name = display_name.strip()
        if not display_name:
            raise ValidationFailedError("nome de exibição da skill não pode ser vazio")

    current = get_skill(conn, skill_id)
    next_owner = repo_owner if repo_owner is not None else current["repo_owner"]
    next_name = repo_name if repo_name is not None else current["repo_name"]
    next_subpath = subpath if subpath is not None else current["subpath"]
    if repo_owner is not None or repo_name is not None:
        _validate_repo(next_owner, next_name)

    try:
        conn.execute(
            """UPDATE agent_skills
               SET display_name = ?, repo_owner = ?, repo_name = ?, subpath = ?,
                   updated_at = datetime('now')
               WHERE id = ?""",
            (
                display_name if display_name is not None else current["display_name"],
                next_owner,
                next_name,
                next_subpath,
                skill_id,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise ConflictError("nome ou repositório já usado por outra skill") from exc


def delete_skill(conn: sqlite3.Connection, skill_id: int) -> None:
    """Remove a skill e qualquer vínculo com imagens, sem recusar por uso.

    Ao contrário de `agents_md.delete_document`, a remoção aqui nunca é
    recusada por vínculo ativo (decisão explícita do escopo): desvincula de
    todas as imagens na mesma operação e não dispara rebuild só por isso.
    """
    conn.execute("DELETE FROM image_skills WHERE skill_id = ?", (skill_id,))
    cur = conn.execute("DELETE FROM agent_skills WHERE id = ?", (skill_id,))
    if cur.rowcount == 0:
        raise NotFoundError(f"skill não encontrada: {skill_id}")


def list_images_with_skills(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Imagens de agente (`provision_kind = 'build'`) com as skills vinculadas.

    Usada pela tela de vínculo por imagem no admin — só essas imagens podem
    receber skill (ver `link_skill`).
    """
    return conn.execute(
        """SELECT id, display_name, repository, tag, pull_state, pull_progress, pull_error
           FROM images WHERE provision_kind = 'build' ORDER BY id"""
    ).fetchall()


def linked_skill_ids(conn: sqlite3.Connection, image_id: int) -> list[int]:
    return [
        row[0]
        for row in conn.execute(
            "SELECT skill_id FROM image_skills WHERE image_id = ? ORDER BY skill_id",
            (image_id,),
        )
    ]


def _require_build_image(conn: sqlite3.Connection, image_id: int) -> sqlite3.Row:
    from app.services.images import get_image  # import local: evita ciclo

    image = get_image(conn, image_id)
    if image["provision_kind"] != "build":
        raise ValidationFailedError(
            "skills só podem ser vinculadas a imagens de agente de código"
        )
    return image


def link_skill(conn: sqlite3.Connection, image_id: int, skill_id: int) -> None:
    _require_build_image(conn, image_id)
    get_skill(conn, skill_id)  # 404 se a skill não existe
    conn.execute(
        "INSERT OR IGNORE INTO image_skills (image_id, skill_id) VALUES (?, ?)",
        (image_id, skill_id),
    )


def unlink_skill(conn: sqlite3.Connection, image_id: int, skill_id: int) -> None:
    _require_build_image(conn, image_id)
    get_skill(conn, skill_id)  # 404 se a skill não existe
    conn.execute(
        "DELETE FROM image_skills WHERE image_id = ? AND skill_id = ?", (image_id, skill_id)
    )


def resolve_image_skill_refs(conn: sqlite3.Connection, image_id: int) -> list[str]:
    """Lista ordenada `owner/repo` (ou `owner/repo:nome-da-skill`) das
    skills vinculadas à imagem.

    `:` separa o nome da skill (valor de `--skill` no CLI real do
    skills.sh — não existe sintaxe de URL com subpasta, ver design.md) e
    nunca aparece num `owner/repo` do GitHub, então é um delimitador seguro
    para o `RUN` de cada Dockerfile fazer o split de volta.
    """
    rows = conn.execute(
        """SELECT s.repo_owner, s.repo_name, s.subpath
           FROM image_skills i
           JOIN agent_skills s ON s.id = i.skill_id
           WHERE i.image_id = ?
           ORDER BY s.display_name""",
        (image_id,),
    ).fetchall()
    refs = []
    for row in rows:
        ref = f"{row['repo_owner']}/{row['repo_name']}"
        if row["subpath"]:
            ref = f"{ref}:{row['subpath']}"
        refs.append(ref)
    return refs

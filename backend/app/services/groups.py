from sqlalchemy.engine import RowMapping

from app.db import INTEGRITY_ERRORS, DbConnection
from app.services.errors import ConflictError


def create_group(conn: DbConnection, name: str) -> int:
    try:
        cur = conn.execute(
            "INSERT INTO groups (name) VALUES (:name) RETURNING id", {"name": name}
        )
    except INTEGRITY_ERRORS as exc:
        raise ConflictError(f"grupo já existe: {name}") from exc
    return cur.fetchone()["id"]


def rename_group(conn: DbConnection, group_id: int, name: str) -> None:
    try:
        conn.execute(
            "UPDATE groups SET name = :name WHERE id = :group_id",
            {"name": name, "group_id": group_id},
        )
    except INTEGRITY_ERRORS as exc:
        raise ConflictError(f"grupo já existe: {name}") from exc


def delete_group(conn: DbConnection, group_id: int) -> None:
    """Remove o grupo e seus vínculos, preservando os usuários membros.

    Apenas `user_groups` e `group_images` são descartados — as contas dos
    antigos membros e suas permissões vindas de outros grupos continuam
    intactas.
    """
    conn.execute(
        "DELETE FROM group_images WHERE group_id = :group_id", {"group_id": group_id}
    )
    conn.execute(
        "DELETE FROM user_groups WHERE group_id = :group_id", {"group_id": group_id}
    )
    conn.execute("DELETE FROM groups WHERE id = :group_id", {"group_id": group_id})


def add_member(conn: DbConnection, group_id: int, user_id: int) -> None:
    conn.execute(
        "INSERT INTO user_groups (user_id, group_id) VALUES (:user_id, :group_id)"
        " ON CONFLICT DO NOTHING",
        {"user_id": user_id, "group_id": group_id},
    )


def remove_member(conn: DbConnection, group_id: int, user_id: int) -> None:
    conn.execute(
        "DELETE FROM user_groups WHERE user_id = :user_id AND group_id = :group_id",
        {"user_id": user_id, "group_id": group_id},
    )


def groups_for_user(conn: DbConnection, user_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT group_id FROM user_groups WHERE user_id = :user_id",
        {"user_id": user_id},
    ).fetchall()
    return [row["group_id"] for row in rows]


def list_groups(conn: DbConnection) -> list[RowMapping]:
    return conn.execute("SELECT id, name FROM groups ORDER BY name").fetchall()


def list_members(conn: DbConnection, group_id: int) -> list[RowMapping]:
    return conn.execute(
        """SELECT u.id, u.email FROM users u
           JOIN user_groups ug ON ug.user_id = u.id
           WHERE ug.group_id = :group_id ORDER BY u.email""",
        {"group_id": group_id},
    ).fetchall()


def list_granted_images(conn: DbConnection, group_id: int) -> list[RowMapping]:
    return conn.execute(
        """SELECT img.id, img.display_name, img.repository, img.tag FROM images img
           JOIN group_images gi ON gi.image_id = img.id
           WHERE gi.group_id = :group_id ORDER BY img.display_name""",
        {"group_id": group_id},
    ).fetchall()

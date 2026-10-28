import sqlite3

from app.services.errors import ConflictError


def create_group(conn: sqlite3.Connection, name: str) -> int:
    try:
        cur = conn.execute("INSERT INTO groups (name) VALUES (?)", (name,))
    except sqlite3.IntegrityError as exc:
        raise ConflictError(f"grupo já existe: {name}") from exc
    return cur.lastrowid


def rename_group(conn: sqlite3.Connection, group_id: int, name: str) -> None:
    try:
        conn.execute("UPDATE groups SET name = ? WHERE id = ?", (name, group_id))
    except sqlite3.IntegrityError as exc:
        raise ConflictError(f"grupo já existe: {name}") from exc


def delete_group(conn: sqlite3.Connection, group_id: int) -> None:
    """Remove o grupo e seus vínculos, preservando os usuários membros.

    Apenas `user_groups` e `group_images` são descartados — as contas dos
    antigos membros e suas permissões vindas de outros grupos continuam
    intactas.
    """
    conn.execute("DELETE FROM group_images WHERE group_id = ?", (group_id,))
    conn.execute("DELETE FROM user_groups WHERE group_id = ?", (group_id,))
    conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))


def add_member(conn: sqlite3.Connection, group_id: int, user_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO user_groups (user_id, group_id) VALUES (?, ?)",
        (user_id, group_id),
    )


def remove_member(conn: sqlite3.Connection, group_id: int, user_id: int) -> None:
    conn.execute(
        "DELETE FROM user_groups WHERE user_id = ? AND group_id = ?",
        (user_id, group_id),
    )


def groups_for_user(conn: sqlite3.Connection, user_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT group_id FROM user_groups WHERE user_id = ?", (user_id,)
    ).fetchall()
    return [row["group_id"] for row in rows]


def list_groups(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT id, name FROM groups ORDER BY name").fetchall()


def list_members(conn: sqlite3.Connection, group_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT u.id, u.email FROM users u
           JOIN user_groups ug ON ug.user_id = u.id
           WHERE ug.group_id = ? ORDER BY u.email""",
        (group_id,),
    ).fetchall()


def list_granted_images(conn: sqlite3.Connection, group_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT img.id, img.display_name, img.repository, img.tag FROM images img
           JOIN group_images gi ON gi.image_id = img.id
           WHERE gi.group_id = ? ORDER BY img.display_name""",
        (group_id,),
    ).fetchall()

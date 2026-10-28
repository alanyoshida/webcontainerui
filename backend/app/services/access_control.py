import sqlite3


def is_permitted(conn: sqlite3.Connection, user_id: int, image_id: int) -> bool:
    """A permissão é a união dos grants dos grupos do usuário (D5).

    Resolvida por junção a cada chamada, não materializada: uma mudança
    de grupo vale na consulta seguinte, sem recálculo em cascata.
    """
    row = conn.execute(
        """SELECT 1
           FROM group_images gi
           JOIN user_groups ug ON ug.group_id = gi.group_id
           WHERE ug.user_id = ? AND gi.image_id = ?
           LIMIT 1""",
        (user_id, image_id),
    ).fetchone()
    return row is not None


def grant(conn: sqlite3.Connection, group_id: int, image_id: int) -> None:
    """Concede a imagem ao grupo. Repetir a mesma concessão não é erro."""
    conn.execute(
        "INSERT OR IGNORE INTO group_images (group_id, image_id) VALUES (?, ?)",
        (group_id, image_id),
    )


def _instances_affected_by_revoke(
    conn: sqlite3.Connection, group_id: int, image_id: int
) -> list[sqlite3.Row]:
    """Instâncias em execução daquela imagem, de usuários do grupo, que
    ficariam sem permissão se este grant fosse removido agora — ou seja,
    nenhum OUTRO grupo do usuário também concede a mesma imagem."""
    return conn.execute(
        """SELECT i.id, i.user_id
           FROM instances i
           JOIN user_groups ug ON ug.user_id = i.user_id AND ug.group_id = ?
           WHERE i.image_id = ?
             AND i.state = 'running'
             AND i.deleted_at IS NULL
             AND NOT EXISTS (
                 SELECT 1 FROM group_images gi2
                 JOIN user_groups ug2 ON ug2.group_id = gi2.group_id
                 WHERE ug2.user_id = i.user_id
                   AND gi2.image_id = ?
                   AND gi2.group_id != ?
             )""",
        (group_id, image_id, image_id, group_id),
    ).fetchall()


def preview_revoke(conn: sqlite3.Connection, group_id: int, image_id: int) -> list[sqlite3.Row]:
    """Só consulta; não altera nada. Usado para informar o impacto antes
    da confirmação do administrador."""
    return _instances_affected_by_revoke(conn, group_id, image_id)


def revoke(conn: sqlite3.Connection, group_id: int, image_id: int) -> list[sqlite3.Row]:
    """Remove o grant e devolve as instâncias que ficaram sem permissão,
    para o chamador pará-las via o runtime — esta função não toca em
    containers, só na tabela de grants."""
    affected = _instances_affected_by_revoke(conn, group_id, image_id)
    conn.execute(
        "DELETE FROM group_images WHERE group_id = ? AND image_id = ?", (group_id, image_id)
    )
    return affected

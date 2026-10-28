import uuid

import pytest

from .conftest import insert_image, insert_user


def test_journal_mode_e_wal(db_conn):
    mode = db_conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def _novo_id():
    return str(uuid.uuid4())


def test_segunda_instancia_viva_do_mesmo_par_e_rejeitada(db_conn):
    user_id = insert_user(db_conn)
    image_id = insert_image(db_conn)

    db_conn.execute(
        """INSERT INTO instances
               (id, user_id, image_id, volume_name, inner_user, inner_password)
           VALUES (?, ?, ?, 'vol-1', 'u', 'p')""",
        (_novo_id(), user_id, image_id),
    )

    with pytest.raises(Exception):
        db_conn.execute(
            """INSERT INTO instances
                   (id, user_id, image_id, volume_name, inner_user, inner_password)
               VALUES (?, ?, ?, 'vol-2', 'u', 'p')""",
            (_novo_id(), user_id, image_id),
        )


def test_apos_exclusao_logica_nova_instancia_e_aceita(db_conn):
    user_id = insert_user(db_conn)
    image_id = insert_image(db_conn)
    primeira_id = _novo_id()

    db_conn.execute(
        """INSERT INTO instances
               (id, user_id, image_id, volume_name, inner_user, inner_password)
           VALUES (?, ?, ?, 'vol-1', 'u', 'p')""",
        (primeira_id, user_id, image_id),
    )
    db_conn.execute(
        "UPDATE instances SET deleted_at = datetime('now') WHERE id = ?",
        (primeira_id,),
    )

    db_conn.execute(
        """INSERT INTO instances
               (id, user_id, image_id, volume_name, inner_user, inner_password)
           VALUES (?, ?, ?, 'vol-2', 'u', 'p')""",
        (_novo_id(), user_id, image_id),
    )

    vivas = db_conn.execute(
        "SELECT COUNT(*) FROM instances WHERE user_id = ? AND image_id = ? AND deleted_at IS NULL",
        (user_id, image_id),
    ).fetchone()[0]
    assert vivas == 1


def test_fixture_de_banco_nao_compartilha_estado_entre_testes_a(db_conn):
    assert insert_user(db_conn, "a@exemplo.test") == 1


def test_fixture_de_banco_nao_compartilha_estado_entre_testes_b(db_conn):
    # Se o banco do teste anterior tivesse sobrevivido, este segundo
    # usuário teria id 2, e a tabela não estaria vazia na leitura abaixo.
    total = db_conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert total == 0
    assert insert_user(db_conn, "b@exemplo.test") == 1

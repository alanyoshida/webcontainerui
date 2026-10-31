import uuid
from pathlib import Path

import pytest

from app.db import connect, init_db

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


def test_instance_runs_existe_apos_init_db(db_conn):
    columns = {row["name"] for row in db_conn.execute("PRAGMA table_info(instance_runs)")}
    assert columns == {"id", "instance_id", "user_id", "image_id", "started_at", "ended_at", "ended_reason"}


def test_ssh_identities_existe_apos_init_db(db_conn):
    columns = {row["name"] for row in db_conn.execute("PRAGMA table_info(ssh_identities)")}
    assert columns == {"user_id", "public_key", "private_key_encrypted", "created_at"}


def test_ssh_identities_uma_linha_por_usuario(db_conn):
    user_id = insert_user(db_conn)
    db_conn.execute(
        "INSERT INTO ssh_identities (user_id, public_key, private_key_encrypted) VALUES (?, ?, ?)",
        (user_id, "ssh-ed25519 AAAA...", b"cifrado"),
    )

    with pytest.raises(Exception):
        db_conn.execute(
            "INSERT INTO ssh_identities (user_id, public_key, private_key_encrypted) VALUES (?, ?, ?)",
            (user_id, "ssh-ed25519 BBBB...", b"outro"),
        )


def test_init_db_e_idempotente_com_ssh_identities_ja_presente(tmp_path):
    db_path = tmp_path / "ja-com-ssh-identities.db"
    conn = connect(db_path)
    try:
        init_db(conn)
        user_id = insert_user(conn)
        conn.execute(
            "INSERT INTO ssh_identities (user_id, public_key, private_key_encrypted) VALUES (?, ?, ?)",
            (user_id, "ssh-ed25519 AAAA...", b"cifrado"),
        )

        init_db(conn)  # roda de novo, como num restart do backend

        row = conn.execute(
            "SELECT public_key FROM ssh_identities WHERE user_id = ?", (user_id,)
        ).fetchone()
        assert row["public_key"] == "ssh-ed25519 AAAA..."
    finally:
        conn.close()


def test_init_db_normaliza_last_seen_at_no_formato_antigo(tmp_path):
    db_path = tmp_path / "formato-antigo.db"
    conn = connect(db_path)
    try:
        init_db(conn)
        user_id = insert_user(conn)
        image_id = insert_image(conn)
        instance_id = _novo_id()
        conn.execute(
            """INSERT INTO instances
                   (id, user_id, image_id, volume_name, inner_user, inner_password, last_seen_at)
               VALUES (?, ?, ?, 'vol-1', 'u', 'p', '2026-10-29 11:49:40+00:00')""",
            (instance_id, user_id, image_id),
        )

        init_db(conn)  # roda de novo a migração, como num restart do backend

        last_seen_at = conn.execute(
            "SELECT last_seen_at FROM instances WHERE id = ?", (instance_id,)
        ).fetchone()["last_seen_at"]
        assert last_seen_at == "2026-10-29 11:49:40"
    finally:
        conn.close()


def test_init_db_normalizacao_e_idempotente_e_nao_mexe_em_valores_ja_corretos(tmp_path):
    db_path = tmp_path / "ja-normalizado.db"
    conn = connect(db_path)
    try:
        init_db(conn)
        user_id = insert_user(conn)
        image_id = insert_image(conn)
        instance_id = _novo_id()
        conn.execute(
            """INSERT INTO instances
                   (id, user_id, image_id, volume_name, inner_user, inner_password, last_seen_at)
               VALUES (?, ?, ?, 'vol-1', 'u', 'p', '2026-10-29 11:49:40')""",
            (instance_id, user_id, image_id),
        )

        init_db(conn)
        init_db(conn)  # duas vezes: nada deve mudar nem falhar

        last_seen_at = conn.execute(
            "SELECT last_seen_at FROM instances WHERE id = ?", (instance_id,)
        ).fetchone()["last_seen_at"]
        assert last_seen_at == "2026-10-29 11:49:40"
    finally:
        conn.close()


def test_init_db_adiciona_icon_path_a_banco_sem_a_coluna(tmp_path):
    db_path = tmp_path / "legado.db"
    conn = connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                repository TEXT NOT NULL,
                tag TEXT NOT NULL,
                shm_size_mb INTEGER NOT NULL,
                mem_limit_mb INTEGER NOT NULL,
                cpu_limit REAL NOT NULL,
                harden_desktop INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                pull_state TEXT NOT NULL DEFAULT 'pulling',
                pull_progress TEXT,
                pull_error TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE (repository, tag)
            );
            """
        )
        conn.execute(
            """INSERT INTO images
                   (display_name, repository, tag, shm_size_mb, mem_limit_mb, cpu_limit)
               VALUES ('Webtop', 'lscr.io/linuxserver/webtop', 'latest', 1024, 2048, 2.0)"""
        )

        init_db(conn)

        columns = {row["name"] for row in conn.execute("PRAGMA table_info(images)")}
        assert "icon_path" in columns
        row = conn.execute("SELECT icon_path FROM images").fetchone()
        assert row["icon_path"] is None
    finally:
        conn.close()


def test_init_db_adiciona_colunas_de_provisionamento_a_banco_sem_elas(tmp_path):
    db_path = tmp_path / "legado-provisionamento.db"
    conn = connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                repository TEXT NOT NULL,
                tag TEXT NOT NULL,
                shm_size_mb INTEGER NOT NULL,
                mem_limit_mb INTEGER NOT NULL,
                cpu_limit REAL NOT NULL,
                harden_desktop INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                pull_state TEXT NOT NULL DEFAULT 'pulling',
                pull_progress TEXT,
                pull_error TEXT,
                icon_path TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE (repository, tag)
            );
            """
        )
        conn.execute(
            """INSERT INTO images
                   (display_name, repository, tag, shm_size_mb, mem_limit_mb, cpu_limit)
               VALUES ('Webtop', 'lscr.io/linuxserver/webtop', 'latest', 1024, 2048, 2.0)"""
        )

        init_db(conn)

        columns = {row["name"] for row in conn.execute("PRAGMA table_info(images)")}
        assert {"port", "provision_kind", "build_hash"} <= columns
        row = conn.execute(
            "SELECT port, provision_kind, build_hash FROM images"
        ).fetchone()
        assert row["port"] == 3000
        assert row["provision_kind"] == "pull"
        assert row["build_hash"] is None
    finally:
        conn.close()

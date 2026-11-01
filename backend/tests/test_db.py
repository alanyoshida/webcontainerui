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


def test_init_db_adiciona_icon_source_e_marca_capas_como_admin(tmp_path):
    db_path = tmp_path / "legado-icon-source.db"
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
                   (display_name, repository, tag, shm_size_mb, mem_limit_mb, cpu_limit, icon_path)
               VALUES ('Com capa', 'r1/teste', 'latest', 1024, 2048, 2.0, '1-abc.png')"""
        )
        conn.execute(
            """INSERT INTO images
                   (display_name, repository, tag, shm_size_mb, mem_limit_mb, cpu_limit)
               VALUES ('Sem capa', 'r2/teste', 'latest', 1024, 2048, 2.0)"""
        )

        init_db(conn)
        init_db(conn)  # idempotente: rodar de novo não reverte o backfill

        columns = {row["name"] for row in conn.execute("PRAGMA table_info(images)")}
        assert "icon_source" in columns
        rows = {
            row["display_name"]: row
            for row in conn.execute("SELECT display_name, icon_path, icon_source FROM images")
        }
        # Capa pré-existente só podia ter vindo de upload manual: é 'admin'
        # para o seed de capas padrão jamais sobrescrevê-la.
        assert rows["Com capa"]["icon_source"] == "admin"
        assert rows["Sem capa"]["icon_path"] is None
        assert rows["Sem capa"]["icon_source"] is None
    finally:
        conn.close()


def test_init_db_adiciona_tabela_e_coluna_de_agents_md(tmp_path):
    db_path = tmp_path / "legado-agents-md.db"
    conn = connect(db_path)
    try:
        # Banco legado: criado antes da tabela de documentos e da coluna
        # de vínculo existirem.
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
                icon_source TEXT,
                port INTEGER NOT NULL DEFAULT 3000,
                provision_kind TEXT NOT NULL DEFAULT 'pull',
                build_hash TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE (repository, tag)
            );
            """
        )

        conn.execute(
            """INSERT INTO images
                   (display_name, repository, tag, shm_size_mb, mem_limit_mb, cpu_limit)
               VALUES ('Webtop', 'r/teste', 'latest', 1024, 2048, 2.0)"""
        )

        init_db(conn)
        init_db(conn)  # idempotente: rodar de novo não falha nem duplica

        tables = {
            row["name"] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "agent_md_documents" in tables

        columns = {row["name"] for row in conn.execute("PRAGMA table_info(images)")}
        assert "agents_md_id" in columns

        row = conn.execute("SELECT agents_md_id FROM images").fetchone()
        assert row["agents_md_id"] is None  # sem vínculo por padrão
    finally:
        conn.close()


def test_agent_skills_existe_apos_init_db(db_conn):
    columns = {row["name"] for row in db_conn.execute("PRAGMA table_info(agent_skills)")}
    assert columns == {
        "id",
        "display_name",
        "repo_owner",
        "repo_name",
        "subpath",
        "created_at",
        "updated_at",
    }


def test_image_skills_existe_apos_init_db(db_conn):
    columns = {row["name"] for row in db_conn.execute("PRAGMA table_info(image_skills)")}
    assert columns == {"image_id", "skill_id"}


def test_init_db_cria_image_version_em_banco_novo(db_conn):
    imagens = {row["name"] for row in db_conn.execute("PRAGMA table_info(images)")}
    instancias = {row["name"] for row in db_conn.execute("PRAGMA table_info(instances)")}

    assert "image_version" in imagens
    assert "image_version" in instancias

    image_id = insert_image(db_conn)
    row = db_conn.execute("SELECT image_version FROM images WHERE id = ?", (image_id,)).fetchone()
    assert row["image_version"] is None


def test_init_db_adiciona_image_version_a_banco_legado(tmp_path):
    db_path = tmp_path / "legado-image-version.db"
    conn = connect(db_path)
    try:
        # Banco legado: tabelas sem as colunas image_version (antes da
        # funcionalidade de ciclo de atualização existir).
        conn.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                disabled_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
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
                icon_source TEXT,
                port INTEGER NOT NULL DEFAULT 3000,
                provision_kind TEXT NOT NULL DEFAULT 'pull',
                build_hash TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE (repository, tag)
            );
            CREATE TABLE instances (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                image_id INTEGER NOT NULL REFERENCES images(id),
                container_id TEXT,
                container_name TEXT,
                volume_name TEXT NOT NULL,
                inner_user TEXT NOT NULL,
                inner_password TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'starting',
                error_message TEXT,
                mcp_validation_errors TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_seen_at TEXT,
                deleted_at TEXT
            );
            """
        )
        conn.execute(
            """INSERT INTO images
                   (display_name, repository, tag, shm_size_mb, mem_limit_mb, cpu_limit)
               VALUES ('Webtop', 'lscr.io/linuxserver/webtop', 'latest', 1024, 2048, 2.0)"""
        )

        init_db(conn)
        init_db(conn)  # idempotente: rodar de novo não falha nem altera dados

        row = conn.execute(
            "SELECT image_version FROM images WHERE repository = 'lscr.io/linuxserver/webtop'"
        ).fetchone()
        assert row["image_version"] is None
    finally:
        conn.close()


def test_agent_skills_nome_duplicado_e_rejeitado(db_conn):
    db_conn.execute(
        "INSERT INTO agent_skills (display_name, repo_owner, repo_name) VALUES (?, ?, ?)",
        ("Minha skill", "owner", "repo-a"),
    )

    with pytest.raises(Exception):
        db_conn.execute(
            "INSERT INTO agent_skills (display_name, repo_owner, repo_name) VALUES (?, ?, ?)",
            ("Minha skill", "owner", "repo-b"),
        )


def test_agent_skills_repo_e_subpath_duplicados_sao_rejeitados(db_conn):
    db_conn.execute(
        "INSERT INTO agent_skills (display_name, repo_owner, repo_name, subpath) VALUES (?, ?, ?, ?)",
        ("Skill A", "owner", "repo", "onboarding"),
    )

    with pytest.raises(Exception):
        db_conn.execute(
            "INSERT INTO agent_skills (display_name, repo_owner, repo_name, subpath) VALUES (?, ?, ?, ?)",
            ("Skill B", "owner", "repo", "onboarding"),
        )


def test_agent_skills_mesmo_repo_com_subpath_diferente_e_aceito(db_conn):
    db_conn.execute(
        "INSERT INTO agent_skills (display_name, repo_owner, repo_name, subpath) VALUES (?, ?, ?, ?)",
        ("Skill A", "owner", "repo", "onboarding"),
    )
    db_conn.execute(
        "INSERT INTO agent_skills (display_name, repo_owner, repo_name, subpath) VALUES (?, ?, ?, ?)",
        ("Skill B", "owner", "repo", "draft-pr"),
    )

    total = db_conn.execute("SELECT COUNT(*) FROM agent_skills").fetchone()[0]
    assert total == 2


def test_image_skills_vincula_skill_a_imagem_de_build(db_conn):
    image_id = insert_image(db_conn, provision_kind="build")
    skill_id = db_conn.execute(
        "INSERT INTO agent_skills (display_name, repo_owner, repo_name) VALUES (?, ?, ?)",
        ("Minha skill", "owner", "repo"),
    ).lastrowid

    db_conn.execute(
        "INSERT INTO image_skills (image_id, skill_id) VALUES (?, ?)", (image_id, skill_id)
    )

    vinculadas = db_conn.execute(
        "SELECT COUNT(*) FROM image_skills WHERE image_id = ? AND skill_id = ?",
        (image_id, skill_id),
    ).fetchone()[0]
    assert vinculadas == 1


def test_mcp_servers_existe_apos_init_db(db_conn):
    columns = {row["name"] for row in db_conn.execute("PRAGMA table_info(mcp_servers)")}
    assert columns == {
        "id",
        "display_name",
        "transport",
        "command",
        "args_json",
        "url",
        "env_encrypted",
        "headers_encrypted",
        "enabled",
        "created_at",
        "updated_at",
    }


def test_image_mcp_servers_existe_apos_init_db(db_conn):
    columns = {row["name"] for row in db_conn.execute("PRAGMA table_info(image_mcp_servers)")}
    assert columns == {"image_id", "mcp_server_id"}


def test_mcp_servers_nome_duplicado_e_rejeitado(db_conn):
    db_conn.execute(
        "INSERT INTO mcp_servers (display_name, transport, command) VALUES (?, ?, ?)",
        ("Meu MCP", "stdio", "npx"),
    )

    with pytest.raises(Exception):
        db_conn.execute(
            "INSERT INTO mcp_servers (display_name, transport, command) VALUES (?, ?, ?)",
            ("Meu MCP", "stdio", "npx"),
        )


def test_image_mcp_servers_vincula_mcp_a_imagem_de_build(db_conn):
    image_id = insert_image(db_conn, provision_kind="build")
    mcp_id = db_conn.execute(
        "INSERT INTO mcp_servers (display_name, transport, command) VALUES (?, ?, ?)",
        ("Meu MCP", "stdio", "npx"),
    ).lastrowid

    db_conn.execute(
        "INSERT INTO image_mcp_servers (image_id, mcp_server_id) VALUES (?, ?)",
        (image_id, mcp_id),
    )

    vinculados = db_conn.execute(
        "SELECT COUNT(*) FROM image_mcp_servers WHERE image_id = ? AND mcp_server_id = ?",
        (image_id, mcp_id),
    ).fetchone()[0]
    assert vinculados == 1

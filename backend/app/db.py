import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    disabled_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    revoked_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);

CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_groups (
    user_id INTEGER NOT NULL REFERENCES users(id),
    group_id INTEGER NOT NULL REFERENCES groups(id),
    UNIQUE (user_id, group_id)
);

CREATE TABLE IF NOT EXISTS images (
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
    agents_md_id INTEGER REFERENCES agent_md_documents(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (repository, tag)
);

CREATE TABLE IF NOT EXISTS group_images (
    group_id INTEGER NOT NULL REFERENCES groups(id),
    image_id INTEGER NOT NULL REFERENCES images(id),
    UNIQUE (group_id, image_id)
);

CREATE TABLE IF NOT EXISTS instances (
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
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT,
    deleted_at TEXT
);

-- Garante uma unica instancia viva por par (usuario, imagem); exclusoes
-- (deleted_at preenchido) ficam fora do indice e nao bloqueiam uma nova.
CREATE UNIQUE INDEX IF NOT EXISTS uq_instances_user_image_live
    ON instances(user_id, image_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_instances_user_id ON instances(user_id);

-- Histórico de execuções (start->stop) de instâncias, para métricas de uso
-- administrativas. Aditivo: instances.state continua sendo a fonte da
-- verdade do estado atual; esta tabela só registra quando cada ciclo
-- começou/terminou e por quê.
CREATE TABLE IF NOT EXISTS instance_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id TEXT NOT NULL REFERENCES instances(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    image_id INTEGER NOT NULL REFERENCES images(id),
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at TEXT,
    ended_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_instance_runs_open
    ON instance_runs(instance_id) WHERE ended_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_instance_runs_started_at ON instance_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_instance_runs_user_id ON instance_runs(user_id);

-- Identidade SSH por usuário (ver services/ssh_identity.py). Uma linha por
-- usuário: regenerar substitui a linha, não acumula histórico.
CREATE TABLE IF NOT EXISTS ssh_identities (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    public_key TEXT NOT NULL,
    private_key_encrypted BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Biblioteca de documentos AGENTS.md (ver services/agents_md.py): textos
-- nomeados que o administrador vincula às entradas do catálogo para serem
-- injetados nas instâncias como /config/AGENTS.md.
CREATE TABLE IF NOT EXISTS agent_md_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    """Abre a conexão em modo WAL, com busy_timeout e foreign_keys ligados.

    `check_same_thread=False` porque o FastAPI pode resolver a dependência
    que abre a conexão numa thread do seu pool e executar o corpo do
    endpoint na thread do event loop (ou vice-versa), dependendo de o
    endpoint ser `def` ou `async def`. O uso da conexão dentro de uma
    requisição é sempre sequencial — nunca duas threads ao mesmo tempo —
    então relaxar essa trava é seguro aqui.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    _migrate_add_icon_path(conn)
    _migrate_add_icon_source(conn)
    _migrate_add_agents_md_id(conn)
    _migrate_add_image_provisioning_columns(conn)
    _migrate_normalize_last_seen_at(conn)


def _migrate_add_icon_source(conn: sqlite3.Connection) -> None:
    """Adiciona a coluna icon_source e marca capas pré-existentes como admin.

    Capas existentes antes desta coluna só podiam vir de upload manual do
    administrador, então o backfill as marca como 'admin' para que o seed de
    capas padrão jamais as sobrescreva (ver services/image_covers.py).
    """
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(images)")}
    if "icon_source" not in columns:
        conn.execute("ALTER TABLE images ADD COLUMN icon_source TEXT")
    conn.execute(
        "UPDATE images SET icon_source = 'admin'"
        " WHERE icon_path IS NOT NULL AND icon_source IS NULL"
    )


def _migrate_add_icon_path(conn: sqlite3.Connection) -> None:
    """Adiciona a coluna icon_path a bancos criados antes dela existir.

    CREATE TABLE IF NOT EXISTS não altera uma tabela já existente, então um
    banco criado por uma versão anterior do schema precisa desse ALTER
    idempotente para ganhar a coluna nova.
    """
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(images)")}
    if "icon_path" not in columns:
        conn.execute("ALTER TABLE images ADD COLUMN icon_path TEXT")


def _migrate_add_agents_md_id(conn: sqlite3.Connection) -> None:
    """Adiciona a coluna agents_md_id a bancos criados antes dela existir.

    A tabela `agent_md_documents` nasce no CREATE TABLE IF NOT EXISTS; a
    coluna em `images`, sendo referencia (0..1), precisa do ALTER guardado
    por PRAGMA table_info para bancos legados.
    """
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(images)")}
    if "agents_md_id" not in columns:
        conn.execute("ALTER TABLE images ADD COLUMN agents_md_id INTEGER")


def _migrate_add_image_provisioning_columns(conn: sqlite3.Connection) -> None:
    """Adiciona porta, tipo de provisionamento e hash de contexto a `images`.

    Mesmo motivo de `_migrate_add_icon_path`: bancos criados antes dessas
    colunas existirem não são alterados por `CREATE TABLE IF NOT EXISTS`.
    Os defaults preservam o comportamento anterior: porta 3000 (a que o
    proxy já assumia) e entradas existentes como provisionadas por pull.
    """
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(images)")}
    if "port" not in columns:
        conn.execute("ALTER TABLE images ADD COLUMN port INTEGER NOT NULL DEFAULT 3000")
    if "provision_kind" not in columns:
        conn.execute(
            "ALTER TABLE images ADD COLUMN provision_kind TEXT NOT NULL DEFAULT 'pull'"
        )
    if "build_hash" not in columns:
        conn.execute("ALTER TABLE images ADD COLUMN build_hash TEXT")


def _migrate_normalize_last_seen_at(conn: sqlite3.Connection) -> None:
    """Remove o sufixo de fuso de `last_seen_at` gravado antes da correção.

    Até essa correção, `last_seen_at` era gravado via `isoformat()` de um
    datetime ciente de fuso ("...+00:00"), diferente de toda outra coluna
    de timestamp do banco (gravadas via `datetime('now')` do SQLite, sem
    sufixo) — isso quebrava o parsing em `usage_metrics` quando esse valor
    chegava a `instance_runs.started_at` via `backfill_open_runs`. O
    `LIKE` só casa com o formato antigo, então rodar de novo sobre um
    banco já normalizado não faz nada.
    """
    conn.execute(
        """UPDATE instances SET last_seen_at = substr(last_seen_at, 1, 19)
           WHERE last_seen_at LIKE '____-__-__ __:__:__+%'"""
    )

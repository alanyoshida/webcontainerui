"""Camada de persistência portável: SQLite em dev, PostgreSQL em produção.

O schema vive num único `MetaData` e é criado com `create_all`, que compila
para cada dialeto; as migrações idempotentes usam o `Inspector` do
SQLAlchemy em vez de `PRAGMA table_info`. Ver change
`postgres-for-production`.

As conexões entregues à aplicação são `DbConnection`, um wrapper fino sobre
`sqlalchemy.engine.Connection` que preserva o estilo dos services: SQL em
texto com parâmetros nomeados (`:nome`), `fetchone`/`fetchall`/iteração,
acesso à linha por nome (`row["coluna"]`) e `lastrowid` após INSERT — nos
dois motores.
"""

import sqlite3
from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.engine import Connection, Engine, URL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

metadata = sa.MetaData()


class now_second(FunctionElement):
    """`CURRENT_TIMESTAMP` com precisão de segundo nos dois motores.

    O PostgreSQL grava microssegundos em `now()`; como o restante do código
    bind timestamps formatados em segundos, defaults com fração invertiam a
    ordem dentro do mesmo segundo (duração negativa). SQLite já é segundos."""

    type = sa.DateTime()
    inherit_cache = True


@compiles(now_second, "postgresql")
def _now_second_pg(element, compiler, **kw):  # noqa: N802
    return "date_trunc('second', now())"


@compiles(now_second, "sqlite")
def _now_second_sqlite(element, compiler, **kw):  # noqa: N802
    return "CURRENT_TIMESTAMP"

# Violação de unicidade/FK: SQLAlchemy embrulha o erro do driver
# (`sqlalchemy.exc.IntegrityError`); conexões `sqlite3` cruas usadas por
# fixtures de teste expõem o erro do DBAPI direto. Os services aceitam os
# dois para poderem rodar contra ambos os tipos de conexão.
INTEGRITY_ERRORS = (IntegrityError, sqlite3.IntegrityError)


def _id() -> sa.Column:
    return sa.Column("id", sa.Integer, primary_key=True)


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime, nullable=False, server_default=now_second())


def _updated_at() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime)


users = sa.Table(
    "users",
    metadata,
    _id(),
    sa.Column("email", sa.String, nullable=False, unique=True),
    sa.Column("password_hash", sa.String, nullable=False),
    sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("disabled_at", sa.DateTime),
    _created_at(),
)

sessions = sa.Table(
    "sessions",
    metadata,
    sa.Column("token_hash", sa.String, primary_key=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
    _created_at(),
    sa.Column("expires_at", sa.DateTime, nullable=False),
    sa.Column("revoked_at", sa.DateTime),
)
sa.Index("idx_sessions_user_id", sessions.c.user_id)

groups = sa.Table(
    "groups",
    metadata,
    _id(),
    sa.Column("name", sa.String, nullable=False, unique=True),
    _created_at(),
)

user_groups = sa.Table(
    "user_groups",
    metadata,
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
    sa.Column("group_id", sa.Integer, sa.ForeignKey("groups.id"), nullable=False),
    sa.UniqueConstraint("user_id", "group_id"),
)

agent_md_documents = sa.Table(
    "agent_md_documents",
    metadata,
    _id(),
    sa.Column("name", sa.String, nullable=False, unique=True),
    sa.Column("content", sa.Text, nullable=False),
    _created_at(),
    _updated_at(),
)

images = sa.Table(
    "images",
    metadata,
    _id(),
    sa.Column("display_name", sa.String, nullable=False),
    sa.Column("repository", sa.String, nullable=False),
    sa.Column("tag", sa.String, nullable=False),
    sa.Column("shm_size_mb", sa.Integer, nullable=False),
    sa.Column("mem_limit_mb", sa.Integer, nullable=False),
    sa.Column("cpu_limit", sa.Float, nullable=False),
    sa.Column("harden_desktop", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("pull_state", sa.String, nullable=False, server_default="pulling"),
    sa.Column("pull_progress", sa.Text),
    sa.Column("pull_error", sa.Text),
    sa.Column("icon_path", sa.Text),
    sa.Column("icon_source", sa.Text),
    sa.Column("port", sa.Integer, nullable=False, server_default=text("3000")),
    sa.Column("provision_kind", sa.String, nullable=False, server_default="pull"),
    sa.Column("build_hash", sa.String),
    # Versão legível da imagem baixada (label build_version das imagens
    # LinuxServer; digest curto na ausência dele). NULL = ainda não capturada.
    sa.Column("image_version", sa.String),
    sa.Column("agents_md_id", sa.Integer, sa.ForeignKey("agent_md_documents.id")),
    _created_at(),
    sa.UniqueConstraint("repository", "tag"),
)

group_images = sa.Table(
    "group_images",
    metadata,
    sa.Column("group_id", sa.Integer, sa.ForeignKey("groups.id"), nullable=False),
    sa.Column("image_id", sa.Integer, sa.ForeignKey("images.id"), nullable=False),
    sa.UniqueConstraint("group_id", "image_id"),
)

instances = sa.Table(
    "instances",
    metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
    sa.Column("image_id", sa.Integer, sa.ForeignKey("images.id"), nullable=False),
    sa.Column("container_id", sa.String),
    sa.Column("container_name", sa.String),
    sa.Column("volume_name", sa.String, nullable=False),
    sa.Column("inner_user", sa.String, nullable=False),
    sa.Column("inner_password", sa.String, nullable=False),
    sa.Column("state", sa.String, nullable=False, server_default="starting"),
    sa.Column("error_message", sa.Text),
    # Quebra de contrato do config de MCP detectada na criação (JSON de
    # mensagens por MCP/campo; NULL = sem quebra). Consultável pelo admin,
    # não impede a instância de ficar pronta (ver mcp_servers.py).
    sa.Column("mcp_validation_errors", sa.Text),
    # Versão da imagem no momento da criação/recriação do container
    # (snapshot do catálogo; NULL = criada antes do registro existir).
    sa.Column("image_version", sa.String),
    _created_at(),
    sa.Column("last_seen_at", sa.DateTime),
    sa.Column("deleted_at", sa.DateTime),
)
# Garante uma unica instancia viva por par (usuario, imagem); exclusoes
# (deleted_at preenchido) ficam fora do indice e nao bloqueiam uma nova.
sa.Index(
    "uq_instances_user_image_live",
    instances.c.user_id,
    instances.c.image_id,
    unique=True,
    sqlite_where=instances.c.deleted_at.is_(None),
    postgresql_where=instances.c.deleted_at.is_(None),
)
sa.Index("idx_instances_user_id", instances.c.user_id)

# Histórico de execuções (start->stop) de instâncias, para métricas de uso
# administrativas. Aditivo: instances.state continua sendo a fonte da
# verdade do estado atual; esta tabela só registra quando cada ciclo
# começou/terminou e por quê.
instance_runs = sa.Table(
    "instance_runs",
    metadata,
    _id(),
    sa.Column("instance_id", sa.String, sa.ForeignKey("instances.id"), nullable=False),
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
    sa.Column("image_id", sa.Integer, sa.ForeignKey("images.id"), nullable=False),
    sa.Column("started_at", sa.DateTime, nullable=False, server_default=now_second()),
    sa.Column("ended_at", sa.DateTime),
    sa.Column("ended_reason", sa.String),
)
sa.Index(
    "idx_instance_runs_open",
    instance_runs.c.instance_id,
    sqlite_where=instance_runs.c.ended_at.is_(None),
    postgresql_where=instance_runs.c.ended_at.is_(None),
)
sa.Index("idx_instance_runs_started_at", instance_runs.c.started_at)
sa.Index("idx_instance_runs_user_id", instance_runs.c.user_id)

# Identidade SSH por usuário (ver services/ssh_identity.py). Uma linha por
# usuário: regenerar substitui a linha, não acumula histórico.
ssh_identities = sa.Table(
    "ssh_identities",
    metadata,
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
    sa.Column("public_key", sa.Text, nullable=False),
    sa.Column("private_key_encrypted", sa.LargeBinary, nullable=False),
    _created_at(),
)

# Biblioteca de documentos AGENTS.md (ver services/agents_md.py): textos
# nomeados que o administrador vincula às entradas do catálogo para serem
# injetados nas instâncias como /config/AGENTS.md.
# (tabela definida acima de `images` por causa da referência)

# Biblioteca de skills (ver services/agent_skills.py): referências a
# repositórios do GitHub no formato distribuído pelo skills.sh, que o
# administrador vincula a imagens de agente de código para serem
# instaladas no build de cada imagem. `subpath` é '' (não NULL) quando o
# repositório não empacota várias skills, para que a UNIQUE abaixo
# funcione — um NULL seria tratado como distinto em ambos os motores.
agent_skills = sa.Table(
    "agent_skills",
    metadata,
    _id(),
    sa.Column("display_name", sa.String, nullable=False, unique=True),
    sa.Column("repo_owner", sa.String, nullable=False),
    sa.Column("repo_name", sa.String, nullable=False),
    sa.Column("subpath", sa.String, nullable=False, server_default=""),
    _created_at(),
    _updated_at(),
    sa.UniqueConstraint("repo_owner", "repo_name", "subpath"),
)

# Vínculo N:N entre skills e imagens de agente de código (só imagens com
# provision_kind='build' recebem vínculo — ver agent_skills.link_skill).
image_skills = sa.Table(
    "image_skills",
    metadata,
    sa.Column("image_id", sa.Integer, sa.ForeignKey("images.id"), nullable=False),
    sa.Column("skill_id", sa.Integer, sa.ForeignKey("agent_skills.id"), nullable=False),
    sa.PrimaryKeyConstraint("image_id", "skill_id"),
)

# Biblioteca de servidores MCP (ver services/mcp_servers.py): cadastro
# genérico (transporte stdio ou http/sse) que o administrador vincula a
# imagens de agente de código. `env_encrypted`/`headers_encrypted` guardam
# os dicionários de variável de ambiente/header cifrados com a mesma
# infraestrutura Fernet da identidade SSH (nunca em claro no banco) — só
# um dos dois é usado, conforme `transport`.
mcp_servers = sa.Table(
    "mcp_servers",
    metadata,
    _id(),
    sa.Column("display_name", sa.String, nullable=False, unique=True),
    sa.Column("transport", sa.String, nullable=False),
    sa.Column("command", sa.Text),
    sa.Column("args_json", sa.Text),
    sa.Column("url", sa.Text),
    sa.Column("env_encrypted", sa.LargeBinary),
    sa.Column("headers_encrypted", sa.LargeBinary),
    sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
    _created_at(),
    _updated_at(),
)

# Vínculo N:N entre servidores MCP e imagens de agente de código (mesma
# regra de `image_skills`: só imagens com provision_kind='build').
image_mcp_servers = sa.Table(
    "image_mcp_servers",
    metadata,
    sa.Column("image_id", sa.Integer, sa.ForeignKey("images.id"), nullable=False),
    sa.Column("mcp_server_id", sa.Integer, sa.ForeignKey("mcp_servers.id"), nullable=False),
    sa.PrimaryKeyConstraint("image_id", "mcp_server_id"),
)


_TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def as_datetime(value: "datetime | str") -> datetime:
    """Normaliza um timestamp lido como `datetime` (Postgres) ou `str`
    (SQLite, onde consultas por `text()` não têm metadados de coluna)."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo is not None else value
    try:
        return datetime.strptime(value, _TS_FORMAT)
    except ValueError:
        # Timestamps legados com offset (ex.: `expires_at` antigo).
        return datetime.fromisoformat(value).replace(tzinfo=None)


def format_ts(value: "datetime | str | None") -> str | None:
    """Serializa um timestamp no formato do banco/API (`YYYY-MM-DD HH:MM:SS`)."""
    if value is None:
        return None
    return as_datetime(value).strftime(_TS_FORMAT)


_TS_PARAM_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


def ts_param(value: "datetime | str") -> str:
    """Timestamp para bind em SQL, com microssegundos.

    Manter a fração de segundo evita inversão de ordem com os defaults do
    PostgreSQL (`now()` grava microssegundos): um `ended_at` truncado em
    segundos poderia ficar antes do `started_at` do mesmo segundo."""
    return as_datetime(value).strftime(_TS_PARAM_FORMAT)


def utcnow() -> datetime:
    """Agora em UTC, sem tzinfo — a convenção de timestamp do banco.

    Manter `naive` preserva o formato que o SQLite já gravava e evita
    ambiguidade de fuso nos dois motores (ver design.md D3)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sqlite_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = sa.create_engine(
        URL.create("sqlite", database=str(db_path)),
        isolation_level="AUTOCOMMIT",
        connect_args={"check_same_thread": False},
    )

    @sa.event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    return engine


def make_engine(database_url: str | None = None, db_path: Path | None = None) -> Engine:
    """Engine do banco configurado.

    Com `database_url` (produção) usa o PostgreSQL apontado; sem ela, o
    SQLite em `db_path` (dev/testes). AUTOCOMMIT reproduz a semântica
    anterior (`sqlite3` com `isolation_level=None`): cada statement vale
    imediatamente, sem transação explícita nos services."""
    if database_url:
        return sa.create_engine(database_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    return _sqlite_engine(Path(db_path or "webcontainerui.db"))


def engine_for_path(db_path: Path) -> Engine:
    """Engine SQLite para um caminho (útil em testes)."""
    return _sqlite_engine(db_path)


class DbResult:
    """Resultado de `DbConnection.execute`, com linhas acessíveis por nome."""

    __slots__ = ("_result",)

    def __init__(self, result) -> None:
        self._result = result

    def fetchone(self):
        return self._result.mappings().first()

    def fetchall(self):
        return self._result.mappings().all()

    def __iter__(self):
        return iter(self._result.mappings())

    @property
    def lastrowid(self):
        """Rowid do DBAPI. Os INSERTs que precisam do id usam `RETURNING id`
        (portável); esta propriedade existe só para SQLite/depuração."""
        return self._result.lastrowid

    @property
    def rowcount(self) -> int:
        return self._result.rowcount


class DbConnection:
    """Wrapper fino sobre `Connection` com a API usada pelos services."""

    __slots__ = ("_conn",)

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def execute(
        self, sql: str, params: Mapping[str, Any] | None = None
    ) -> DbResult:
        return DbResult(self._conn.execute(text(sql), params or {}))

    def close(self) -> None:
        self._conn.close()

    def __getattr__(self, name: str):
        return getattr(self._conn, name)


def connect(engine: Engine) -> DbConnection:
    """Abre uma conexão de vida curta a partir do engine."""
    return DbConnection(engine.connect())


def init_db(target: Engine | sqlite3.Connection) -> None:
    """Cria o schema e aplica as migrações idempotentes.

    Aceita um `Engine` (produção/dev) ou uma `sqlite3.Connection` crua —
    esta última só para fixtures de teste que abrem o arquivo direto."""
    if isinstance(target, Engine):
        engine = target
    else:
        path = Path(target.execute("PRAGMA database_list").fetchone()[2])
        engine = engine_for_path(path)
    with engine.connect() as conn:
        metadata.create_all(conn)
        _migrate_add_icon_path(conn)
        _migrate_add_icon_source(conn)
        _migrate_add_agents_md_id(conn)
        _migrate_add_image_provisioning_columns(conn)
        _migrate_add_instance_mcp_validation_errors(conn)
        _migrate_add_image_version_columns(conn)
        _migrate_normalize_last_seen_at(conn)
        _migrate_normalize_session_timestamps(conn)


def _column_names(conn: Connection, table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns(table)}


def _add_column(conn: Connection, table: str, column: str, ddl: str) -> None:
    if column not in _column_names(conn, table):
        conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _migrate_add_icon_path(conn: Connection) -> None:
    """Adiciona a coluna icon_path a bancos criados antes dela existir.

    `create_all` não altera uma tabela já existente, então um banco criado
    por uma versão anterior do schema precisa desse ALTER idempotente."""
    _add_column(conn, "images", "icon_path", "icon_path TEXT")


def _migrate_add_icon_source(conn: Connection) -> None:
    """Adiciona a coluna icon_source e marca capas pré-existentes como admin.

    Capas existentes antes desta coluna só podiam vir de upload manual do
    administrador, então o backfill as marca como 'admin' para que o seed de
    capas padrão jamais as sobrescreva (ver services/image_covers.py)."""
    _add_column(conn, "images", "icon_source", "icon_source TEXT")
    conn.execute(
        text(
            "UPDATE images SET icon_source = 'admin'"
            " WHERE icon_path IS NOT NULL AND icon_source IS NULL"
        )
    )


def _migrate_add_agents_md_id(conn: Connection) -> None:
    """Adiciona a coluna agents_md_id a bancos criados antes dela existir."""
    _add_column(conn, "images", "agents_md_id", "agents_md_id INTEGER")


def _migrate_add_image_provisioning_columns(conn: Connection) -> None:
    """Adiciona porta, tipo de provisionamento e hash de contexto a `images`.

    Os defaults preservam o comportamento anterior: porta 3000 (a que o
    proxy já assumia) e entradas existentes como provisionadas por pull."""
    _add_column(
        conn, "images", "port", "port INTEGER NOT NULL DEFAULT 3000"
    )
    _add_column(
        conn,
        "images",
        "provision_kind",
        "provision_kind TEXT NOT NULL DEFAULT 'pull'",
    )
    _add_column(conn, "images", "build_hash", "build_hash TEXT")


def _migrate_add_instance_mcp_validation_errors(conn: Connection) -> None:
    """Adiciona a coluna `mcp_validation_errors` a `instances`.

    NULL significa "sem quebra de contrato registrada"."""
    _add_column(conn, "instances", "mcp_validation_errors", "mcp_validation_errors TEXT")


def _migrate_add_image_version_columns(conn: Connection) -> None:
    """Adiciona `image_version` a `images` e a `instances`.

    NULL significa "versão desconhecida" tanto para a entrada do catálogo
    (ainda não capturada) quanto para a instância (criada antes do registro
    existir)."""
    _add_column(conn, "images", "image_version", "image_version TEXT")
    _add_column(conn, "instances", "image_version", "image_version TEXT")


def _migrate_normalize_last_seen_at(conn: Connection) -> None:
    """Remove o sufixo de fuso de `last_seen_at` gravado antes da correção.

    Correção histórica de dados do SQLite (bancos legados): até certa
    versão, `last_seen_at` era gravado com "+00:00", diferente das demais
    colunas. O `LIKE` só casa com o formato antigo e é no-op num banco já
    normalizado. Em PostgreSQL o banco nasce novo e a coluna é `timestamp`
    — `substr` sobre timestamp não existe, então nada a fazer."""
    if conn.dialect.name != "sqlite":
        return
    conn.exec_driver_sql(
        """UPDATE instances SET last_seen_at = substr(last_seen_at, 1, 19)
           WHERE last_seen_at LIKE '____-__-__ __:__:__+%'"""
    )


def _migrate_normalize_session_timestamps(conn: Connection) -> None:
    """Remove o sufixo de fuso de `expires_at`/`revoked_at` legados.

    Versões anteriores gravavam as datas da sessão via `isoformat()` de um
    datetime ciente de fuso ("...+00:00"), enquanto as demais colunas usam
    o formato sem offset. A leitura já tolera os dois (`as_datetime`), mas
    normalizar mantém comparações e ordenações consistentes. Só no SQLite:
    o PostgreSQL nasce novo com colunas `timestamp`."""
    if conn.dialect.name != "sqlite":
        return
    conn.exec_driver_sql(
        """UPDATE sessions SET expires_at = substr(expires_at, 1, 19)
           WHERE expires_at LIKE '____-__-__ __:__:__+%'"""
    )
    conn.exec_driver_sql(
        """UPDATE sessions SET revoked_at = substr(revoked_at, 1, 19)
           WHERE revoked_at LIKE '____-__-__ __:__:__+%'"""
    )


def sqlite3_connection(db_path: Path) -> sqlite3.Connection:
    """Conexão `sqlite3` crua, para fixtures de teste que semeiam direto.

    A aplicação não usa isto; os testes de API escrevem no mesmo arquivo
    SQLite que o engine da app usa."""
    conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

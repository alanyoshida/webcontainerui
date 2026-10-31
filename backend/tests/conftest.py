import sqlite3
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect, init_db
from app.main import create_app
from app.runtime.fake import FakeContainerRuntime
from app.services.passwords import hash_password


@pytest.fixture
def db_conn():
    """Conexão SQLite num arquivo temporário, com schema aplicado.

    Cada teste recebe um banco próprio e vazio: o arquivo é criado sob um
    diretório temporário isolado e removido ao final, então nada escrito
    por um teste é visível ao próximo.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "webcontainerui.db"
        conn = connect(db_path)
        init_db(conn)
        try:
            yield conn
        finally:
            conn.close()


def insert_user(conn: sqlite3.Connection, email: str = "user@exemplo.test") -> int:
    cur = conn.execute(
        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
        (email, "hash"),
    )
    return cur.lastrowid


def insert_image(
    conn: sqlite3.Connection,
    repository: str = "lscr.io/linuxserver/webtop",
    tag: str = "latest",
    *,
    pull_state: str = "ready",
    enabled: bool = True,
    port: int = 3000,
    provision_kind: str = "pull",
    build_hash: str | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO images
               (display_name, repository, tag, shm_size_mb, mem_limit_mb, cpu_limit,
                pull_state, enabled, port, provision_kind, build_hash)
           VALUES (?, ?, ?, 1024, 2048, 2.0, ?, ?, ?, ?, ?)""",
        ("Webtop", repository, tag, pull_state, int(enabled), port, provision_kind, build_hash),
    )
    return cur.lastrowid


def insert_instance(
    conn: sqlite3.Connection,
    user_id: int,
    image_id: int,
    *,
    instance_id: str | None = None,
    state: str = "running",
) -> str:
    import uuid

    instance_id = instance_id or str(uuid.uuid4())
    conn.execute(
        """INSERT INTO instances
               (id, user_id, image_id, volume_name, inner_user, inner_password, state)
           VALUES (?, ?, ?, 'vol-1', 'u', 'p', ?)""",
        (instance_id, user_id, image_id, state),
    )
    return instance_id


def insert_run(
    conn: sqlite3.Connection,
    instance_id: str,
    user_id: int,
    image_id: int,
    started_at: str,
    ended_at: str | None = None,
    ended_reason: str | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO instance_runs (instance_id, user_id, image_id, started_at, ended_at, ended_reason)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (instance_id, user_id, image_id, started_at, ended_at, ended_reason),
    )
    return cur.lastrowid


def insert_group(conn: sqlite3.Connection, name: str = "grupo") -> int:
    cur = conn.execute("INSERT INTO groups (name) VALUES (?)", (name,))
    return cur.lastrowid


def add_user_to_group(conn: sqlite3.Connection, user_id: int, group_id: int) -> None:
    conn.execute("INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)", (user_id, group_id))


def grant_image_to_group(conn: sqlite3.Connection, group_id: int, image_id: int) -> None:
    conn.execute("INSERT INTO group_images (group_id, image_id) VALUES (?, ?)", (group_id, image_id))


@pytest.fixture
def app_settings(tmp_path):
    return Settings(db_path=tmp_path / "test.db", uploads_dir=tmp_path / "uploads")


@pytest.fixture
def fake_runtime():
    return FakeContainerRuntime()


@pytest.fixture
def client(app_settings, fake_runtime):
    """Cliente HTTP sobre a aplicação real, via ASGITransport (camada de API de D7).

    `TestClient` do Starlette é a própria `httpx.ASGITransport` por baixo;
    o uso em bloco `with` dispara o `lifespan`, que aplica o schema no
    banco temporário de `app_settings`. O runtime de containers é o falso
    de `app/runtime/fake.py`: nenhum teste de API depende de Docker.
    """
    app = create_app(app_settings, runtime=fake_runtime)
    with TestClient(app, base_url="http://testserver") as c:
        yield c


@pytest.fixture
def https_client(app_settings, fake_runtime):
    app = create_app(app_settings, runtime=fake_runtime)
    with TestClient(app, base_url="https://testserver") as c:
        yield c


@pytest.fixture
def fake_backend():
    """Servidor real (uvicorn, em thread própria) que faz o papel do
    container nos testes do proxy de sessão. Ver `tests/fake_backend.py`."""
    from .fake_backend import FakeBackendServer

    server = FakeBackendServer()
    port = server.start()
    try:
        yield port
    finally:
        server.stop()


@pytest.fixture
def proxy_client(app_settings, fake_runtime, fake_backend):
    """Como `client`, mas com o proxy de sessão resolvendo qualquer
    instância para o `fake_backend` em vez da rede Docker real."""
    port = fake_backend

    def resolver(row):
        return f"http://127.0.0.1:{port}"

    app = create_app(app_settings, runtime=fake_runtime, backend_resolver=resolver)
    with TestClient(app, base_url="http://testserver") as c:
        yield c


@pytest.fixture
def seed_user(client, app_settings):
    """Insere um usuário direto no banco da aplicação já inicializada.

    Depende de `client` apenas para garantir, pela ordem de fixtures, que
    o schema já foi aplicado pelo `lifespan` antes da inserção.
    """

    def _seed(email: str, password: str, *, is_admin: bool = False, disabled: bool = False) -> int:
        conn = connect(app_settings.db_path)
        try:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, is_admin, disabled_at) VALUES (?, ?, ?, ?)",
                (
                    email,
                    hash_password(password),
                    int(is_admin),
                    "2024-01-01 00:00:00" if disabled else None,
                ),
            )
            return cur.lastrowid
        finally:
            conn.close()

    return _seed

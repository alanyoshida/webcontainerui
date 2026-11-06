"""E2E do plano de dados externo (change external-stream-proxy).

Opt-in (`pytest -m e2e`): sobe um Caddy real em container e um portal real
em uvicorn, provando que (1) o caminho pelas rotas publicadas entrega a
sessão com a credencial injetada e (2) sem o portal no ar nada é
encaminhado ao container. Não precisa de imagem webtop — o "container" é o
`FakeBackendServer` dos testes de proxy.

O teste do caminho in-process (dev, sem Caddy) usa o mesmo portal e o mesmo
backend, só que com a resolução do proxy interno.
"""

import socket
import subprocess
import threading
import time
import uuid

import httpx
import pytest
import uvicorn

from app.config import Settings
from app.db import engine_for_path, init_db, sqlite3_connection
from app.main import create_app
from app.runtime.fake import FakeContainerRuntime
from app.services.passwords import hash_password

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image
from .fake_backend import app as fake_backend_app

pytestmark = pytest.mark.e2e

SECRET = "segredo-e2e-do-plano-de-dados"
PASSWORD = "senha-usuario-123"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve(app, port: int, host: str = "127.0.0.1") -> httpx.Client:
    # No teste com Caddy o portal precisa aceitar conexões do container
    # (host-gateway do Docker), por isso é possível escutar em 0.0.0.0.
    server = uvicorn.Server(
        uvicorn.Config(app, host=host, port=port, log_level="warning", lifespan="on")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            httpx.get(f"{base}/health", timeout=1)
            return httpx.Client(base_url=base, timeout=10), server, thread
        except httpx.HTTPError:
            time.sleep(0.05)
    raise RuntimeError("portal de teste não subiu")


def _wait_port(port: int, deadline_seconds: float = 15.0) -> None:
    deadline = time.time() + deadline_seconds
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(f"porta {port} não abriu")


def _seed_running_instance(settings: Settings, backend_port: int, email: str) -> tuple[str, str]:
    """Cria usuário, imagem e instância `running` direto no banco.

    Feito depois do startup do portal para a reconciliação não tratar a
    instância como morta (o runtime falso não tem esse container)."""
    conn = sqlite3_connection(settings.db_path)
    try:
        conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, hash_password(PASSWORD)),
        )
        user_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()["id"]
        image_id = insert_image(conn, repository=f"repo-{email}", port=3000)
        group_id = insert_group(conn, name=f"grupo-{email}")
        add_user_to_group(conn, user_id, group_id)
        grant_image_to_group(conn, group_id, image_id)
        instance_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO instances
                   (id, user_id, image_id, volume_name, inner_user, inner_password,
                    state, container_id, container_name)
               VALUES (?, ?, ?, 'vol-e2e', 'u-e2e', 'p-e2e', 'running', 'fake-e2e', ?)""",
            (instance_id, user_id, image_id, f"wcui-{instance_id}"),
        )
    finally:
        conn.close()
    return instance_id, f"http://127.0.0.1:{backend_port}"


def _login(client: httpx.Client, email: str) -> str:
    resp = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200
    return resp.cookies["wcui_session"]


@pytest.fixture
def backend():
    # Escuta em 0.0.0.0: no teste com Caddy o "container" é alcançado pelo
    # host-gateway do Docker, não por 127.0.0.1.
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            fake_backend_app, host="0.0.0.0", port=port, log_level="warning", lifespan="off"
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _wait_port(port)
    try:
        yield port
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def test_sessao_funciona_pelo_caminho_in_process_no_modo_dev(tmp_path, backend):
    """Sem plano de dados (dev), o próprio portal entrega a sessão."""
    settings = Settings(
        db_path=tmp_path / "dev.db",
        uploads_dir=tmp_path / "uploads",
        data_plane_secret=SECRET,
    )
    app = create_app(
        settings,
        runtime=FakeContainerRuntime(),
        backend_resolver=lambda row: f"http://127.0.0.1:{backend}",
    )
    client, server, thread = _serve(app, _free_port())
    try:
        instance_id, _ = _seed_running_instance(settings, backend, "dev-e2e@exemplo.test")
        token = _login(client, "dev-e2e@exemplo.test")

        resp = client.get(
            f"/i/{instance_id}/echo-headers", cookies={"wcui_session": token}
        )

        assert resp.status_code == 200
        assert resp.json()["authorization"].startswith("Basic ")
    finally:
        client.close()
        server.should_exit = True
        thread.join(timeout=10)


def test_plano_de_dados_entrega_sessao_e_para_sem_o_portal(tmp_path, backend):
    """Caddy real: rota publicada encaminha ao container; portal fora do ar
    faz a autorização falhar fechada, sem nada chegar ao backend."""
    portal_port = _free_port()
    settings = Settings(
        db_path=tmp_path / "plane.db",
        uploads_dir=tmp_path / "uploads",
        data_plane_secret=SECRET,
    )
    app = create_app(settings, runtime=FakeContainerRuntime())
    client, server, thread = _serve(app, portal_port, host="0.0.0.0")
    caddy_name = f"wcui-e2e-caddy-{uuid.uuid4().hex[:8]}"
    caddy_port = _free_port()
    try:
        instance_id, _ = _seed_running_instance(
            settings, backend, "plane-e2e@exemplo.test"
        )
        token = _login(client, "plane-e2e@exemplo.test")

        routes = tmp_path / "routes"
        routes.mkdir()
        (routes / f"{instance_id}.caddy").write_text(
            f"""
handle /i/{instance_id}/* {{
\tforward_auth host.docker.internal:{portal_port} {{
\t\turi /internal/data-plane/authorize
\t\theader_up -Upgrade
\t\theader_up -Connection
\t\theader_up -Sec-WebSocket-Key
\t\theader_up -Sec-WebSocket-Version
\t\theader_up -Sec-WebSocket-Protocol
\t\theader_up -Sec-WebSocket-Extensions
\t\theader_up X-Data-Plane-Secret {{$WCUI_DATA_PLANE_SECRET}}
\t\tcopy_headers Authorization
\t}}
\treverse_proxy host.docker.internal:{backend}
}}
""",
            encoding="utf-8",
        )
        caddyfile = tmp_path / "Caddyfile"
        caddyfile.write_text(
            f"""
{{
\tadmin off
}}
:80 {{
\trespond /internal/* 404
\timport /etc/caddy/caddy-routes/*.caddy
\treverse_proxy host.docker.internal:{portal_port}
}}
""",
            encoding="utf-8",
        )

        subprocess.run(
            [
                "docker", "run", "-d", "--rm", "--name", caddy_name,
                "--add-host=host.docker.internal:host-gateway",
                "-e", f"WCUI_DATA_PLANE_SECRET={SECRET}",
                "-v", f"{caddyfile}:/etc/caddy/Caddyfile:ro",
                "-v", f"{routes}:/etc/caddy/caddy-routes:ro",
                "-p", f"127.0.0.1:{caddy_port}:80",
                "caddy:2-alpine",
            ],
            check=True,
            capture_output=True,
        )
        _wait_port(caddy_port)
        base = f"http://127.0.0.1:{caddy_port}"
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                if httpx.get(f"{base}/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.1)

        # O endpoint interno não é exposto pela borda.
        assert httpx.get(f"{base}/internal/data-plane/authorize", timeout=10).status_code == 404

        aprovada = httpx.get(
            f"{base}/i/{instance_id}/echo-headers",
            cookies={"wcui_session": token},
            timeout=10,
        )
        assert aprovada.status_code == 200, aprovada.text
        assert aprovada.json()["authorization"].startswith("Basic ")

        # O canal persistente também atravessa o plano de dados: o upgrade
        # chega ao backend com o subprotocolo preservado.
        from websockets.sync.client import connect as ws_connect

        with ws_connect(
            f"ws://127.0.0.1:{caddy_port}/i/{instance_id}/ws",
            additional_headers={"Cookie": f"wcui_session={token}"},
            subprotocols=["tty"],
            open_timeout=10,
        ) as ws:
            ws.send("ola")
            assert ws.recv(timeout=10) == "echo:ola"

        # Portal parado: a autorização falha fechada e o backend não é
        # alcançado (a resposta deixa de ser o eco do backend).
        server.should_exit = True
        thread.join(timeout=10)

        recusada = httpx.get(
            f"{base}/i/{instance_id}/echo-headers",
            cookies={"wcui_session": token},
            timeout=10,
        )
        assert recusada.status_code >= 500
        assert "authorization" not in recusada.text
    finally:
        client.close()
        server.should_exit = True
        thread.join(timeout=5)
        subprocess.run(
            ["docker", "rm", "-f", caddy_name], check=False, capture_output=True
        )

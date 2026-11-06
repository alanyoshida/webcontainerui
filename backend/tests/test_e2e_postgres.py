"""Fluxo completo do portal sobre PostgreSQL real (change postgres-for-production).

Opt-in (`pytest -m e2e`): exige Docker. Usa o runtime falso — o que se
verifica aqui é a persistência (bootstrap, login, usuários, ciclo de
instância e métricas) contra o dialeto PostgreSQL, não o Docker da
instância. O runtime real fica coberto pelos e2e existentes no SQLite/dev.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.runtime.fake import FakeContainerRuntime

from .postgres_server import postgres_url  # noqa: F401 - fixture

pytestmark = pytest.mark.e2e

ADMIN_EMAIL = "admin@pg.test"
ADMIN_PASSWORD = "senha-admin-pg-123"
USER_PASSWORD = "senha-do-usuario-123"
_SSH_KEY = "t4mYe5XoHfy1V4ecB-h_xK-fW33T7_5OFhLtckL4kHQ="


def _settings(tmp_path, postgres_url: str, *, uploads: str) -> Settings:
    return Settings(
        database_url=postgres_url,
        db_path=tmp_path / "nao-usado.db",
        uploads_dir=tmp_path / uploads,
        admin_email=ADMIN_EMAIL,
        admin_password=ADMIN_PASSWORD,
        ssh_key_encryption_key=_SSH_KEY,
    )


def _login(client, email: str, password: str):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_fluxo_completo_no_postgres(postgres_url, tmp_path):
    settings = _settings(tmp_path, postgres_url, uploads="uploads-1")
    app = create_app(settings, runtime=FakeContainerRuntime())
    with TestClient(app, base_url="http://testserver") as client:
        login = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        assert login.status_code == 200, login.text
        admin_id = login.json()["id"]

        criado = client.post(
            "/api/admin/users",
            json={"email": "novo@pg.test", "password": USER_PASSWORD},
        )
        assert criado.status_code == 201, criado.text
        assert _login(client, "novo@pg.test", USER_PASSWORD).status_code == 200
        # volta a sessão de administrador para as operações seguintes
        assert _login(client, ADMIN_EMAIL, ADMIN_PASSWORD).status_code == 200

        resposta_imagens = client.get("/api/admin/images")
        assert resposta_imagens.status_code == 200, resposta_imagens.text
        imagens = resposta_imagens.json()
        agente = next(
            i
            for i in imagens
            if i["pull_state"] == "ready" and i["provision_kind"] == "build"
        )

        grupo = client.post("/api/admin/groups", json={"name": "pg-e2e"})
        assert grupo.status_code == 201, grupo.text
        group_id = grupo.json()["id"]
        assert (
            client.post(
                f"/api/admin/groups/{group_id}/members", json={"user_id": admin_id}
            ).status_code
            == 204
        )
        assert (
            client.post(
                f"/api/admin/groups/{group_id}/images",
                json={"image_id": agente["id"]},
            ).status_code
            == 204
        )

        instancia = client.post("/api/instances", json={"image_id": agente["id"]})
        assert instancia.status_code == 201, instancia.text
        assert instancia.json()["state"] == "running"
        instance_id = instancia.json()["id"]
        assert client.post(f"/api/instances/{instance_id}/stop").status_code == 204

        resumo = client.get("/api/admin/usage/summary")
        assert resumo.status_code == 200, resumo.text

        runs = client.get("/api/admin/usage/runs")
        assert runs.status_code == 200, runs.text
        assert runs.json()["total"] >= 1
        run = runs.json()["items"][0]
        # Timestamps voltam serializados no contrato da API, mesmo sendo
        # `datetime` no driver do PostgreSQL (design.md D3).
        assert len(run["started_at"]) == 19
        assert run["duration_seconds"] >= 0


def test_reinicio_sobre_banco_ja_migrado_preserva_dados(postgres_url, tmp_path):
    settings = _settings(tmp_path, postgres_url, uploads="uploads-2")

    app1 = create_app(settings, runtime=FakeContainerRuntime())
    with TestClient(app1, base_url="http://testserver") as client:
        assert _login(client, ADMIN_EMAIL, ADMIN_PASSWORD).status_code == 200
        criado = client.post(
            "/api/admin/users",
            json={"email": "persistido@pg.test", "password": USER_PASSWORD},
        )
        assert criado.status_code == 201, criado.text

    # Segundo processo sobre o mesmo banco: bootstrap idempotente, admin não
    # duplicado e os dados do primeiro boot continuam autenticando.
    app2 = create_app(settings, runtime=FakeContainerRuntime())
    with TestClient(app2, base_url="http://testserver") as client:
        assert _login(client, "persistido@pg.test", USER_PASSWORD).status_code == 200

        admin_login = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        assert admin_login.status_code == 200
        usuarios = client.get("/api/admin/users").json()
        emails = [u["email"] for u in usuarios]
        assert emails.count(ADMIN_EMAIL) == 1
        assert "persistido@pg.test" in emails

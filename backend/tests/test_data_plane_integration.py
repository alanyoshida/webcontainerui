import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect
from app.main import create_app
from app.services import data_plane
from app.services.passwords import hash_password

from .conftest import (
    add_user_to_group,
    grant_image_to_group,
    insert_group,
    insert_image,
)

SECRET = "segredo-do-plano-de-dados-de-teste"
CADDY = "wcui-caddy"
PASSWORD = "senha-usuario-123"


@pytest.fixture
def plane(tmp_path, fake_runtime, fake_backend):
    fake_runtime.register_container(CADDY)
    settings = Settings(
        db_path=tmp_path / "plane.db",
        uploads_dir=tmp_path / "uploads",
        data_plane_secret=SECRET,
        caddy_routes_dir=tmp_path / "routes",
        caddy_container=CADDY,
    )
    app = create_app(settings, runtime=fake_runtime)
    with TestClient(app, base_url="http://testserver") as client:
        yield client, settings, fake_backend


def _create_running_instance(client, settings, email="dono@exemplo.test") -> str:
    conn = connect(settings.db_path)
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
    finally:
        conn.close()
    assert client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD}
    ).status_code == 200
    return client.post("/api/instances", json={"image_id": image_id}).json()["id"]


def _authorize(client, instance_id, secret=SECRET):
    headers = {"X-Forwarded-Uri": f"/i/{instance_id}/app/"}
    if secret is not None:
        headers["X-Data-Plane-Secret"] = secret
    return client.get("/internal/data-plane/authorize", headers=headers)


def test_data_plane_credencial_aprovada_chega_ao_container(plane):
    client, settings, backend_port = plane
    instance_id = _create_running_instance(client, settings)

    decisao = _authorize(client, instance_id)
    assert decisao.status_code == 200
    credencial = decisao.headers["authorization"]

    # O plano de dados encaminha a requisição com o cabeçalho copiado da
    # resposta de autorização; o backend faz o papel do container.
    encaminhada = httpx.get(
        f"http://127.0.0.1:{backend_port}/i/{instance_id}/echo-headers",
        headers={"Authorization": credencial},
        timeout=5,
    )

    corpo = encaminhada.json()
    assert corpo["instance_id"] == instance_id
    assert corpo["authorization"] == credencial
    assert credencial.startswith("Basic ")


def test_data_plane_recusa_sem_aprovacao_nao_emite_credencial(plane):
    client, settings, _ = plane
    instance_id = _create_running_instance(client, settings)

    recusa = _authorize(client, instance_id, secret=None)

    assert recusa.status_code == 401
    assert "authorization" not in recusa.headers


def test_data_plane_rota_publicada_aponta_para_container_na_porta_do_catalogo(plane):
    client, settings, _ = plane
    instance_id = _create_running_instance(client, settings)

    content = data_plane.route_path(settings.caddy_routes_dir, instance_id).read_text(
        encoding="utf-8"
    )

    assert f"handle /i/{instance_id}/*" in content
    assert f"reverse_proxy wcui-{instance_id}:3000" in content

import base64

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import sqlite3_connection
from app.main import create_app
from app.services.passwords import hash_password

from .conftest import (
    add_user_to_group,
    grant_image_to_group,
    insert_group,
    insert_image,
)

SECRET = "segredo-do-plano-de-dados-de-teste"


@pytest.fixture
def dpa(tmp_path, fake_runtime):
    settings = Settings(
        db_path=tmp_path / "data-plane.db",
        uploads_dir=tmp_path / "uploads",
        data_plane_secret=SECRET,
    )
    app = create_app(settings, runtime=fake_runtime)
    with TestClient(app, base_url="http://testserver") as c:
        yield c, settings


def _authorize(client, secret=SECRET, uri=None):
    headers = {}
    if secret is not None:
        headers["X-Data-Plane-Secret"] = secret
    if uri is not None:
        headers["X-Forwarded-Uri"] = uri
    return client.get("/internal/data-plane/authorize", headers=headers)


def _login_as(client, settings, email, password="senha-usuario-123"):
    conn = sqlite3_connection(settings.db_path)
    try:
        conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, hash_password(password)),
        )
    finally:
        conn.close()
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["id"]


def _create_running_instance(client, settings, email) -> str:
    user_id = _login_as(client, settings, email)
    conn = sqlite3_connection(settings.db_path)
    image_id = insert_image(conn, repository=f"repo-{email}")
    group_id = insert_group(conn, name=f"grupo-{email}")
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    return client.post("/api/instances", json={"image_id": image_id}).json()["id"]


def test_data_plane_authorize_sem_segredo_configurado_recusa(tmp_path, fake_runtime):
    settings = Settings(db_path=tmp_path / "a.db", uploads_dir=tmp_path / "u")
    app = create_app(settings, runtime=fake_runtime)
    with TestClient(app, base_url="http://testserver") as c:
        assert _authorize(c, secret="").status_code == 401


def test_data_plane_authorize_segredo_ausente_recusa(dpa):
    client, settings = dpa
    instance_id = _create_running_instance(client, settings, "sem-segredo@exemplo.test")

    assert _authorize(client, secret=None, uri=f"/i/{instance_id}/").status_code == 401


def test_data_plane_authorize_segredo_errado_recusa(dpa):
    client, settings = dpa
    instance_id = _create_running_instance(client, settings, "segredo-errado@exemplo.test")

    assert _authorize(client, secret="outro", uri=f"/i/{instance_id}/").status_code == 401


def test_data_plane_authorize_sem_sessao_recusa(dpa):
    client, settings = dpa
    instance_id = _create_running_instance(client, settings, "anon@exemplo.test")
    client.cookies.clear()

    assert _authorize(client, uri=f"/i/{instance_id}/").status_code == 401


def test_data_plane_authorize_uri_sem_instancia_recusa(dpa):
    client, settings = dpa
    _create_running_instance(client, settings, "sem-uri@exemplo.test")

    assert _authorize(client, uri="/outra/coisa").status_code == 404
    assert _authorize(client).status_code == 404


def test_data_plane_authorize_dono_aprovado_com_credencial(dpa):
    client, settings = dpa
    instance_id = _create_running_instance(client, settings, "dono@exemplo.test")
    conn = sqlite3_connection(settings.db_path)
    row = conn.execute(
        "SELECT inner_user, inner_password FROM instances WHERE id = ?", (instance_id,)
    ).fetchone()
    conn.close()

    resp = _authorize(client, uri=f"/i/{instance_id}/app/")

    assert resp.status_code == 200
    esperado = "Basic " + base64.b64encode(
        f"{row['inner_user']}:{row['inner_password']}".encode()
    ).decode()
    assert resp.headers["authorization"] == esperado


def test_data_plane_authorize_instancia_de_outro_nao_revela_existencia(dpa):
    client, settings = dpa
    instance_id = _create_running_instance(client, settings, "dono-a@exemplo.test")

    with TestClient(client.app, base_url="http://testserver") as outro:
        _login_as(outro, settings, "dono-b@exemplo.test")
        resp_de_outro = _authorize(outro, uri=f"/i/{instance_id}/")
        resp_inexistente = _authorize(
            outro, uri="/i/00000000-0000-0000-0000-000000000000/"
        )

    assert resp_de_outro.status_code == resp_inexistente.status_code == 404
    assert resp_de_outro.json() == resp_inexistente.json()


def test_data_plane_authorize_instancia_parada_recusa(dpa):
    client, settings = dpa
    instance_id = _create_running_instance(client, settings, "parada@exemplo.test")
    client.post(f"/api/instances/{instance_id}/stop")

    assert _authorize(client, uri=f"/i/{instance_id}/").status_code == 409


def test_data_plane_authorize_aprovado_registra_atividade(dpa):
    client, settings = dpa
    instance_id = _create_running_instance(client, settings, "atividade@exemplo.test")

    assert _authorize(client, uri=f"/i/{instance_id}/").status_code == 200

    conn = sqlite3_connection(settings.db_path)
    assert client.app.state.activity_tracker.flush(conn) == 1
    row = conn.execute(
        "SELECT last_seen_at FROM instances WHERE id = ?", (instance_id,)
    ).fetchone()
    conn.close()
    assert row["last_seen_at"] is not None


def test_data_plane_authorize_fora_do_schema_publico(tmp_path, fake_runtime):
    settings = Settings(
        db_path=tmp_path / "schema.db",
        uploads_dir=tmp_path / "uploads",
        data_plane_secret=SECRET,
        docs_enabled=True,
    )
    app = create_app(settings, runtime=fake_runtime)
    with TestClient(app, base_url="http://testserver") as c:
        schema = c.get("/openapi.json").json()

    assert "/internal/data-plane/authorize" not in schema["paths"]


def test_data_plane_authorize_nao_cai_no_catch_all_do_spa(tmp_path, fake_runtime):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    settings = Settings(
        db_path=tmp_path / "spa.db",
        uploads_dir=tmp_path / "uploads",
        data_plane_secret=SECRET,
        frontend_dist=dist,
    )
    app = create_app(settings, runtime=fake_runtime)
    with TestClient(app, base_url="http://testserver") as c:
        resp = c.get("/internal/data-plane/authorize")

    assert resp.status_code == 401
    assert "spa" not in resp.text

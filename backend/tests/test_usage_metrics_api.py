from app.db import connect

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image


def _login_admin(client, seed_user, email="admin@exemplo.test", password="senha-admin-123"):
    seed_user(email, password, is_admin=True)
    client.post("/api/auth/login", json={"email": email, "password": password})


def _login_as(client, seed_user, email, password="senha-usuario-123"):
    seed_user(email, password)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["id"]


def _setup_running_instance(client, seed_user, app_settings, email):
    user_id = _login_as(client, seed_user, email)
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]
    return user_id, image_id, instance_id


def test_usage_endpoints_exigem_admin(client, seed_user):
    seed_user("comum@exemplo.test", "senha-comum-123")
    client.post("/api/auth/login", json={"email": "comum@exemplo.test", "password": "senha-comum-123"})

    assert client.get("/api/admin/usage/live").status_code == 403
    assert client.get("/api/admin/usage/runs").status_code == 403
    assert client.get("/api/admin/usage/summary").status_code == 403


def test_live_retorna_instancias_em_execucao_para_admin(client, seed_user, app_settings):
    from fastapi.testclient import TestClient

    with TestClient(client.app, base_url="http://testserver") as usuario_client:
        user_id, image_id, instance_id = _setup_running_instance(
            usuario_client, seed_user, app_settings, "viva@exemplo.test"
        )

    _login_admin(client, seed_user)
    resp = client.get("/api/admin/usage/live")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["instance_id"] == instance_id
    assert body[0]["user_id"] == user_id
    assert body[0]["image_id"] == image_id
    assert body[0]["duration_seconds"] >= 0


def test_runs_pagina_e_filtra_fora_da_janela_de_30_dias(client, seed_user, app_settings):
    from fastapi.testclient import TestClient

    with TestClient(client.app, base_url="http://testserver") as usuario_client:
        user_id, image_id, instance_id = _setup_running_instance(
            usuario_client, seed_user, app_settings, "runs-api@exemplo.test"
        )
        usuario_client.post(f"/api/instances/{instance_id}/stop")

    # um segundo run, bem fora da janela de 30 dias
    conn = connect(app_settings.db_path)
    conn.execute(
        """INSERT INTO instance_runs (instance_id, user_id, image_id, started_at, ended_at, ended_reason)
           VALUES (?, ?, ?, '2000-01-01 00:00:00', '2000-01-01 01:00:00', 'user_stop')""",
        (instance_id, user_id, image_id),
    )
    conn.close()

    _login_admin(client, seed_user)
    resp = client.get("/api/admin/usage/runs")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["instance_id"] == instance_id
    assert body["items"][0]["ended_reason"] == "user_stop"

    paginado = client.get("/api/admin/usage/runs?limit=0&offset=0").json()
    assert paginado["total"] == 1
    assert paginado["items"] == []


def test_summary_retorna_todas_as_secoes(client, seed_user, app_settings):
    from fastapi.testclient import TestClient

    with TestClient(client.app, base_url="http://testserver") as usuario_client:
        _setup_running_instance(usuario_client, seed_user, app_settings, "summary@exemplo.test")

    _login_admin(client, seed_user)
    resp = client.get("/api/admin/usage/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["by_user"]) == 1
    assert len(body["image_ranking"]) == 1
    assert isinstance(body["by_group"], list)
    assert isinstance(body["reason_breakdown"], list)
    assert len(body["daily_series"]) == 31  # 30 dias + hoje, inclusive nas duas pontas
    assert body["peak_concurrency"] >= 1

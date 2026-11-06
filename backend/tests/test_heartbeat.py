from fastapi.testclient import TestClient

from app.db import connect

from .conftest import (
    add_user_to_group,
    grant_image_to_group,
    insert_group,
    insert_image,
)


def _login_as(client, seed_user, email, password="senha-usuario-123"):
    seed_user(email, password)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["id"]


def _create_running_instance(client, seed_user, app_settings, email) -> str:
    user_id = _login_as(client, seed_user, email)
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn, repository=f"repo-{email}")
    group_id = insert_group(conn, name=f"grupo-{email}")
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    return client.post("/api/instances", json={"image_id": image_id}).json()["id"]


def _flush(client, app_settings) -> int:
    conn = connect(app_settings.db_path)
    try:
        return client.app.state.activity_tracker.flush(conn)
    finally:
        conn.close()


def test_heartbeat_anonimo_e_recusado(client):
    assert client.post("/api/instances/qualquer/heartbeat").status_code == 401


def test_heartbeat_de_instancia_de_outro_usuario_e_404(
    client, seed_user, app_settings
):
    instance_id = _create_running_instance(
        client, seed_user, app_settings, "dono-a@exemplo.test"
    )

    with TestClient(client.app, base_url="http://testserver") as outro:
        _login_as(outro, seed_user, "dono-b@exemplo.test")
        assert outro.post(f"/api/instances/{instance_id}/heartbeat").status_code == 404


def test_heartbeat_toca_a_atividade_da_instancia(client, seed_user, app_settings):
    instance_id = _create_running_instance(
        client, seed_user, app_settings, "heartbeat@exemplo.test"
    )

    assert client.post(f"/api/instances/{instance_id}/heartbeat").status_code == 204
    assert _flush(client, app_settings) == 1

    conn = connect(app_settings.db_path)
    row = conn.execute(
        "SELECT last_seen_at FROM instances WHERE id = ?", (instance_id,)
    ).fetchone()
    conn.close()
    assert row["last_seen_at"] is not None


def test_heartbeat_e_limitado_por_janela(client, seed_user, app_settings):
    instance_id = _create_running_instance(
        client, seed_user, app_settings, "throttle@exemplo.test"
    )

    assert client.post(f"/api/instances/{instance_id}/heartbeat").status_code == 204
    assert _flush(client, app_settings) == 1  # primeiro toque registrado

    assert client.post(f"/api/instances/{instance_id}/heartbeat").status_code == 204
    assert _flush(client, app_settings) == 0  # segundo, dentro da janela, ignorado


def test_heartbeat_de_instancia_parada_nao_registra_atividade(
    client, seed_user, app_settings
):
    instance_id = _create_running_instance(
        client, seed_user, app_settings, "heartbeat-parada@exemplo.test"
    )
    client.post(f"/api/instances/{instance_id}/stop")

    assert client.post(f"/api/instances/{instance_id}/heartbeat").status_code == 204
    assert _flush(client, app_settings) == 0

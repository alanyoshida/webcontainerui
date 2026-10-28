from app.db import connect
from app.runtime.protocol import ContainerState

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image


def _login_as(client, seed_user, email, password="senha-usuario-123"):
    seed_user(email, password)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["id"]


def test_iniciar_instancia_parada_religa_o_mesmo_container(client, seed_user, app_settings, fake_runtime):
    import asyncio

    user_id = _login_as(client, seed_user, "reiniciar@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    primeira = client.post("/api/instances", json={"image_id": image_id}).json()
    container_id_original = fake_runtime._containers and next(iter(fake_runtime._containers))
    client.post(f"/api/instances/{primeira['id']}/stop")

    segunda = client.post("/api/instances", json={"image_id": image_id})

    assert segunda.status_code == 201
    assert segunda.json()["id"] == primeira["id"]  # mesma instância, religada
    assert segunda.json()["state"] == "running"
    assert asyncio.run(fake_runtime.inspect_container(container_id_original)) == ContainerState.RUNNING


def test_iniciar_apos_container_removido_por_fora_recria_preservando_volume(
    client, seed_user, app_settings, fake_runtime
):
    import asyncio

    user_id = _login_as(client, seed_user, "recriar@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    primeira = client.post("/api/instances", json={"image_id": image_id}).json()
    conn = connect(app_settings.db_path)
    volume_name = conn.execute(
        "SELECT volume_name, container_id FROM instances WHERE id = ?", (primeira["id"],)
    ).fetchone()
    container_id_original, volume_name = volume_name["container_id"], volume_name["volume_name"]
    conn.close()

    client.post(f"/api/instances/{primeira['id']}/stop")
    asyncio.run(fake_runtime.remove_container(container_id_original))  # removido por fora

    segunda = client.post("/api/instances", json={"image_id": image_id})

    assert segunda.status_code == 201
    assert segunda.json()["id"] == primeira["id"]
    assert segunda.json()["state"] == "running"
    conn = connect(app_settings.db_path)
    row = conn.execute(
        "SELECT container_id, volume_name FROM instances WHERE id = ?", (primeira["id"],)
    ).fetchone()
    conn.close()
    assert row["container_id"] != container_id_original  # container novo
    assert row["volume_name"] == volume_name  # mesmo volume: dados preservados

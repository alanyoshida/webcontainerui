import asyncio

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect
from app.main import create_app
from app.runtime.fake import FakeContainerRuntime
from app.services import data_plane, reaper
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


def _settings(tmp_path, *, routes_dir=True) -> Settings:
    return Settings(
        db_path=tmp_path / "routes.db",
        uploads_dir=tmp_path / "uploads",
        data_plane_secret=SECRET,
        caddy_routes_dir=(tmp_path / "routes") if routes_dir else None,
        caddy_container=CADDY,
    )


@pytest.fixture
def env(tmp_path, fake_runtime):
    fake_runtime.register_container(CADDY)
    settings = _settings(tmp_path)
    app = create_app(settings, runtime=fake_runtime)
    with TestClient(app, base_url="http://testserver") as client:
        fake_runtime.exec_calls.clear()  # ignora o reload do startup
        yield client, settings, fake_runtime


def _create_instance(client, settings, email="dono@exemplo.test") -> tuple[str, int]:
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
    resp = client.post("/api/instances", json={"image_id": image_id})
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"], image_id


def _reloads(runtime) -> list[list[str]]:
    return [
        call["command"]
        for call in runtime.exec_calls
        if call["command"] == data_plane.CADDY_RELOAD_COMMAND
    ]


def test_data_plane_rota_publicada_na_criacao_e_recarrega(env):
    client, settings, runtime = env
    instance_id, _ = _create_instance(client, settings)

    path = data_plane.route_path(settings.caddy_routes_dir, instance_id)
    content = path.read_text(encoding="utf-8")

    assert f"handle /i/{instance_id}/*" in content
    assert f"reverse_proxy wcui-{instance_id}:3000" in content
    assert "forward_auth portal:8000" in content
    assert "copy_headers Authorization" in content
    assert len(_reloads(runtime)) == 1


def test_data_plane_publish_route_e_idempotente(env):
    client, settings, runtime = env

    asyncio.run(data_plane.publish_route(runtime, settings, "id-x", "container-x", 3000))
    asyncio.run(data_plane.publish_route(runtime, settings, "id-x", "container-x", 3000))

    assert len(_reloads(runtime)) == 1  # a segunda chamada não reescreve nem recarrega


def test_data_plane_withdraw_route_remove_arquivo_e_recarrega(env):
    client, settings, runtime = env
    instance_id, _ = _create_instance(client, settings)
    path = data_plane.route_path(settings.caddy_routes_dir, instance_id)
    assert path.exists()

    client.post(f"/api/instances/{instance_id}/stop")

    assert not path.exists()
    assert len(_reloads(runtime)) == 2  # criação + parada


def test_data_plane_withdraw_sem_arquivo_nao_recarrega(env):
    client, settings, runtime = env

    asyncio.run(data_plane.withdraw_route(runtime, settings, "nunca-publicada"))

    assert _reloads(runtime) == []


def test_data_plane_sem_routes_dir_e_noop(tmp_path, fake_runtime):
    fake_runtime.register_container(CADDY)
    settings = _settings(tmp_path, routes_dir=False)
    app = create_app(settings, runtime=fake_runtime)
    with TestClient(app, base_url="http://testserver") as client:
        asyncio.run(
            data_plane.publish_route(fake_runtime, settings, "id-x", "container-x", 3000)
        )
        asyncio.run(data_plane.withdraw_route(fake_runtime, settings, "id-x"))

    assert fake_runtime.exec_calls == []


def test_data_plane_exclusao_retira_rota(env):
    client, settings, runtime = env
    instance_id, _ = _create_instance(client, settings)
    path = data_plane.route_path(settings.caddy_routes_dir, instance_id)

    resp = client.delete(f"/api/instances/{instance_id}?confirm=true")

    assert resp.status_code == 204
    assert not path.exists()


def test_data_plane_atualizacao_republica_rota(env):
    client, settings, runtime = env
    instance_id, _ = _create_instance(client, settings)
    path = data_plane.route_path(settings.caddy_routes_dir, instance_id)

    resp = client.post(f"/api/instances/{instance_id}/update")

    assert resp.status_code == 200, resp.text
    assert path.exists()
    assert f"wcui-{instance_id}:3000" in path.read_text(encoding="utf-8")


def test_data_plane_startup_publica_vivas_e_remove_rotas_orfas(tmp_path):
    settings = _settings(tmp_path)
    runtime1 = FakeContainerRuntime()
    runtime1.register_container(CADDY)
    app1 = create_app(settings, runtime=runtime1)
    with TestClient(app1, base_url="http://testserver") as client:
        instance_id, _ = _create_instance(client, settings)
        conn = connect(settings.db_path)
        container_id = conn.execute(
            "SELECT container_id FROM instances WHERE id = ?", (instance_id,)
        ).fetchone()["container_id"]
        conn.close()

    orfa = settings.caddy_routes_dir / "00000000-0000-0000-0000-000000000000.caddy"
    orfa.write_text("# rota órfã\n", encoding="utf-8")

    runtime2 = FakeContainerRuntime()
    runtime2.register_container(CADDY)
    runtime2.register_container(container_id)  # container segue vivo no host
    app2 = create_app(settings, runtime=runtime2)
    with TestClient(app2, base_url="http://testserver"):
        pass

    assert data_plane.route_path(settings.caddy_routes_dir, instance_id).exists()
    assert not orfa.exists()


def test_data_plane_reaper_retira_rota_ao_parar_por_ociosidade(tmp_path):
    runtime = FakeContainerRuntime()
    runtime.register_container(CADDY)
    settings = _settings(tmp_path)
    app = create_app(settings, runtime=runtime)
    with TestClient(app, base_url="http://testserver") as client:
        instance_id, _ = _create_instance(client, settings)
        conn = connect(settings.db_path)
        conn.execute(
            "UPDATE instances SET last_seen_at = '2000-01-01 00:00:00' WHERE id = ?",
            (instance_id,),
        )
        conn.close()

        async def _uma_rodada():
            task = asyncio.create_task(
                reaper.run_reaper(
                    settings.db_path,
                    runtime,
                    idle_timeout_minutes=1,
                    interval_seconds=0.01,
                    settings=settings,
                )
            )
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(_uma_rodada())

        assert not data_plane.route_path(settings.caddy_routes_dir, instance_id).exists()

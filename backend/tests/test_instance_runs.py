import uuid

from app.db import connect
from app.runtime.errors import RuntimeOperationError
from app.services.instances import _close_run, _open_run

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image, insert_user


def _novo_id():
    return str(uuid.uuid4())


def _insert_instance(conn, user_id, image_id, instance_id=None):
    instance_id = instance_id or _novo_id()
    conn.execute(
        """INSERT INTO instances
               (id, user_id, image_id, volume_name, inner_user, inner_password)
           VALUES (?, ?, ?, 'vol-1', 'u', 'p')""",
        (instance_id, user_id, image_id),
    )
    return instance_id


def test_abrir_run_cria_registro_sem_fim(db_conn):
    user_id = insert_user(db_conn)
    image_id = insert_image(db_conn)
    instance_id = _insert_instance(db_conn, user_id, image_id)

    _open_run(db_conn, instance_id, user_id, image_id)

    row = db_conn.execute(
        "SELECT user_id, image_id, ended_at FROM instance_runs WHERE instance_id = ?", (instance_id,)
    ).fetchone()
    assert row["user_id"] == user_id
    assert row["image_id"] == image_id
    assert row["ended_at"] is None


def test_abrir_run_duas_vezes_nao_duplica(db_conn):
    user_id = insert_user(db_conn)
    image_id = insert_image(db_conn)
    instance_id = _insert_instance(db_conn, user_id, image_id)

    _open_run(db_conn, instance_id, user_id, image_id)
    _open_run(db_conn, instance_id, user_id, image_id)

    total = db_conn.execute(
        "SELECT COUNT(*) FROM instance_runs WHERE instance_id = ?", (instance_id,)
    ).fetchone()[0]
    assert total == 1


def test_fechar_run_aberto_grava_fim_e_motivo(db_conn):
    user_id = insert_user(db_conn)
    image_id = insert_image(db_conn)
    instance_id = _insert_instance(db_conn, user_id, image_id)
    _open_run(db_conn, instance_id, user_id, image_id)

    _close_run(db_conn, instance_id, "user_stop")

    row = db_conn.execute(
        "SELECT ended_at, ended_reason FROM instance_runs WHERE instance_id = ?", (instance_id,)
    ).fetchone()
    assert row["ended_at"] is not None
    assert row["ended_reason"] == "user_stop"


def test_fechar_run_sem_run_aberto_e_noop(db_conn):
    user_id = insert_user(db_conn)
    image_id = insert_image(db_conn)
    instance_id = _insert_instance(db_conn, user_id, image_id)

    _close_run(db_conn, instance_id, "user_stop")  # não levanta erro

    total = db_conn.execute(
        "SELECT COUNT(*) FROM instance_runs WHERE instance_id = ?", (instance_id,)
    ).fetchone()[0]
    assert total == 0


def test_fechar_run_ja_fechado_nao_sobrescreve_motivo(db_conn):
    user_id = insert_user(db_conn)
    image_id = insert_image(db_conn)
    instance_id = _insert_instance(db_conn, user_id, image_id)
    _open_run(db_conn, instance_id, user_id, image_id)
    _close_run(db_conn, instance_id, "user_stop")

    _close_run(db_conn, instance_id, "idle_timeout")

    row = db_conn.execute(
        "SELECT ended_reason FROM instance_runs WHERE instance_id = ?", (instance_id,)
    ).fetchone()
    assert row["ended_reason"] == "user_stop"


def _login_as(client, seed_user, email, password="senha-usuario-123"):
    seed_user(email, password)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["id"]


def test_criar_instancia_com_sucesso_abre_run(client, seed_user, app_settings):
    user_id = _login_as(client, seed_user, "runs-criacao@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]

    conn = connect(app_settings.db_path)
    row = conn.execute(
        "SELECT user_id, image_id, ended_at FROM instance_runs WHERE instance_id = ?", (instance_id,)
    ).fetchone()
    conn.close()
    assert row["user_id"] == user_id
    assert row["image_id"] == image_id
    assert row["ended_at"] is None


def test_falha_na_criacao_nao_abre_run(client, seed_user, app_settings, fake_runtime):
    fake_runtime.fail_next("start_container", RuntimeOperationError("docker indisponível"))
    user_id = _login_as(client, seed_user, "runs-falha@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]

    conn = connect(app_settings.db_path)
    total = conn.execute(
        "SELECT COUNT(*) FROM instance_runs WHERE instance_id = ?", (instance_id,)
    ).fetchone()[0]
    conn.close()
    assert total == 0


def test_parar_pela_rota_fecha_run_com_user_stop(client, seed_user, app_settings):
    user_id = _login_as(client, seed_user, "runs-parar@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]

    resp = client.post(f"/api/instances/{instance_id}/stop")
    assert resp.status_code == 204

    conn = connect(app_settings.db_path)
    row = conn.execute(
        "SELECT ended_at, ended_reason FROM instance_runs WHERE instance_id = ?", (instance_id,)
    ).fetchone()
    conn.close()
    assert row["ended_at"] is not None
    assert row["ended_reason"] == "user_stop"


def test_parar_instancia_ja_parada_e_idempotente_sem_duplicar_fechamento(client, seed_user, app_settings):
    user_id = _login_as(client, seed_user, "runs-parar-dupla@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]

    assert client.post(f"/api/instances/{instance_id}/stop").status_code == 204
    assert client.post(f"/api/instances/{instance_id}/stop").status_code == 204  # idempotente

    conn = connect(app_settings.db_path)
    total = conn.execute(
        "SELECT COUNT(*) FROM instance_runs WHERE instance_id = ?", (instance_id,)
    ).fetchone()[0]
    conn.close()
    assert total == 1


async def test_ociosidade_fecha_run_com_idle_timeout(client, seed_user, app_settings, fake_runtime):
    import asyncio

    from app.services.reaper import reap_idle_instances

    user_id = _login_as(client, seed_user, "runs-ociosa@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]

    conn = connect(app_settings.db_path)
    conn.execute("UPDATE instances SET last_seen_at = '2000-01-01 00:00:00' WHERE id = ?", (instance_id,))
    conn.close()

    conn = connect(app_settings.db_path)
    await reap_idle_instances(conn, fake_runtime, app_settings.idle_timeout_minutes)
    conn.close()

    conn = connect(app_settings.db_path)
    row = conn.execute(
        "SELECT ended_at, ended_reason FROM instance_runs WHERE instance_id = ?", (instance_id,)
    ).fetchone()
    conn.close()
    assert row["ended_at"] is not None
    assert row["ended_reason"] == "idle_timeout"


async def test_reconciliacao_fecha_run_com_reconciled(client, seed_user, app_settings, fake_runtime):
    from app.services.reaper import reconcile_instance_states

    user_id = _login_as(client, seed_user, "runs-reconc@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]

    conn = connect(app_settings.db_path)
    container_id = conn.execute(
        "SELECT container_id FROM instances WHERE id = ?", (instance_id,)
    ).fetchone()["container_id"]
    conn.close()
    await fake_runtime.remove_container(container_id)  # encerrado "por fora"

    conn = connect(app_settings.db_path)
    await reconcile_instance_states(conn, fake_runtime)
    conn.close()

    conn = connect(app_settings.db_path)
    row = conn.execute(
        "SELECT ended_at, ended_reason FROM instance_runs WHERE instance_id = ?", (instance_id,)
    ).fetchone()
    conn.close()
    assert row["ended_at"] is not None
    assert row["ended_reason"] == "reconciled"


def test_excluir_instancia_em_execucao_fecha_run_com_deleted(client, seed_user, app_settings):
    user_id = _login_as(client, seed_user, "runs-excluir@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]

    resp = client.delete(f"/api/instances/{instance_id}?confirm=true")
    assert resp.status_code == 204

    conn = connect(app_settings.db_path)
    row = conn.execute(
        "SELECT ended_at, ended_reason FROM instance_runs WHERE instance_id = ?", (instance_id,)
    ).fetchone()
    conn.close()
    assert row["ended_at"] is not None
    assert row["ended_reason"] == "deleted"


def test_excluir_instancia_ja_parada_nao_falha_nem_fecha_run(client, seed_user, app_settings):
    user_id = _login_as(client, seed_user, "runs-excluir-parada@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]
    client.post(f"/api/instances/{instance_id}/stop")

    resp = client.delete(f"/api/instances/{instance_id}?confirm=true")
    assert resp.status_code == 204

    conn = connect(app_settings.db_path)
    row = conn.execute(
        "SELECT ended_reason FROM instance_runs WHERE instance_id = ?", (instance_id,)
    ).fetchone()
    conn.close()
    assert row["ended_reason"] == "user_stop"  # não sobrescrito por "deleted"


def test_backfill_abre_run_para_instancia_ja_em_execucao_antes_do_deploy(app_settings, fake_runtime):
    from app.db import init_db
    from app.main import create_app
    from app.runtime.protocol import ContainerState

    from fastapi.testclient import TestClient

    conn = connect(app_settings.db_path)
    init_db(conn)
    user_id = insert_user(conn)
    image_id = insert_image(conn)
    instance_id = _novo_id()
    container_id = "fake-pre-existente"
    conn.execute(
        """INSERT INTO instances
               (id, user_id, image_id, container_id, container_name, volume_name,
                inner_user, inner_password, state, last_seen_at)
           VALUES (?, ?, ?, ?, 'c', 'vol-1', 'u', 'p', 'running', '2024-01-01 00:00:00')""",
        (instance_id, user_id, image_id, container_id),
    )
    conn.close()
    fake_runtime._containers[container_id] = {"spec": None, "state": ContainerState.RUNNING}

    app = create_app(app_settings, runtime=fake_runtime)
    with TestClient(app, base_url="http://testserver"):
        pass  # só dispara o lifespan (reconciliação + backfill)

    conn = connect(app_settings.db_path)
    row = conn.execute(
        "SELECT started_at, ended_at FROM instance_runs WHERE instance_id = ?", (instance_id,)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["ended_at"] is None
    assert row["started_at"] == "2024-01-01 00:00:00"


def test_backfill_rodando_de_novo_nao_duplica_o_run(app_settings, fake_runtime):
    from app.db import init_db
    from app.main import create_app
    from app.runtime.protocol import ContainerState

    from fastapi.testclient import TestClient

    conn = connect(app_settings.db_path)
    init_db(conn)
    user_id = insert_user(conn)
    image_id = insert_image(conn)
    instance_id = _novo_id()
    container_id = "fake-pre-existente-2"
    conn.execute(
        """INSERT INTO instances
               (id, user_id, image_id, container_id, container_name, volume_name,
                inner_user, inner_password, state)
           VALUES (?, ?, ?, ?, 'c', 'vol-1', 'u', 'p', 'running')""",
        (instance_id, user_id, image_id, container_id),
    )
    conn.close()
    fake_runtime._containers[container_id] = {"spec": None, "state": ContainerState.RUNNING}

    app = create_app(app_settings, runtime=fake_runtime)
    with TestClient(app, base_url="http://testserver"):
        pass
    with TestClient(app, base_url="http://testserver"):
        pass  # reinício simulado: backfill roda de novo

    conn = connect(app_settings.db_path)
    total = conn.execute(
        "SELECT COUNT(*) FROM instance_runs WHERE instance_id = ?", (instance_id,)
    ).fetchone()[0]
    conn.close()
    assert total == 1


def test_religar_instancia_parada_abre_novo_run(client, seed_user, app_settings):
    user_id = _login_as(client, seed_user, "runs-religar@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]
    client.post(f"/api/instances/{instance_id}/stop")
    client.post("/api/instances", json={"image_id": image_id})  # religa a mesma instância

    conn = connect(app_settings.db_path)
    rows = conn.execute(
        "SELECT ended_at FROM instance_runs WHERE instance_id = ? ORDER BY id", (instance_id,)
    ).fetchall()
    conn.close()
    assert len(rows) == 2
    assert rows[0]["ended_at"] is not None  # primeiro run, fechado pelo stop
    assert rows[1]["ended_at"] is None  # segundo run, aberto pela religada

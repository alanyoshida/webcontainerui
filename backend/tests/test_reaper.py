from app.db import connect
from app.runtime.protocol import ContainerState
from app.services.reaper import reap_idle_instances, reconcile_instance_states, run_reaper

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image


def _login_as(client, seed_user, email, password="senha-usuario-123"):
    seed_user(email, password)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["id"]


def test_instancia_ociosa_alem_do_limite_e_parada_com_volume_preservado(
    client, seed_user, app_settings, fake_runtime
):
    user_id = _login_as(client, seed_user, "ociosa@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]

    conn = connect(app_settings.db_path)
    volume_name = conn.execute(
        "SELECT volume_name FROM instances WHERE id = ?", (instance_id,)
    ).fetchone()["volume_name"]
    # simula inatividade: last_seen_at bem no passado
    conn.execute(
        "UPDATE instances SET last_seen_at = '2000-01-01 00:00:00' WHERE id = ?", (instance_id,)
    )
    conn.close()

    conn = connect(app_settings.db_path)
    import asyncio

    paradas = asyncio.run(reap_idle_instances(conn, fake_runtime, app_settings.idle_timeout_minutes))
    conn.close()

    assert paradas == [instance_id]
    conn = connect(app_settings.db_path)
    row = conn.execute("SELECT state FROM instances WHERE id = ?", (instance_id,)).fetchone()
    conn.close()
    assert row["state"] == "stopped"
    assert volume_name in fake_runtime._volumes


def test_sessao_com_trafego_continuo_nao_e_parada(client, seed_user, app_settings, fake_runtime):
    import asyncio

    user_id = _login_as(client, seed_user, "ativa@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]
    # last_seen_at recente (padrão NULL->created_at agora, também recente)

    conn = connect(app_settings.db_path)
    paradas = asyncio.run(reap_idle_instances(conn, fake_runtime, app_settings.idle_timeout_minutes))
    conn.close()

    assert paradas == []
    conn = connect(app_settings.db_path)
    row = conn.execute("SELECT state FROM instances WHERE id = ?", (instance_id,)).fetchone()
    conn.close()
    assert row["state"] == "running"


def test_reconciliacao_corrige_container_encerrado_por_fora(
    client, seed_user, app_settings, fake_runtime
):
    import asyncio

    user_id = _login_as(client, seed_user, "externa@exemplo.test")
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

    # encerrado "por fora": o runtime some com o container sem o DB saber
    asyncio.run(fake_runtime.remove_container(container_id))

    conn = connect(app_settings.db_path)
    corrigidas = asyncio.run(reconcile_instance_states(conn, fake_runtime))
    conn.close()

    assert corrigidas == [instance_id]
    conn = connect(app_settings.db_path)
    row = conn.execute("SELECT state FROM instances WHERE id = ?", (instance_id,)).fetchone()
    conn.close()
    assert row["state"] == "stopped"


async def test_run_reaper_reconcilia_sozinho_sem_chamada_direta(client, seed_user, app_settings, fake_runtime):
    """O loop do reaper reconcilia a cada iteração (11.1): uma instância cujo
    container morreu por fora vira "stopped" só por `run_reaper` rodar, sem
    que o teste precise chamar `reconcile_instance_states` diretamente."""
    import asyncio

    user_id = _login_as(client, seed_user, "loop-reconcilia@exemplo.test")
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

    task = asyncio.create_task(
        run_reaper(app_settings.db_path, fake_runtime, idle_timeout_minutes=30, interval_seconds=0.01)
    )
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    conn = connect(app_settings.db_path)
    row = conn.execute("SELECT state FROM instances WHERE id = ?", (instance_id,)).fetchone()
    conn.close()
    assert row["state"] == "stopped"


async def test_instancia_reconciliada_nao_vira_candidata_a_parar_por_ociosidade(
    client, seed_user, app_settings, fake_runtime, monkeypatch
):
    """11.2: a reconciliação roda antes da checagem de ociosidade na mesma
    iteração, então uma instância corrigida para "stopped" não deve nem
    aparecer para `find_idle_running_instances` naquele ciclo."""
    import asyncio

    import app.services.reaper as reaper_module

    user_id = _login_as(client, seed_user, "nao-candidata@exemplo.test")
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
    await fake_runtime.remove_container(container_id)

    candidatos_vistos = []
    original_find = reaper_module.find_idle_running_instances

    def espiando(conn, idle_timeout_minutes):
        candidatos = original_find(conn, idle_timeout_minutes)
        candidatos_vistos.append([row["id"] for row in candidatos])
        return candidatos

    monkeypatch.setattr(reaper_module, "find_idle_running_instances", espiando)

    task = asyncio.create_task(
        run_reaper(app_settings.db_path, fake_runtime, idle_timeout_minutes=30, interval_seconds=0.01)
    )
    await asyncio.sleep(0.03)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(candidatos_vistos) >= 1
    for candidatos in candidatos_vistos:
        assert instance_id not in candidatos


async def test_falha_na_reconciliacao_nao_interrompe_o_loop(app_settings, fake_runtime, monkeypatch):
    """Mesma proteção por iteração que já existe para reap_idle_instances
    (10.3) vale para a chamada de reconciliação."""
    import asyncio

    from app.db import init_db
    import app.services.reaper as reaper_module

    conn = connect(app_settings.db_path)
    init_db(conn)
    conn.close()

    chamadas = []
    original = reaper_module.reconcile_instance_states

    async def falha_depois_funciona(conn, runtime):
        chamadas.append(1)
        if len(chamadas) == 1:
            raise RuntimeError("falha simulada na reconciliação")
        return await original(conn, runtime)

    monkeypatch.setattr(reaper_module, "reconcile_instance_states", falha_depois_funciona)

    task = asyncio.create_task(
        run_reaper(app_settings.db_path, fake_runtime, idle_timeout_minutes=30, interval_seconds=0.01)
    )
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(chamadas) >= 2  # sobreviveu à falha e seguiu rodando


async def test_falha_injetada_no_reaper_nao_encerra_o_loop(app_settings, fake_runtime, monkeypatch):
    """Uma iteração falhando não deve impedir a próxima de rodar (10.3)."""
    import asyncio

    from app.db import init_db
    import app.services.reaper as reaper_module

    conn = connect(app_settings.db_path)
    init_db(conn)
    conn.close()

    chamadas = []
    original = reaper_module.reap_idle_instances

    async def falha_depois_funciona(conn, runtime, idle_timeout_minutes):
        chamadas.append(1)
        if len(chamadas) == 1:
            raise RuntimeError("falha simulada na primeira iteração")
        return await original(conn, runtime, idle_timeout_minutes)

    monkeypatch.setattr(reaper_module, "reap_idle_instances", falha_depois_funciona)

    task = asyncio.create_task(
        run_reaper(app_settings.db_path, fake_runtime, idle_timeout_minutes=30, interval_seconds=0.01)
    )
    await asyncio.sleep(0.05)  # algumas iterações, a primeira falhando
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(chamadas) >= 2  # sobreviveu à falha e seguiu rodando

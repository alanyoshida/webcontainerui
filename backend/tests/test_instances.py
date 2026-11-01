import io
import tarfile

from app.db import connect
from app.runtime.errors import RuntimeOperationError

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image


def _tar_content(tar_bytes: bytes, name: str) -> bytes:
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
        return tar.extractfile(name).read()


def _login_admin(client, seed_user, email="admin@exemplo.test", password="senha-admin-123"):
    seed_user(email, password, is_admin=True)
    client.post("/api/auth/login", json={"email": email, "password": password})


def _login_as(client, seed_user, email, password="senha-usuario-123"):
    seed_user(email, password)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["id"]


def test_criacao_registra_o_dono(client, seed_user, app_settings):
    user_id = _login_as(client, seed_user, "dona@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    resp = client.post("/api/instances", json={"image_id": image_id})

    assert resp.status_code == 201
    conn = connect(app_settings.db_path)
    row = conn.execute(
        "SELECT user_id FROM instances WHERE id = ?", (resp.json()["id"],)
    ).fetchone()
    conn.close()
    assert row["user_id"] == user_id


def test_container_criado_sem_porta_publicada_na_rede_interna_com_sharing_desligado(
    client, seed_user, app_settings, fake_runtime
):
    user_id = _login_as(client, seed_user, "rede@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    resp = client.post("/api/instances", json={"image_id": image_id})
    instance_id = resp.json()["id"]

    conn = connect(app_settings.db_path)
    row = conn.execute("SELECT container_id FROM instances WHERE id = ?", (instance_id,)).fetchone()
    conn.close()

    container = fake_runtime._containers[row["container_id"]]
    spec = container["spec"]

    assert not hasattr(spec, "ports")  # o protocolo nem permite expressar porta publicada
    assert spec.network == app_settings.docker_network
    assert spec.env["SELKIES_ENABLE_SHARING"] == "false"
    assert spec.env["SELKIES_ENABLE_SHARED"] == "false"
    assert spec.env["SUBFOLDER"] == f"/i/{instance_id}/"
    assert "SELKIES_ENABLE_WEBRTC" not in spec.env  # WebRTC nunca é habilitado


def test_criacao_injeta_a_identidade_ssh_do_dono_no_destino_config(
    client, seed_user, app_settings, fake_runtime
):
    from app.db import init_db
    from app.services.ssh_identity import get_or_create_identity

    user_id = _login_as(client, seed_user, "ssh@exemplo.test")
    conn = connect(app_settings.db_path)
    init_db(conn)
    image_id = insert_image(conn)  # provision_kind='pull' (webtop) por padrão
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    identity = get_or_create_identity(conn, app_settings, user_id)
    conn.close()

    resp = client.post("/api/instances", json={"image_id": image_id})
    assert resp.status_code == 201

    assert len(fake_runtime.put_archive_calls) == 1
    call = fake_runtime.put_archive_calls[0]
    assert call["destination_path"] == "/config"
    assert _tar_content(call["tar_bytes"], ".ssh/id_ed25519.pub").decode() == identity["public_key"] + "\n"


def test_criacao_fixa_o_dono_dos_arquivos_conforme_provision_kind(
    client, seed_user, app_settings, fake_runtime
):
    from app.db import init_db

    user_id = _login_as(client, seed_user, "dono-ssh@exemplo.test")
    conn = connect(app_settings.db_path)
    init_db(conn)
    image_webtop = insert_image(conn, repository="exemplo/webtop", tag="latest")
    image_agente = insert_image(
        conn, repository="wcui-agent-teste", tag="latest", provision_kind="build"
    )
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_webtop)
    grant_image_to_group(conn, group_id, image_agente)
    conn.close()

    client.post("/api/instances", json={"image_id": image_webtop})
    client.post("/api/instances", json={"image_id": image_agente})

    assert len(fake_runtime.put_archive_calls) == 2
    webtop_tar = fake_runtime.put_archive_calls[0]["tar_bytes"]
    agente_tar = fake_runtime.put_archive_calls[1]["tar_bytes"]
    with tarfile.open(fileobj=io.BytesIO(webtop_tar), mode="r") as tar:
        member = tar.getmember(".ssh")
        assert (member.uid, member.gid) == (app_settings.puid, app_settings.pgid)
    with tarfile.open(fileobj=io.BytesIO(agente_tar), mode="r") as tar:
        member = tar.getmember(".ssh")
        assert (member.uid, member.gid) == (0, 0)


async def test_propagacao_atualiza_instancias_em_execucao_e_paradas(
    client, seed_user, app_settings, fake_runtime
):
    from app.db import init_db
    from app.services.instances import propagate_ssh_identity_to_live_instances
    from app.services.ssh_identity import get_or_create_identity

    user_id = _login_as(client, seed_user, "propaga@exemplo.test")
    conn = connect(app_settings.db_path)
    init_db(conn)
    image_a = insert_image(conn, repository="exemplo/webtop", tag="latest")
    image_b = insert_image(conn, repository="exemplo/webtop", tag="ubuntu-kde")
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_a)
    grant_image_to_group(conn, group_id, image_b)
    get_or_create_identity(conn, app_settings, user_id)
    conn.close()

    resp_a = client.post("/api/instances", json={"image_id": image_a})
    resp_b = client.post("/api/instances", json={"image_id": image_b})
    instance_a = resp_a.json()["id"]
    instance_b = resp_b.json()["id"]
    client.post(f"/api/instances/{instance_b}/stop")

    fake_runtime.put_archive_calls.clear()  # ignora as chamadas da própria criação
    conn = connect(app_settings.db_path)
    failures = await propagate_ssh_identity_to_live_instances(conn, fake_runtime, app_settings, user_id)
    conn.close()

    assert failures == []
    atualizadas = {call["container_id"] for call in fake_runtime.put_archive_calls}
    conn = connect(app_settings.db_path)
    container_a = conn.execute(
        "SELECT container_id FROM instances WHERE id = ?", (instance_a,)
    ).fetchone()["container_id"]
    container_b = conn.execute(
        "SELECT container_id FROM instances WHERE id = ?", (instance_b,)
    ).fetchone()["container_id"]
    conn.close()
    assert atualizadas == {container_a, container_b}


async def test_propagacao_isola_falha_por_instancia(client, seed_user, app_settings, fake_runtime):
    from app.db import init_db
    from app.services.instances import propagate_ssh_identity_to_live_instances
    from app.services.ssh_identity import get_or_create_identity

    user_id = _login_as(client, seed_user, "propaga-falha@exemplo.test")
    conn = connect(app_settings.db_path)
    init_db(conn)
    image_a = insert_image(conn, repository="exemplo/webtop", tag="latest")
    image_b = insert_image(conn, repository="exemplo/webtop", tag="ubuntu-kde")
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_a)
    grant_image_to_group(conn, group_id, image_b)
    get_or_create_identity(conn, app_settings, user_id)
    conn.close()

    client.post("/api/instances", json={"image_id": image_a})
    client.post("/api/instances", json={"image_id": image_b})

    fake_runtime.put_archive_calls.clear()
    fake_runtime.fail_next("put_archive", RuntimeOperationError("docker indisponível"))

    conn = connect(app_settings.db_path)
    failures = await propagate_ssh_identity_to_live_instances(conn, fake_runtime, app_settings, user_id)
    conn.close()

    assert len(failures) == 1
    assert len(fake_runtime.put_archive_calls) == 1  # a segunda instância ainda foi tentada e teve sucesso


def test_segunda_instancia_da_mesma_imagem_devolve_a_existente(client, seed_user, app_settings):
    user_id = _login_as(client, seed_user, "dupla@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    primeira = client.post("/api/instances", json={"image_id": image_id})
    segunda = client.post("/api/instances", json={"image_id": image_id})

    assert primeira.json()["id"] == segunda.json()["id"]


def test_instancias_de_imagens_diferentes_coexistem(client, seed_user, app_settings):
    user_id = _login_as(client, seed_user, "multi@exemplo.test")
    conn = connect(app_settings.db_path)
    imagem_a = insert_image(conn, repository="exemplo/webtop", tag="latest")
    imagem_b = insert_image(conn, repository="lscr.io/linuxserver/webtop", tag="alpine-kde")
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, imagem_a)
    grant_image_to_group(conn, group_id, imagem_b)
    conn.close()

    resp_a = client.post("/api/instances", json={"image_id": imagem_a})
    resp_b = client.post("/api/instances", json={"image_id": imagem_b})

    assert resp_a.status_code == resp_b.status_code == 201
    assert resp_a.json()["id"] != resp_b.json()["id"]
    assert len(client.get("/api/instances").json()) == 2


def test_criacao_recusada_para_imagem_nao_pronta(client, seed_user, app_settings):
    user_id = _login_as(client, seed_user, "pendente@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn, pull_state="pulling")
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    resp = client.post("/api/instances", json={"image_id": image_id})
    assert resp.status_code == 400


def test_criacao_recusada_para_imagem_desabilitada(client, seed_user, app_settings):
    user_id = _login_as(client, seed_user, "desab@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn, enabled=False)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    resp = client.post("/api/instances", json={"image_id": image_id})
    assert resp.status_code == 400


def test_criacao_recusada_sem_permissao(client, seed_user, app_settings):
    _login_as(client, seed_user, "sempermissao@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    conn.close()

    resp = client.post("/api/instances", json={"image_id": image_id})
    assert resp.status_code == 403


def test_parar_preserva_o_volume(client, seed_user, app_settings, fake_runtime):
    user_id = _login_as(client, seed_user, "parar@exemplo.test")
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
    conn.close()

    resp = client.post(f"/api/instances/{instance_id}/stop")
    assert resp.status_code == 204

    conn = connect(app_settings.db_path)
    row = conn.execute("SELECT state FROM instances WHERE id = ?", (instance_id,)).fetchone()
    conn.close()
    assert row["state"] == "stopped"
    assert volume_name in fake_runtime._volumes


def test_exclusao_sem_confirmacao_nao_remove_nada(client, seed_user, app_settings):
    user_id = _login_as(client, seed_user, "semconf@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]

    resp = client.delete(f"/api/instances/{instance_id}")
    assert resp.status_code == 400

    conn = connect(app_settings.db_path)
    row = conn.execute("SELECT deleted_at FROM instances WHERE id = ?", (instance_id,)).fetchone()
    conn.close()
    assert row["deleted_at"] is None


def test_exclusao_confirmada_permite_nova_instancia_da_mesma_imagem(
    client, seed_user, app_settings, fake_runtime
):
    user_id = _login_as(client, seed_user, "comconf@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    primeira_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]

    resp = client.delete(f"/api/instances/{primeira_id}?confirm=true")
    assert resp.status_code == 204

    segunda = client.post("/api/instances", json={"image_id": image_id})
    assert segunda.status_code == 201
    assert segunda.json()["id"] != primeira_id


def test_acao_sobre_instancia_de_outro_usuario_e_recusada(client, seed_user, app_settings):
    dono_id = _login_as(client, seed_user, "dono2@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, dono_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]

    # outro usuário, mesma app (sessão substitui o cookie no mesmo client)
    from fastapi.testclient import TestClient

    with TestClient(client.app, base_url="http://testserver") as outro_client:
        _login_as(outro_client, seed_user, "outro2@exemplo.test")

        resp_stop = outro_client.post(f"/api/instances/{instance_id}/stop")
        resp_delete = outro_client.delete(f"/api/instances/{instance_id}?confirm=true")

        assert resp_stop.status_code == 404
        assert resp_delete.status_code == 404


def test_listagem_retorna_apenas_as_instancias_do_solicitante(client, seed_user, app_settings):
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    conn.close()

    usuario_a = _login_as(client, seed_user, "a@exemplo.test")
    conn = connect(app_settings.db_path)
    add_user_to_group(conn, usuario_a, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    client.post("/api/instances", json={"image_id": image_id})

    from fastapi.testclient import TestClient

    with TestClient(client.app, base_url="http://testserver") as client_b:
        usuario_b = _login_as(client_b, seed_user, "b@exemplo.test")
        conn = connect(app_settings.db_path)
        add_user_to_group(conn, usuario_b, group_id)
        conn.close()

        assert client_b.get("/api/instances").json() == []


def test_falha_na_criacao_deixa_estado_de_erro_sem_container_em_execucao(
    client, seed_user, app_settings, fake_runtime
):
    fake_runtime.fail_next("start_container", RuntimeOperationError("docker indisponível"))
    user_id = _login_as(client, seed_user, "falha@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    resp = client.post("/api/instances", json={"image_id": image_id})

    assert resp.status_code == 201  # a rota responde; o erro fica no estado da instância
    body = resp.json()
    assert body["state"] == "error"
    assert "docker indisponível" in body["error_message"]
    assert fake_runtime._containers == {}  # removido após a falha no start


def test_desabilitar_conta_para_instancia_em_execucao_preservando_volume(
    client, seed_user, app_settings, fake_runtime
):
    from fastapi.testclient import TestClient

    _login_admin(client, seed_user)
    with TestClient(client.app, base_url="http://testserver") as client_usuario:
        user_id = _login_as(client_usuario, seed_user, "paraisar@exemplo.test")
        conn = connect(app_settings.db_path)
        image_id = insert_image(conn)
        group_id = insert_group(conn)
        add_user_to_group(conn, user_id, group_id)
        grant_image_to_group(conn, group_id, image_id)
        conn.close()
        instance_id = client_usuario.post("/api/instances", json={"image_id": image_id}).json()["id"]

        resp = client.post(f"/api/admin/users/{user_id}/disable")
        assert resp.status_code == 204

        conn = connect(app_settings.db_path)
        row = conn.execute(
            "SELECT state, volume_name FROM instances WHERE id = ?", (instance_id,)
        ).fetchone()
        conn.close()
        assert row["state"] == "stopped"
        assert row["volume_name"] in fake_runtime._volumes


def test_env_PORTA_usa_a_porta_da_imagem(client, seed_user, app_settings, fake_runtime):
    user_id = _login_as(client, seed_user, "porta@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn, port=4242)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    resp = client.post("/api/instances", json={"image_id": image_id})
    instance_id = resp.json()["id"]

    conn = connect(app_settings.db_path)
    from app.services.instances import get_owned_instance

    row = get_owned_instance(conn, instance_id, user_id)
    container_id = conn.execute(
        "SELECT container_id FROM instances WHERE id = ?", (instance_id,)
    ).fetchone()["container_id"]
    conn.close()

    assert row["image_port"] == 4242
    spec = fake_runtime._containers[container_id]["spec"]
    assert spec.env["PORT"] == "4242"


def test_resposta_da_instancia_expoe_versao_da_instancia_e_do_catalogo(client, seed_user, app_settings):
    user_id = _login_as(client, seed_user, "versao@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn, image_version="1.143.1-ls31")
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    resp = client.post("/api/instances", json={"image_id": image_id})

    body = resp.json()
    assert body["image_version"] == "1.143.1-ls31"  # snapshot da criação
    assert body["image_catalog_version"] == "1.143.1-ls31"


def test_atualizacao_recria_o_container_do_tag_atual_preservando_o_volume(
    client, seed_user, app_settings, fake_runtime
):
    user_id = _login_as(client, seed_user, "update@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn, image_version="1.0.0")
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]

    conn = connect(app_settings.db_path)
    antiga = conn.execute(
        "SELECT container_id, container_name, volume_name FROM instances WHERE id = ?",
        (instance_id,),
    ).fetchone()
    conn.close()
    container_antigo = antiga["container_id"]
    volume_name = antiga["volume_name"]
    assert volume_name in fake_runtime._volumes

    # o catálogo ganhou uma versão nova (update-image concluído)
    conn = connect(app_settings.db_path)
    conn.execute("UPDATE images SET image_version = '2.0.0' WHERE id = ?", (image_id,))
    conn.close()

    resp = client.post(f"/api/instances/{instance_id}/update")
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "running"
    assert body["image_version"] == "2.0.0"  # snapshot atualizado na recriação
    assert body["image_catalog_version"] == "2.0.0"

    conn = connect(app_settings.db_path)
    nova = conn.execute(
        "SELECT container_id, volume_name FROM instances WHERE id = ?", (instance_id,)
    ).fetchone()
    conn.close()

    assert nova["container_id"] != container_antigo
    assert container_antigo not in fake_runtime._containers  # container antigo removido
    assert nova["volume_name"] == volume_name  # volume preservado
    assert volume_name in fake_runtime._volumes  # e não removido do runtime

    # container recriado do repositório/tag atual da imagem
    spec = fake_runtime._containers[nova["container_id"]]["spec"]
    assert spec.repository == "exemplo/webtop"  # repositório do insert_image
    assert spec.tag == "latest"


def test_atualizacao_fecha_o_run_antigo_e_abre_run_novo(client, seed_user, app_settings):
    user_id = _login_as(client, seed_user, "runs@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]

    resp = client.post(f"/api/instances/{instance_id}/update")
    assert resp.status_code == 200

    conn = connect(app_settings.db_path)
    runs = conn.execute(
        "SELECT started_at, ended_at, ended_reason FROM instance_runs"
        " WHERE instance_id = ? ORDER BY id",
        (instance_id,),
    ).fetchall()
    conn.close()
    assert len(runs) == 2
    assert runs[0]["ended_at"] is not None
    assert runs[0]["ended_reason"] == "instance_update"
    assert runs[1]["ended_at"] is None  # run novo em aberto


def test_atualizacao_de_instancia_parada_recria_ao_iniciar(client, seed_user, app_settings, fake_runtime):
    user_id = _login_as(client, seed_user, "parada@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]
    client.post(f"/api/instances/{instance_id}/stop")

    resp = client.post(f"/api/instances/{instance_id}/update")

    assert resp.status_code == 200
    assert resp.json()["state"] == "running"


def test_atualizacao_recusada_quando_a_imagem_nao_esta_pronta(client, seed_user, app_settings):
    user_id = _login_as(client, seed_user, "naopronta@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]

    conn = connect(app_settings.db_path)
    conn.execute("UPDATE images SET pull_state = 'pulling' WHERE id = ?", (image_id,))
    conn.close()

    resp = client.post(f"/api/instances/{instance_id}/update")
    assert resp.status_code == 400


def test_atualizacao_por_nao_dono_e_404_anonimo(client, seed_user, app_settings):
    dono_id = _login_as(client, seed_user, "donoupdate@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    add_user_to_group(conn, dono_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]

    from fastapi.testclient import TestClient

    with TestClient(client.app, base_url="http://testserver") as outro_client:
        _login_as(outro_client, seed_user, "outroupdate@exemplo.test")
        resp = outro_client.post(f"/api/instances/{instance_id}/update")
        assert resp.status_code == 404


def test_recriacao_religa_snapshot_da_versao_do_catalogo(client, seed_user, app_settings, fake_runtime):
    """2.3: instância cujo container foi recriado passa a registrar a
    versão atual do catálogo. Mera religada (start do mesmo container) não
    é recriação — o snapshot permanece o da criação do container."""
    user_id = _login_as(client, seed_user, "snapshot@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn, image_version="1.0.0")
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
    client.post(f"/api/instances/{instance_id}/stop")
    fake_runtime._containers.pop(container_id)  # container sumiu do runtime

    # o catálogo avançou de versão antes da recriação
    conn = connect(app_settings.db_path)
    conn.execute("UPDATE images SET image_version = '3.0.0' WHERE id = ?", (image_id,))
    conn.close()

    resp = client.post("/api/instances", json={"image_id": image_id})
    assert resp.status_code == 201  # devolve a instância existente, recriada
    assert resp.json()["image_version"] == "3.0.0"

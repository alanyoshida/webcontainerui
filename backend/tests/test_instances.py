from app.db import connect
from app.runtime.errors import RuntimeOperationError

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image


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
    imagem_a = insert_image(conn, repository="lscr.io/linuxserver/webtop", tag="latest")
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

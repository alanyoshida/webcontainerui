import base64

from app.db import connect

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image


def _login_as(client, seed_user, email, password="senha-usuario-123"):
    seed_user(email, password)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["id"]


def _create_running_instance(client, seed_user, app_settings, email, *, tag="latest") -> tuple[str, int]:
    user_id = _login_as(client, seed_user, email)
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn, tag=tag)
    group_id = insert_group(conn, name=f"grupo-{email}")
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()
    instance_id = client.post("/api/instances", json={"image_id": image_id}).json()["id"]
    return instance_id, user_id


def test_requisicao_anonima_e_recusada(proxy_client):
    resp = proxy_client.get("/i/qualquer-coisa/echo-headers")
    assert resp.status_code == 401


def test_dono_alcanca_a_propria_instancia_e_credencial_interna_e_injetada(
    proxy_client, seed_user, app_settings
):
    instance_id, _ = _create_running_instance(proxy_client, seed_user, app_settings, "dona@exemplo.test")
    conn = connect(app_settings.db_path)
    row = conn.execute(
        "SELECT inner_user, inner_password FROM instances WHERE id = ?", (instance_id,)
    ).fetchone()
    conn.close()

    resp = proxy_client.get(
        f"/i/{instance_id}/echo-headers", headers={"Authorization": "Basic cliente-nao-deve-passar"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["instance_id"] == instance_id
    esperado = "Basic " + base64.b64encode(
        f"{row['inner_user']}:{row['inner_password']}".encode()
    ).decode()
    assert body["authorization"] == esperado  # a credencial do cliente foi descartada


def test_acesso_a_instancia_de_outro_usuario_e_recusado_sem_revelar_existencia(
    proxy_client, seed_user, app_settings
):
    from fastapi.testclient import TestClient

    instance_id, _ = _create_running_instance(proxy_client, seed_user, app_settings, "a2@exemplo.test")

    with TestClient(proxy_client.app, base_url="http://testserver") as outro:
        _login_as(outro, seed_user, "b2@exemplo.test")

        resp_de_outro = outro.get(f"/i/{instance_id}/echo-headers")
        resp_inexistente = outro.get("/i/00000000-0000-0000-0000-000000000000/echo-headers")

        assert resp_de_outro.status_code == resp_inexistente.status_code == 404
        assert resp_de_outro.json() == resp_inexistente.json()


def test_instancia_parada_nao_e_encaminhada(proxy_client, seed_user, app_settings):
    instance_id, _ = _create_running_instance(proxy_client, seed_user, app_settings, "parada@exemplo.test")
    proxy_client.post(f"/api/instances/{instance_id}/stop")

    resp = proxy_client.get(f"/i/{instance_id}/echo-headers")

    assert resp.status_code == 409


def test_container_inalcancavel_retorna_502_sem_vazar_endereco(client, seed_user, app_settings):
    """Usa `client` (sem `fake_backend`): o resolver padrão aponta para um
    container Docker que não existe, então a chamada de rede falha."""
    instance_id, _ = _create_running_instance(client, seed_user, app_settings, "indisponivel@exemplo.test")

    resp = client.get(f"/i/{instance_id}/echo-headers")

    assert resp.status_code == 502
    assert "wcui" not in resp.text  # não expõe o nome interno do container


def test_timeout_do_cliente_upstream_e_longo_nao_o_padrao_de_5s():
    from app.api.session_proxy import UPSTREAM_TIMEOUT_SECONDS

    assert UPSTREAM_TIMEOUT_SECONDS >= 3600.0


def test_fluxo_continuo_e_entregue_em_varios_pedacos(proxy_client, seed_user, app_settings):
    instance_id, _ = _create_running_instance(proxy_client, seed_user, app_settings, "stream@exemplo.test")

    with proxy_client.stream("GET", f"/i/{instance_id}/stream") as resp:
        assert resp.status_code == 200
        pedacos = list(resp.iter_bytes())

    assert len(pedacos) > 1
    assert b"".join(pedacos) == b"".join(f"chunk-{i}\n".encode() for i in range(5))


def test_websocket_nao_dono_nao_estabelece_canal(proxy_client, seed_user, app_settings):
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    instance_id, _ = _create_running_instance(proxy_client, seed_user, app_settings, "wsdona@exemplo.test")

    with TestClient(proxy_client.app, base_url="http://testserver") as outro:
        _login_as(outro, seed_user, "wsoutro@exemplo.test")
        try:
            with outro.websocket_connect(f"/i/{instance_id}/ws"):
                raise AssertionError("não deveria conseguir conectar")
        except WebSocketDisconnect as exc:
            assert exc.code == 4404


def test_websocket_sem_sessao_nao_estabelece_canal(proxy_client, seed_user, app_settings):
    """Distinto do caso "não é dono" (código 4404): aqui não há sessão
    nenhuma, nem válida nem inválida — o canal deve recusar antes mesmo de
    checar propriedade."""
    from starlette.websockets import WebSocketDisconnect

    instance_id, _ = _create_running_instance(proxy_client, seed_user, app_settings, "wsanon@exemplo.test")
    proxy_client.cookies.clear()

    try:
        with proxy_client.websocket_connect(f"/i/{instance_id}/ws"):
            raise AssertionError("não deveria conseguir conectar sem sessão")
    except WebSocketDisconnect as exc:
        assert exc.code == 4401


def test_websocket_dono_troca_mensagens_nos_dois_sentidos(proxy_client, seed_user, app_settings):
    instance_id, _ = _create_running_instance(proxy_client, seed_user, app_settings, "wsok@exemplo.test")

    with proxy_client.websocket_connect(f"/i/{instance_id}/ws") as ws:
        ws.send_text("ola")
        resposta = ws.receive_text()

    assert resposta == "echo:ola"  # ida (cliente->upstream) e volta (upstream->cliente)


def test_websocket_ocioso_nao_e_encerrado_pela_nossa_propria_politica(
    proxy_client, seed_user, app_settings
):
    """Não dá para esperar 3600s num teste; isto prova a parte testável
    sem esperar tanto: o relay não aplica ping/timeout próprio sobre uma
    conexão sem tráfego (ver `ping_interval=None` em session_proxy.py) —
    o número exato do timeout upstream é coberto à parte, por inspeção."""
    import time

    instance_id, _ = _create_running_instance(proxy_client, seed_user, app_settings, "wsocioso@exemplo.test")

    with proxy_client.websocket_connect(f"/i/{instance_id}/ws") as ws:
        time.sleep(0.3)  # período ocioso, sem nenhuma mensagem
        ws.send_text("ainda-viva")
        assert ws.receive_text() == "echo:ainda-viva"


def test_isolamento_entre_duas_sessoes_simultaneas(proxy_client, seed_user, app_settings):
    from fastapi.testclient import TestClient

    instancia_a, _ = _create_running_instance(proxy_client, seed_user, app_settings, "isoA@exemplo.test")

    with TestClient(proxy_client.app, base_url="http://testserver") as client_b:
        instancia_b, _ = _create_running_instance(
            client_b, seed_user, app_settings, "isoB@exemplo.test", tag="alpine-kde"
        )

        resp_a_tenta_b = proxy_client.get(f"/i/{instancia_b}/echo-headers")
        resp_b_tenta_a = client_b.get(f"/i/{instancia_a}/echo-headers")
        assert resp_a_tenta_b.status_code == 404
        assert resp_b_tenta_a.status_code == 404

        resp_a_na_propria = proxy_client.get(f"/i/{instancia_a}/echo-headers")
        resp_b_na_propria = client_b.get(f"/i/{instancia_b}/echo-headers")
        assert resp_a_na_propria.status_code == resp_b_na_propria.status_code == 200
        assert resp_a_na_propria.json()["instance_id"] == instancia_a
        assert resp_b_na_propria.json()["instance_id"] == instancia_b

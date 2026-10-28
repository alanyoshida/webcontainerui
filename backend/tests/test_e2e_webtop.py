"""Teste de ponta a ponta com Docker real e uma imagem webtop real.

Opt-in (`pytest -m e2e`): baixa uma imagem de alguns gigabytes na primeira
execução e precisa de um daemon Docker acessível. Não roda na suíte
padrão (ver pyproject.toml — `addopts = "-m 'not e2e'"`), exatamente para
que o resto da suíte não dependa de Docker (D7 em design.md).
"""

import pytest

from app.config import Settings
from app.db import connect
from app.main import create_app
from fastapi.testclient import TestClient

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image, insert_user

pytestmark = pytest.mark.e2e

_IMAGE_REPOSITORY = "lscr.io/linuxserver/webtop"
_IMAGE_TAG = "latest"  # XFCE sobre Alpine — a variante padrão documentada


@pytest.fixture
def e2e_app_settings(tmp_path):
    return Settings(
        db_path=tmp_path / "e2e.db",
        uploads_dir=tmp_path / "uploads",
        docker_network="bridge",  # sem rede dedicada criada neste teste isolado
    )


async def test_dono_alcanca_a_sessao_e_outro_usuario_nao(e2e_app_settings):
    """Sobe um webtop real, confirma que o dono alcança `/i/<id>/` e que
    outro usuário autenticado recebe 404 — a prova de ponta a ponta do
    requisito central do produto (isolamento entre usuários).

    `runtime` não é passado para `create_app`: o `AioDockerContainerRuntime`
    padrão é construído dentro do `lifespan`, no mesmo event loop que o
    `TestClient` usa para rodar a app (sua própria thread/portal) — construir
    um à parte, numa fixture, prendia o conector aiohttp a outro loop e
    quebrava com "attached to a different loop" (o mesmo tipo de bug já
    corrigido em `main.py`, ver D3/D7 em design.md).

    O pull de verdade acontece aqui, com um runtime à parte e descartado
    logo em seguida (nunca entregue à app, então sem o problema de loop
    acima): `create_container` não baixa sob demanda — o fluxo real é o
    catálogo do admin pré-puxar (já coberto com runtime falso em
    test_image_catalog.py); aqui só se garante que a imagem existe
    localmente antes de pedir a criação da instância.
    """
    from app.db import init_db
    from app.runtime.docker_runtime import AioDockerContainerRuntime
    from app.services.passwords import hash_password

    pull_runtime = AioDockerContainerRuntime()
    async for _ in pull_runtime.pull_image(_IMAGE_REPOSITORY, _IMAGE_TAG):
        pass
    await pull_runtime.close()

    conn = connect(e2e_app_settings.db_path)
    init_db(conn)
    dono_id = insert_user(conn, "dono-e2e@exemplo.test")
    outro_id = insert_user(conn, "outro-e2e@exemplo.test")
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id IN (?, ?)",
        (hash_password("senha-e2e-123456"), dono_id, outro_id),
    )
    image_id = insert_image(conn, repository=_IMAGE_REPOSITORY, tag=_IMAGE_TAG)
    group_id = insert_group(conn)
    add_user_to_group(conn, dono_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    app = create_app(e2e_app_settings)
    with TestClient(app, base_url="http://testserver") as client:
        login = client.post(
            "/api/auth/login", json={"email": "dono-e2e@exemplo.test", "password": "senha-e2e-123456"}
        )
        assert login.status_code == 200

        criada = client.post("/api/instances", json={"image_id": image_id})
        assert criada.status_code == 201, criada.text
        body = criada.json()
        assert body["state"] == "running", body.get("error_message")
        instance_id = body["id"]
        dono_cookies = dict(client.cookies)  # capturado já aqui: o finally precisa dele mesmo se o try falhar cedo

        # Tudo que segue, até o fim da função, fica sob este try/finally:
        # um container real foi criado agora, e qualquer exceção daqui em
        # diante — inclusive na resolução de IP abaixo — não pode pular
        # a limpeza, ou o container/volume ficam órfãos no Docker de
        # verdade (como aconteceu numa iteração anterior deste teste,
        # quando a resolução de IP ainda estava fora do try/finally).
        try:
            # Em produção o portal roda dentro da mesma rede Docker do
            # container e resolve por nome (D1/D2 em design.md); este
            # teste roda o portal como processo solto no host, sem
            # acesso ao DNS interno do Docker. Para exercitar o proxy de
            # verdade mesmo assim, aponta o resolver para o IP do
            # container na rede bridge, que o host alcança diretamente.
            import aiodocker

            conn2 = connect(e2e_app_settings.db_path)
            container_id = conn2.execute(
                "SELECT container_id FROM instances WHERE id = ?", (instance_id,)
            ).fetchone()["container_id"]
            conn2.close()

            inspector = aiodocker.Docker()
            info = await inspector.containers.container(container_id).show()
            # O IP de nível superior (NetworkSettings.IPAddress) só é
            # preenchido para o modo de rede legado; com rede nomeada
            # (mesmo "bridge" explícito), o IP mora em Networks.<nome>.
            ip = info["NetworkSettings"]["Networks"][e2e_app_settings.docker_network]["IPAddress"]
            await inspector.close()
            app.state.backend_resolver = lambda row, _ip=ip: f"http://{_ip}:3000"

            # O container acabou de iniciar: o Nginx/Selkies interno leva
            # alguns segundos para aceitar conexões. 502 nesta janela é
            # "ainda não subiu", não "inalcançável" — espera curta antes
            # de considerar falha de verdade.
            import time

            resp_dono = None
            for _ in range(15):
                resp_dono = client.get(f"/i/{instance_id}/")
                if resp_dono.status_code != 502:
                    break
                time.sleep(2)

            # o Selkies real serve HTML, não necessariamente 200 na raiz
            # sem credencial de sessão de cliente; o que importa aqui é
            # que o proxy ALCANÇOU o container, não um 502/404.
            assert resp_dono.status_code != 502
            assert resp_dono.status_code != 404

            # Um segundo `TestClient(app)` aninhado sobre o MESMO `app`
            # dispararia o shutdown do lifespan inteiro ao sair do `with`
            # — fechando a sessão aiodocker que a limpeza no `finally`
            # ainda precisa. Troca de cookies no mesmo cliente evita isso
            # sem precisar de uma segunda app.
            client.cookies.clear()
            login_outro = client.post(
                "/api/auth/login",
                json={"email": "outro-e2e@exemplo.test", "password": "senha-e2e-123456"},
            )
            assert login_outro.status_code == 200
            resp_outro = client.get(f"/i/{instance_id}/")
            assert resp_outro.status_code == 404
        finally:
            client.cookies.clear()
            for name, value in dono_cookies.items():
                client.cookies.set(name, value)
            client.delete(f"/api/instances/{instance_id}?confirm=true")

"""Testes de API da biblioteca de servidores MCP, do vínculo com imagens e
da propagação reportada nas respostas (tarefas 3.2, 3.3, 3.4, 4.2, 4.3 e 8.2)."""

import json

from app.db import connect
from app.services.instances import create_instance
from app.services.mcp_servers import create_mcp_server, link_mcp_server

from .conftest import insert_image, insert_user


def _login_admin(client, seed_user, email="admin@exemplo.test", password="senha-admin-123"):
    seed_user(email, password, is_admin=True)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


def _login_comum(client, seed_user, email="comum@exemplo.test", password="senha-usuario-123"):
    seed_user(email, password)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


def _agent_image_id(conn, repository: str = "wcui-agent-claude-code") -> int:
    """Id da imagem de agente já semeada pelo lifespan do app — pronta para
    uso (o build de fundo da seed é irrelevante para estes testes)."""
    row = conn.execute("SELECT id FROM images WHERE repository = ?", (repository,)).fetchone()
    conn.execute("UPDATE images SET pull_state = 'ready', enabled = 1 WHERE id = ?", (row[0],))
    return row[0]


async def _seed_live_instance(conn, fake_runtime, app_settings, image_id: int) -> str:
    """Instância viva real (via serviço), com container no runtime fake."""
    user_id = insert_user(conn)
    from .conftest import add_user_to_group, grant_image_to_group, insert_group

    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    instance = await create_instance(conn, fake_runtime, app_settings, user_id, image_id)
    return instance["id"]


def test_admin_cria_lista_e_edita_mcp(client, seed_user):
    _login_admin(client, seed_user)

    criado = client.post(
        "/api/admin/mcp-servers",
        json={
            "display_name": "Contexto",
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "mcp-server"],
            "env": {"API_KEY": "segredo-123"},
        },
    )
    assert criado.status_code == 201
    mcp = criado.json()
    assert mcp["transport"] == "stdio"
    assert mcp["args"] == ["-y", "mcp-server"]
    assert mcp["env_keys"] == ["API_KEY"]  # só as chaves, nunca os valores
    assert "segredo-123" not in criado.text

    mcp_id = mcp["id"]
    editado = client.patch(
        f"/api/admin/mcp-servers/{mcp_id}", json={"display_name": "Contexto v2"}
    )
    assert editado.status_code == 200
    corpo = editado.json()
    assert corpo["server"]["display_name"] == "Contexto v2"
    assert corpo["server"]["command"] == "npx"  # intacto
    assert corpo["propagation_failures"] == []
    assert corpo["schema_validation_errors"] == []

    lista = client.get("/api/admin/mcp-servers")
    assert [m["display_name"] for m in lista.json()] == ["Contexto v2"]


def test_segredo_de_header_so_expoe_chaves(client, seed_user):
    _login_admin(client, seed_user)

    criado = client.post(
        "/api/admin/mcp-servers",
        json={
            "display_name": "Remoto",
            "transport": "http",
            "url": "https://mcp.test",
            "headers": {"Authorization": "Bearer abc-123"},
        },
    )

    assert criado.status_code == 201
    assert criado.json()["headers_keys"] == ["Authorization"]
    assert "abc-123" not in criado.text


def test_usuario_comum_nao_gerencia_mcps(client, seed_user):
    _login_comum(client, seed_user)

    assert client.get("/api/admin/mcp-servers").status_code == 403
    assert (
        client.post(
            "/api/admin/mcp-servers",
            json={"display_name": "X", "transport": "stdio", "command": "npx"},
        ).status_code
        == 403
    )


def test_cadastro_invalido_retorna_400_e_duplicado_409(client, seed_user):
    _login_admin(client, seed_user)

    assert (
        client.post(
            "/api/admin/mcp-servers",
            json={"display_name": "X", "transport": "stdio"},
        ).status_code
        == 400
    )
    client.post(
        "/api/admin/mcp-servers",
        json={"display_name": "X", "transport": "stdio", "command": "npx"},
    )
    assert (
        client.post(
            "/api/admin/mcp-servers",
            json={"display_name": "X", "transport": "stdio", "command": "outro"},
        ).status_code
        == 409
    )


def test_remocao_de_inexistente_e_404(client, seed_user):
    _login_admin(client, seed_user)
    assert client.delete("/api/admin/mcp-servers/999").status_code == 404


def test_vinculo_e_desvinculo_via_api_com_imagem_de_build(
    client, seed_user, app_settings
):
    _login_admin(client, seed_user)
    conn = connect(app_settings.db_path)
    image_id = _agent_image_id(conn, "wcui-agent-claude-code")
    conn.close()

    mcp_id = client.post(
        "/api/admin/mcp-servers",
        json={"display_name": "Local", "transport": "stdio", "command": "npx"},
    ).json()["id"]

    vinculo = client.post(f"/api/admin/mcp-servers/images/{image_id}/servers/{mcp_id}")
    assert vinculo.status_code == 200
    corpo = vinculo.json()
    assert corpo["mcp_server_ids"] == [mcp_id]
    assert corpo["propagation_failures"] == []
    assert corpo["schema_validation_errors"] == []

    listagem = client.get("/api/admin/mcp-servers")
    assert listagem.json()[0]["linked_images"] == 1  # contador por MCP

    imagens = client.get("/api/admin/mcp-servers/images")
    assert imagens.json()[0]["mcp_server_ids"] == [mcp_id]  # vínculo por imagem

    desvinculo = client.delete(f"/api/admin/mcp-servers/images/{image_id}/servers/{mcp_id}")
    assert desvinculo.status_code == 200
    assert desvinculo.json()["mcp_server_ids"] == []


def test_vinculo_a_imagem_pull_e_recusado(client, seed_user, app_settings):
    _login_admin(client, seed_user)
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn, repository="linuxserver/webtop", provision_kind="pull")
    conn.close()

    mcp_id = client.post(
        "/api/admin/mcp-servers",
        json={"display_name": "Local", "transport": "stdio", "command": "npx"},
    ).json()["id"]

    resp = client.post(f"/api/admin/mcp-servers/images/{image_id}/servers/{mcp_id}")
    assert resp.status_code == 400


async def test_remocao_via_api_desvincula_e_propaga(
    client, seed_user, app_settings, fake_runtime
):
    """Tarefa 3.2: remover um MCP vinculado a 2 imagens desvincula de ambas
    e propaga a reescrita às instâncias vivas delas."""
    _login_admin(client, seed_user)
    conn = connect(app_settings.db_path)
    image_1 = _agent_image_id(conn, "wcui-agent-claude-code")
    image_2 = _agent_image_id(conn, "wcui-agent-oh-my-pi")
    mcp_id = create_mcp_server(conn, "Local", "stdio", settings=app_settings, command="npx")
    link_mcp_server(conn, image_1, mcp_id)
    link_mcp_server(conn, image_2, mcp_id)
    await _seed_live_instance(conn, fake_runtime, app_settings, image_1)
    conn.close()

    resp = client.delete(f"/api/admin/mcp-servers/{mcp_id}")

    assert resp.status_code == 200
    assert resp.json()["propagation_failures"] == []
    assert resp.json()["schema_validation_errors"] == []
    conn = connect(app_settings.db_path)
    vinculos = dict(conn.execute("SELECT image_id, COUNT(*) FROM image_mcp_servers GROUP BY image_id"))
    conn.close()
    assert vinculos == {}  # cascade nas duas imagens
    # A instância viva da image_1 recebeu a reescrita (sem o MCP).
    arquivos = [f for files in fake_runtime._files.values() for f in files]
    assert "/config/.claude.json" in arquivos


async def test_resposta_de_vinculo_revela_quebra_de_contrato_nomeando_campo(
    client, seed_user, app_settings, fake_runtime
):
    """Tarefa 8.2: vincular um MCP com campo inválido numa imagem com
    instância viva relata a quebra nomeando o MCP e o campo."""
    _login_admin(client, seed_user)
    conn = connect(app_settings.db_path)
    image_id = _agent_image_id(conn, "wcui-agent-claude-code")
    mcp_id = create_mcp_server(
        conn, "Quebrado", "stdio", settings=app_settings, command="npx", args=["-y"]
    )
    conn.execute("UPDATE mcp_servers SET args_json = '\"texto\"' WHERE id = ?", (mcp_id,))
    await _seed_live_instance(conn, fake_runtime, app_settings, image_id)
    conn.close()

    resp = client.post(f"/api/admin/mcp-servers/images/{image_id}/servers/{mcp_id}")

    assert resp.status_code == 200
    erros = resp.json()["schema_validation_errors"]
    assert len(erros) == 1
    assert erros[0]["error"] == "MCP 'Quebrado': campo 'args': 'texto' is not of type 'array'"
    assert erros[0]["instance_id"]


def test_get_admin_mcp_servers_responde_200_autenticado(client, seed_user):
    _login_admin(client, seed_user)
    assert client.get("/api/admin/mcp-servers").status_code == 200


def test_listagem_tolera_linha_com_args_corrompido(client, seed_user, app_settings):
    """Um cadastro com args_json inválido (corrompido fora do portal, ou
    quebra futura) não pode derrubar a listagem inteira com 500 — a linha
    volta com args vazio, mesmo isolamento de MCP malformado do resto."""
    _login_admin(client, seed_user)
    conn = connect(app_settings.db_path)
    mcp_ok = conn.execute(
        "INSERT INTO mcp_servers (display_name, transport, command) VALUES ('Ok', 'stdio', 'npx')"
    ).lastrowid
    mcp_ruim = conn.execute(
        "INSERT INTO mcp_servers (display_name, transport, command, args_json) VALUES ('Ruim', 'stdio', 'python', '\"texto\"')"
    ).lastrowid
    conn.execute("UPDATE mcp_servers SET env_encrypted = X'00FF' WHERE id = ?", (mcp_ok,))
    conn.close()

    resp = client.get("/api/admin/mcp-servers")

    assert resp.status_code == 200
    por_nome = {m["display_name"]: m for m in resp.json()}
    assert por_nome["Ruim"]["args"] == []
    assert por_nome["Ok"]["env_keys"] == []  # blob ilegível isolado

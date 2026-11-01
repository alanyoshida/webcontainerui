"""Testes da injeção de MCPs na criação da instância (tarefas 9.1 e 9.2):
mesmo ponto da identidade SSH e do AGENTS.md, best-effort, com quebra de
contrato registrada em `instances.mcp_validation_errors`."""

import json

from app.db import connect
from app.runtime.errors import RuntimeOperationError
from app.services.mcp_servers import create_mcp_server, link_mcp_server

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_user


def _login(client, seed_user, email, password="senha-usuario-123"):
    seed_user(email, password)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["id"]


def _config_of(fake_runtime, container_id: str):
    files = fake_runtime._files.get(container_id, {})
    raw = files.get("/config/.claude.json")
    return json.loads(raw) if raw else None


async def test_criacao_de_instancia_injeta_mcps_vinculados(
    client, seed_user, app_settings, fake_runtime
):
    user_id = _login(client, seed_user, "mcp-injeta@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = conn.execute(
        "SELECT id FROM images WHERE repository = 'wcui-agent-claude-code'"
    ).fetchone()[0]
    conn.execute("UPDATE images SET pull_state = 'ready', enabled = 1 WHERE id = ?", (image_id,))
    mcp_id = create_mcp_server(
        conn, "Local", "stdio", settings=app_settings, command="npx", args=["-y", "pkg"]
    )
    link_mcp_server(conn, image_id, mcp_id)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)

    criada = client.post("/api/instances", json={"image_id": image_id})

    assert criada.status_code == 201
    assert criada.json()["state"] == "running"
    container_id = criada.json()["container_id"] if "container_id" in criada.json() else None
    conn2 = connect(app_settings.db_path)
    container_id = conn2.execute(
        "SELECT container_id FROM instances WHERE id = ?", (criada.json()["id"],)
    ).fetchone()[0]
    conn2.close()

    config = _config_of(fake_runtime, container_id)
    assert config is not None
    assert set(config["mcpServers"]) == {"Local"}
    assert criada.json()["mcp_validation_errors"] == []


async def test_quebra_de_contrato_na_criacao_fica_registrada_para_o_admin(
    client, seed_user, app_settings, fake_runtime
):
    """Tarefa 9.1: MCP com campo inválido é escrito e a quebra fica
    registrada na instância, consultável pela listagem."""
    user_id = _login(client, seed_user, "mcp-quebra@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = conn.execute(
        "SELECT id FROM images WHERE repository = 'wcui-agent-claude-code'"
    ).fetchone()[0]
    conn.execute("UPDATE images SET pull_state = 'ready', enabled = 1 WHERE id = ?", (image_id,))
    mcp_id = create_mcp_server(
        conn, "Quebrado", "stdio", settings=app_settings, command="npx", args=["-y"]
    )
    conn.execute("UPDATE mcp_servers SET args_json = '\"texto\"' WHERE id = ?", (mcp_id,))
    link_mcp_server(conn, image_id, mcp_id)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)

    criada = client.post("/api/instances", json={"image_id": image_id})

    assert criada.status_code == 201
    assert criada.json()["mcp_validation_errors"] == [
        "MCP 'Quebrado': campo 'args': 'texto' is not of type 'array'"
    ]
    conn2 = connect(app_settings.db_path)
    container_id = conn2.execute(
        "SELECT container_id FROM instances WHERE id = ?", (criada.json()["id"],)
    ).fetchone()[0]
    conn2.close()
    config = _config_of(fake_runtime, container_id)
    assert "Quebrado" in config["mcpServers"]  # escrito mesmo com quebra


async def test_falha_de_injecao_nao_impede_instancia_de_ficar_pronta(
    client, seed_user, app_settings, fake_runtime
):
    """Tarefa 9.2: erro no runtime durante a injeção de MCP não derruba a
    criação — a instância termina running, sem config de MCP."""
    user_id = _login(client, seed_user, "mcp-falha@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = conn.execute(
        "SELECT id FROM images WHERE repository = 'wcui-agent-claude-code'"
    ).fetchone()[0]
    conn.execute("UPDATE images SET pull_state = 'ready', enabled = 1 WHERE id = ?", (image_id,))
    mcp_id = create_mcp_server(conn, "Local", "stdio", settings=app_settings, command="npx")
    link_mcp_server(conn, image_id, mcp_id)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    fake_runtime.fail_next("get_archive", RuntimeOperationError("docker indisponível"))

    criada = client.post("/api/instances", json={"image_id": image_id})

    assert criada.status_code == 201
    assert criada.json()["state"] == "running"
    assert criada.json()["mcp_validation_errors"] == []
    conn2 = connect(app_settings.db_path)
    container_id = conn2.execute(
        "SELECT container_id FROM instances WHERE id = ?", (criada.json()["id"],)
    ).fetchone()[0]
    conn2.close()
    assert _config_of(fake_runtime, container_id) is None


async def test_instancia_sem_mcp_vinculado_nao_escreve_nada(
    client, seed_user, app_settings, fake_runtime
):
    user_id = _login(client, seed_user, "mcp-vazio@exemplo.test")
    conn = connect(app_settings.db_path)
    image_id = conn.execute(
        "SELECT id FROM images WHERE repository = 'wcui-agent-claude-code'"
    ).fetchone()[0]
    conn.execute("UPDATE images SET pull_state = 'ready', enabled = 1 WHERE id = ?", (image_id,))
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    criada = client.post("/api/instances", json={"image_id": image_id})

    assert criada.status_code == 201
    conn2 = connect(app_settings.db_path)
    container_id = conn2.execute(
        "SELECT container_id FROM instances WHERE id = ?", (criada.json()["id"],)
    ).fetchone()[0]
    conn2.close()
    # "Sempre recomputa": mesmo sem MCP vinculado o estado converge para a
    # chave vazia (design.md), sem tocar nas demais chaves do arquivo.
    assert _config_of(fake_runtime, container_id) == {"mcpServers": {}}

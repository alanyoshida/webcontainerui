"""Testes dos tradutores de MCP, do merge nos arquivos nativos e da
validação de schema pós-escrita (tarefas 6 e 7 da change)."""

import json

from app.services.mcp_tool_configs import (
    CONFIG_PATHS,
    HERMES_ENV_PATH,
    MCP_JSON_SCHEMAS,
    build_archive,
    extract_mcp_payload,
    merge_json,
    merge_yaml,
    tool_for_image,
    translate_servers,
    validate_tool_config,
)

import pytest


# ---------------------------------------------------------------- helpers

def _stdio(nome="Local", **overrides):
    server = {
        "display_name": nome,
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "pkg"],
        "url": None,
        "env": {"API_KEY": "segredo-123"},
        "headers": {},
        "enabled": True,
    }
    server.update(overrides)
    return server


def _remote(nome="Remoto", transport="http", **overrides):
    server = {
        "display_name": nome,
        "transport": transport,
        "command": None,
        "args": [],
        "url": "https://mcp.test/sse",
        "env": {},
        "headers": {"Authorization": "Bearer abc-123"},
        "enabled": True,
    }
    server.update(overrides)
    return server


# ------------------------------------------------- tarefa 6.1: merge JSON

def test_merge_json_preserva_chaves_pre_existentes():
    atual = json.dumps(
        {"mcpServers": {"antigo": {"command": "x"}}, "outraChave": {"estado": 1}}
    ).encode()

    novo = merge_json(atual, "claude-code", {"novo": {"type": "stdio", "command": "npx"}})
    documento = json.loads(novo)

    assert documento["outraChave"] == {"estado": 1}  # sobrevive
    assert set(documento["mcpServers"]) == {"novo"}  # chave substituída por completo


def test_merge_json_parte_de_vazio_quando_arquivo_nao_existe():
    novo = merge_json(None, "agy", {"srv": {"command": "npx"}})

    assert json.loads(novo) == {"mcpServers": {"srv": {"command": "npx"}}}


def test_merge_json_tolerante_a_comentarios_jsonc_do_opencode():
    atual = (
        "{\n"
        '  // comentário de linha\n'
        '  "theme": "dark", /* comentário de bloco */\n'
        '  "mcp": {"antigo": {"type": "local", "command": ["x"]}}\n'
        "}\n"
    ).encode()

    novo = merge_json(atual, "opencode", {"novo": {"type": "local", "command": ["npx"]}})
    documento = json.loads(novo)

    assert documento["theme"] == "dark"
    assert set(documento["mcp"]) == {"novo"}


# ------------------------------------------------- tarefa 6.2: merge YAML

def test_merge_yaml_preserva_comentarios_e_chaves_do_hermes():
    atual = (
        "# documentação do hermes\n"
        "_config_version: 3\n"
        "fallback_model: gpt-x\n"
        "# fallback_model: gpt-y  (comentado)\n"
        "mcp_servers:\n"
        "  antigo:\n"
        "    command: x\n"
    ).encode()

    novo = merge_yaml(atual, "hermes", {"novo": {"command": "npx", "enabled": True}})
    texto = novo.decode()

    assert "_config_version: 3" in texto
    assert "fallback_model: gpt-x" in texto
    assert "# fallback_model: gpt-y  (comentado)" in texto  # comentário sobrevive
    assert "# documentação do hermes" in texto
    assert "antigo" not in texto
    assert "command: npx" in texto


def test_merge_yaml_parte_de_vazio_quando_arquivo_nao_existe():
    novo = merge_yaml(None, "hermes", {"srv": {"command": "npx"}})

    assert "command: npx" in novo.decode()


# --------------------------------------------- tarefa 6.3: os 5 tradutores

def test_tradutor_claude_code():
    payload = translate_servers(
        "claude-code", [_stdio(), _remote(transport="sse")]
    )

    assert payload == {
        "Local": {"type": "stdio", "command": "npx", "args": ["-y", "pkg"], "env": {"API_KEY": "segredo-123"}},
        "Remoto": {"type": "sse", "url": "https://mcp.test/sse", "headers": {"Authorization": "Bearer abc-123"}},
    }


def test_tradutor_opencode_combina_comando_e_args_em_array():
    payload = translate_servers("opencode", [_stdio(), _remote()])

    assert payload["Local"] == {
        "type": "local",
        "command": ["npx", "-y", "pkg"],
        "environment": {"API_KEY": "segredo-123"},
    }
    assert payload["Remoto"] == {
        "type": "remote",
        "url": "https://mcp.test/sse",
        "headers": {"Authorization": "Bearer abc-123"},
    }


def test_tradutor_agy_usa_serverUrl_e_disabled():
    payload = translate_servers(
        "agy", [_stdio(), _remote(), _stdio("Off", enabled=False)]
    )

    assert payload["Local"] == {
        "command": "npx",
        "args": ["-y", "pkg"],
        "env": {"API_KEY": "segredo-123"},
        "disabled": False,
    }
    assert payload["Remoto"] == {
        "serverUrl": "https://mcp.test/sse",
        "headers": {"Authorization": "Bearer abc-123"},
        "disabled": False,
    }
    assert payload["Off"]["disabled"] is True  # desativado entra marcado


def test_tradutor_hermes_manda_segredo_para_o_env():
    payload, env_content = translate_servers(
        "hermes", [_stdio("Local"), _remote("Remoto"), _remote("SSE", transport="sse")]
    )

    assert payload["Local"] == {
        "command": "npx",
        "args": ["-y", "pkg"],
        "env": {"API_KEY": "segredo-123"},
        "enabled": True,
    }
    # O segredo do header nunca fica no YAML — vai a referência da tabela:
    assert payload["Remoto"] == {
        "url": "https://mcp.test/sse",
        "headers": {"Authorization": "Bearer ${MCP_REMOTO_API_KEY}"},
        "enabled": True,
    }
    assert payload["SSE"]["headers"] == {"Authorization": "Bearer ${MCP_SSE_API_KEY}"}
    assert env_content == "MCP_REMOTO_API_KEY=abc-123\nMCP_SSE_API_KEY=abc-123\n"
    assert "abc-123" not in json.dumps(payload)


def test_tradutor_oh_my_pi_usa_campo_transport():
    payload = translate_servers(
        "oh-my-pi", [_stdio(), _remote(transport="sse")]
    )

    assert payload["Local"] == {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "pkg"],
        "env": {"API_KEY": "segredo-123"},
        "disabled": False,
    }
    assert payload["Remoto"] == {
        "transport": "sse",
        "url": "https://mcp.test/sse",
        "headers": {"Authorization": "Bearer abc-123"},
        "disabled": False,
    }


def test_claude_code_e_opencode_omitiram_mcp_desativado():
    """As duas ferramentas sem campo de desativação no contrato confirmado
    não recebem o servidor desativado — incluir sem marcador seria ativá-lo."""

    for tool in ("claude-code", "opencode"):
        payload = translate_servers(tool, [_stdio("On"), _stdio("Off", enabled=False)])
        assert set(payload) == {"On"}


def test_caminhos_de_config_cobrem_as_5_ferramentas():
    assert set(CONFIG_PATHS) == {"claude-code", "opencode", "agy", "hermes", "oh-my-pi"}
    assert HERMES_ENV_PATH == "/config/.hermes/.env"


def test_tool_for_image_mapeia_pelo_repositorio(db_conn):
    from .conftest import insert_image

    image_id = insert_image(db_conn, repository="wcui-agent-claude-code", provision_kind="build")
    from app.services.images import get_image

    assert tool_for_image(get_image(db_conn, image_id)) == "claude-code"
    assert tool_for_image({"repository": "linuxserver/webtop"}) is None


# --------------------------------- tarefa 6.4: isolamento de falha por MCP

@pytest.mark.parametrize(
    "quebrado",
    [
        _stdio("Quebrado", command=None),  # stdio sem comando
        _stdio("Quebrado", transport="websocket"),  # transporte desconhecido
        _stdio("Quebrado", display_name=""),  # sem nome
    ],
)
def test_mcp_malformado_nao_derruba_os_demais(quebrado):
    payload = translate_servers("claude-code", [_stdio("Bom"), quebrado])

    assert set(payload) == {"Bom"}


# ----------------------------- tarefa 7.2: schemas + 7.3: validate_tool_config

def test_schema_valido_e_invalido_por_ferramenta():
    casos = {
        "claude-code": ({"s": {"type": "stdio", "command": "npx"}}, {"s": {"type": "stdio"}}),
        "opencode": ({"s": {"type": "remote", "url": "https://x"}}, {"s": {"type": "local", "command": []}}),
        "agy": ({"s": {"command": "npx"}}, {"s": {"args": ["-y"]}}),
        "hermes": ({"s": {"url": "https://x", "enabled": True}}, {"s": {"headers": {}}}),
        "oh-my-pi": (
            {"s": {"transport": "http", "url": "https://x"}},
            {"s": {"transport": "stdio", "args": ["x"]}},
        ),
    }
    for tool, (valido, invalido) in casos.items():
        assert validate_tool_config(valido, MCP_JSON_SCHEMAS[tool]) == [], tool
        erros = validate_tool_config(invalido, MCP_JSON_SCHEMAS[tool])
        assert erros and all(e.startswith("MCP 's':") for e in erros), tool


def test_validate_tool_config_nomeia_o_campo_ausente():
    erros = validate_tool_config(
        {"minha-skill": {"type": "stdio", "args": ["-y"]}},
        MCP_JSON_SCHEMAS["claude-code"],
    )

    assert erros == ["MCP 'minha-skill': campo 'command' obrigatório ausente"]


def test_validate_tool_config_nomeia_o_campo_com_valor_errado():
    erros = validate_tool_config(
        {"srv": {"type": "stdio", "command": 123}},
        MCP_JSON_SCHEMAS["claude-code"],
    )

    assert len(erros) == 1
    assert erros[0].startswith("MCP 'srv': campo 'command':")


# ----------------------------------------------------------- helpers tar

def test_build_archive_round_trip(tmp_path):
    import io
    import tarfile

    tar_bytes = build_archive("mcp.json", b'{"a": 1}')
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        member = tar.getmember("mcp.json")
        assert member.size == len(b'{"a": 1}')
        assert tar.extractfile("mcp.json").read() == b'{"a": 1}'


def test_extract_mcp_payload_json_e_yaml():
    json_doc = merge_json(None, "oh-my-pi", {"s": {"command": "npx"}})
    assert extract_mcp_payload(json_doc, "oh-my-pi") == {"s": {"command": "npx"}}

    yaml_doc = merge_yaml(None, "hermes", {"s": {"command": "npx"}})
    assert extract_mcp_payload(yaml_doc, "hermes") == {"s": {"command": "npx"}}

    assert extract_mcp_payload(b"", "claude-code") == {}

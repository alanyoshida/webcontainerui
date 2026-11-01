"""Tradução da biblioteca de MCP para o formato nativo de cada ferramenta.

Cada uma das 5 imagens de agente lê seus servidores MCP de um arquivo
próprio (tabela de contrato confirmada em design.md). Este módulo traduz a
lista resolvida de MCPs (`mcp_servers.resolve_image_mcp_servers`) para o
objeto que cada ferramenta espera e faz o **merge** dele no arquivo dentro
do container — nunca sobrescrevendo o arquivo inteiro, que guarda outro
estado da ferramenta (sessão, migração, outras configurações).

A validação pós-escrita (JSON Schema por ferramenta, tarefa 7) também vive
aqui: depois de gravar, o arquivo é lido de volta e a chave de MCP é
conferida contra o contrato da ferramenta, para que um bug de tradução ou
uma mudança de versão dela nunca passe em silêncio.
"""

from __future__ import annotations

import io
import json
import re
import sqlite3
import tarfile
import time
from typing import Callable

import jsonschema
from ruamel.yaml import YAML

# Ferramenta -> imagem (prefixo do repositório no catálogo). A escolha do
# tradutor é pelo repositório da imagem (`images.repository`), que é como
# as 5 imagens de agente nascem no seed (`agent_images.AGENT_IMAGES`).
TOOL_BY_REPOSITORY: dict[str, str] = {
    "wcui-agent-claude-code": "claude-code",
    "wcui-agent-opencode": "opencode",
    "wcui-agent-agy": "agy",
    "wcui-agent-hermes": "hermes",
    "wcui-agent-oh-my-pi": "oh-my-pi",
}

# Arquivo nativo de cada ferramenta, dentro do volume montado em /config
# (HOME das imagens de agente é /config — ver `_base/Dockerfile`).
CONFIG_PATHS: dict[str, str] = {
    "claude-code": "/config/.claude.json",
    "opencode": "/config/.config/opencode/opencode.jsonc",
    "agy": "/config/.gemini/config/mcp_config.json",
    "hermes": "/config/.hermes/config.yaml",
    "oh-my-pi": "/config/.omp/agent/mcp.json",
}

HERMES_ENV_PATH = "/config/.hermes/.env"

# Chave de MCP no arquivo de cada ferramenta.
MCP_KEYS: dict[str, str] = {
    "claude-code": "mcpServers",
    "opencode": "mcp",
    "agy": "mcpServers",
    "hermes": "mcp_servers",
    "oh-my-pi": "mcpServers",
}

MCP_JSON_SCHEMAS: dict[str, dict] = {
    # `additionalProperties` no lugar de `properties`: o nome da chave de
    # cada servidor é livre (é o display_name), o contrato está no objeto
    # de baixo. Mesmo molde do exemplo de design.md.
    "claude-code": {
        "type": "object",
        "$defs": {
            "stdio": {
                "properties": {
                    "type": {"const": "stdio"},
                    "command": {"type": "string"},
                    "args": {"type": "array"},
                    "env": {"type": "object"},
                },
                "required": ["type", "command"],
            },
            "remote": {
                "properties": {
                    "type": {"enum": ["http", "sse"]},
                    "url": {"type": "string"},
                    "headers": {"type": "object"},
                },
                "required": ["type", "url"],
            },
        },
        "additionalProperties": {
            "type": "object",
            "oneOf": [
                {"$ref": "#/$defs/stdio"},
                {"$ref": "#/$defs/remote"},
            ],
        },
    },
    "opencode": {
        "type": "object",
        "$defs": {
            "local": {
                "properties": {
                    "type": {"const": "local"},
                    "command": {"type": "array", "minItems": 1},
                    "environment": {"type": "object"},
                },
                "required": ["type", "command"],
            },
            "remote": {
                "properties": {
                    "type": {"const": "remote"},
                    "url": {"type": "string"},
                    "headers": {"type": "object"},
                },
                "required": ["type", "url"],
            },
        },
        "additionalProperties": {
            "type": "object",
            "oneOf": [
                {"$ref": "#/$defs/local"},
                {"$ref": "#/$defs/remote"},
            ],
        },
    },
    "agy": {
        "type": "object",
        "$defs": {
            # Sem campo de tipo: stdio e remoto se distinguem pela presença
            # de `command` ou `serverUrl`.
            "stdio": {
                "properties": {
                    "command": {"type": "string"},
                    "args": {"type": "array"},
                    "env": {"type": "object"},
                    "disabled": {"type": "boolean"},
                },
                "required": ["command"],
            },
            "remote": {
                "properties": {
                    "serverUrl": {"type": "string"},
                    "headers": {"type": "object"},
                    "disabled": {"type": "boolean"},
                },
                "required": ["serverUrl"],
            },
        },
        "additionalProperties": {
            "type": "object",
            "oneOf": [
                {"$ref": "#/$defs/stdio"},
                {"$ref": "#/$defs/remote"},
            ],
        },
    },
    "hermes": {
        "type": "object",
        "$defs": {
            "stdio": {
                "properties": {
                    "command": {"type": "string"},
                    "args": {"type": "array"},
                    "env": {"type": "object"},
                    "enabled": {"type": "boolean"},
                },
                "required": ["command"],
            },
            "remote": {
                "properties": {
                    "url": {"type": "string"},
                    "headers": {"type": "object"},
                    "enabled": {"type": "boolean"},
                },
                "required": ["url"],
            },
        },
        "additionalProperties": {
            "type": "object",
            "oneOf": [
                {"$ref": "#/$defs/stdio"},
                {"$ref": "#/$defs/remote"},
            ],
        },
    },
    "oh-my-pi": {
        "type": "object",
        "$defs": {
            "stdio": {
                "properties": {
                    "transport": {"const": "stdio"},
                    "command": {"type": "string"},
                    "args": {"type": "array"},
                    "env": {"type": "object"},
                    "disabled": {"type": "boolean"},
                },
                "required": ["transport", "command"],
            },
            "remote": {
                "properties": {
                    "transport": {"enum": ["http", "sse"]},
                    "url": {"type": "string"},
                    "headers": {"type": "object"},
                    "disabled": {"type": "boolean"},
                },
                "required": ["transport", "url"],
            },
        },
        "additionalProperties": {
            "type": "object",
            "oneOf": [
                {"$ref": "#/$defs/stdio"},
                {"$ref": "#/$defs/remote"},
            ],
        },
    },
}


def tool_for_image(image: sqlite3.Row) -> str | None:
    """Ferramenta dona da imagem, ou `None` se não for uma das 5 de agente
    (imagens webtop não participam — o vínculo já é bloqueado antes, mas
    a propagação nunca deve presumir)."""
    return TOOL_BY_REPOSITORY.get(image["repository"])


def validate_tool_config(payload: dict, schema: dict) -> list[str]:
    """Valida o objeto sob a chave de MCP contra o schema da ferramenta e
    devolve mensagens legíveis por servidor (`[]` = válido). Nunca levanta:
    quebra de contrato é reportada, não interrompe a propagação."""
    messages: list[str] = []
    validator = jsonschema.Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path)):
        server = error.absolute_path[0] if error.absolute_path else "?"
        if error.validator == "oneOf":
            message = _one_of_message(error.instance, schema) or _field_message(error)
        else:
            message = _field_message(error)
        messages.append(f"MCP '{server}': {message}")
    return messages


def _field_message(error: jsonschema.ValidationError) -> str:
    """Mensagem de um erro de schema, nomeando o campo quando dá para
    identificar qual foi."""
    if error.validator == "required":
        missing = error.message.split("'")[1]
        return f"campo '{missing}' obrigatório ausente"
    field = error.relative_path[-1] if error.relative_path else None
    if field is not None:
        return f"campo '{field}': {error.message}"
    return error.message


def _error_rank(error: jsonschema.ValidationError) -> int:
    """Ordem de utilidade dentro de uma branch: campo ausente primeiro,
    valor de tipo errado depois."""
    if error.validator == "required":
        return 0
    if error.validator == "type":
        return 1
    return 2


def _one_of_message(entry: dict, schema: dict) -> str | None:
    """Erro de campo sob `oneOf` (stdio vs remoto): o jsonschema devolve o
    erro no nível da entrada, com as causas das duas branches misturadas.
    Revalida a entrada contra cada branch do `$defs` e reporta a causa da
    branch mais próxima de bater (menos erros) — a mensagem que aponta o
    campo que o admin realmente precisa corrigir."""
    best: tuple[int, str] | None = None
    for branch in (schema.get("$defs") or {}).values():
        errors = sorted(
            jsonschema.Draft202012Validator(branch).iter_errors(entry), key=_error_rank
        )
        if not errors:
            continue
        if best is None or len(errors) < best[0]:
            best = (len(errors), _field_message(errors[0]))
    return best[1] if best else None


# ---------------------------------------------------------------------------
# Tradutores: lista resolvida de MCPs -> objeto na chave da ferramenta
# ---------------------------------------------------------------------------

# Retorno de cada tradutor: o objeto a mesclar na chave de MCP. O Hermes
# retorna também o conteúdo do `.env` complementar (por isso o dict extra).
Translation = dict | tuple[dict, str]


def _env_id(display_name: str) -> str:
    """Nome da variável de ambiente do segredo do Hermes:
    `MCP_<NOME_NORMALIZADO>_API_KEY`."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", display_name).strip("_").upper()
    return f"MCP_{slug}_API_KEY"


def _translate_claude_code(servers: list[dict]) -> Translation:
    out: dict = {}
    for server in servers:
        if not server["enabled"]:
            continue  # sem campo de desativação no contrato confirmado
        if server["transport"] == "stdio":
            out[server["display_name"]] = {
                "type": "stdio",
                "command": server["command"],
                "args": server["args"],
                "env": server["env"],
            }
        else:
            out[server["display_name"]] = {
                "type": server["transport"],  # "http" | "sse"
                "url": server["url"],
                "headers": server["headers"],
            }
    return out


def _translate_opencode(servers: list[dict]) -> Translation:
    out: dict = {}
    for server in servers:
        if not server["enabled"]:
            continue
        if server["transport"] == "stdio":
            out[server["display_name"]] = {
                "type": "local",
                "command": [server["command"], *server["args"]],
                "environment": server["env"],
            }
        else:
            out[server["display_name"]] = {
                "type": "remote",
                "url": server["url"],
                "headers": server["headers"],
            }
    return out


def _translate_agy(servers: list[dict]) -> Translation:
    out: dict = {}
    for server in servers:
        disabled = not server["enabled"]
        if server["transport"] == "stdio":
            out[server["display_name"]] = {
                "command": server["command"],
                "args": server["args"],
                "env": server["env"],
                "disabled": disabled,
            }
        else:
            out[server["display_name"]] = {
                "serverUrl": server["url"],  # o campo é `serverUrl`, não `url`
                "headers": server["headers"],
                "disabled": disabled,
            }
    return out


def _translate_oh_my_pi(servers: list[dict]) -> Translation:
    out: dict = {}
    for server in servers:
        disabled = not server["enabled"]
        if server["transport"] == "stdio":
            out[server["display_name"]] = {
                "transport": "stdio",
                "command": server["command"],
                "args": server["args"],
                "env": server["env"],
                "disabled": disabled,
            }
        else:
            out[server["display_name"]] = {
                "transport": server["transport"],  # "http" | "sse"
                "url": server["url"],
                "headers": server["headers"],
                "disabled": disabled,
            }
    return out


def _translate_hermes(servers: list[dict]) -> Translation:
    """Hermes: YAML em `mcp_servers` + segredos em `/config/.hermes/.env`
    (`MCP_<NOME>_API_KEY=<valor>`), referenciados no YAML como `${...}` —
    nunca o valor em claro no arquivo (design.md). O valor do header segue
    a tabela de contrato: prefixo estático fica no YAML (`Bearer
    ${MCP_X_API_KEY}`) e só o segredo vai para o `.env`."""
    out: dict = {}
    env_lines: list[str] = []
    for server in servers:
        enabled = server["enabled"]
        if server["transport"] == "stdio":
            out[server["display_name"]] = {
                "command": server["command"],
                "args": server["args"],
                "env": server["env"],
                "enabled": enabled,
            }
            continue
        env_name = _env_id(server["display_name"])
        headers: dict[str, str] = {}
        for key, value in server["headers"].items():
            if not value or not value.strip():
                headers[key] = value
                continue
            prefix, _, secret = value.partition(" ")
            if not secret:
                # O valor inteiro é o segredo (ex: `token-puro`).
                env_lines.append(f"{env_name}={value}")
                headers[key] = f"${{{env_name}}}"
            else:
                # `Bearer abc` -> YAML `Bearer ${...}`, `.env` com `abc`.
                env_lines.append(f"{env_name}={secret}")
                headers[key] = f"{prefix} ${{{env_name}}}"
        out[server["display_name"]] = {
            "url": server["url"],
            "headers": headers,
            "enabled": enabled,
        }
    env_content = "\n".join(env_lines) + ("\n" if env_lines else "")
    return out, env_content


_TRANSLATORS: dict[str, Callable[[list[dict]], Translation]] = {
    "claude-code": _translate_claude_code,
    "opencode": _translate_opencode,
    "agy": _translate_agy,
    "hermes": _translate_hermes,
    "oh-my-pi": _translate_oh_my_pi,
}


def translate_servers(tool: str, servers: list[dict]) -> Translation:
    """Traduz a lista resolvida para o formato da ferramenta. Um MCP
    malformado é descartado isoladamente (tarefa 6.4): nunca derruba a
    tradução dos demais."""
    translate = _TRANSLATORS[tool]
    ok: list[dict] = []
    for server in servers:
        try:
            ok.append(_sanitize(server))
        except Exception:  # noqa: BLE001 - isolamento por MCP é o objetivo
            continue
    return translate(ok)


def _sanitize(server: dict) -> dict:
    """Confere os pré-requisitos mínimos de um MCP resolvido antes de
    entregar ao tradutor (ex: stdio sem comando). Levanta para que o
    servidor seja descartado isoladamente pelo `translate_servers`."""
    if not server.get("display_name"):
        raise ValueError("MCP sem nome")
    transport = server.get("transport")
    if transport == "stdio" and not server.get("command"):
        raise ValueError(f"MCP '{server.get('display_name')}' sem comando")
    if transport in ("http", "sse") and not server.get("url"):
        raise ValueError(f"MCP '{server.get('display_name')}' sem URL")
    if transport not in ("stdio", "http", "sse"):
        raise ValueError(f"MCP '{server.get('display_name')}' com transporte inválido")
    return server


# ---------------------------------------------------------------------------
# Merge nos arquivos nativos (ler -> substituir só a chave -> reserializar)
# ---------------------------------------------------------------------------


def merge_json(current: bytes | None, tool: str, payload: dict) -> bytes:
    """Merge genérico em JSON (tarefa 6.1): parte de `{}` quando o arquivo
    não existe, substitui só a chave de MCP e preserva as demais chaves.
    Arquivos JSONC (OpenCode) podem ter comentários; o parse tolera
    comentários de linha e bloco, e a reescrita os descarta — o arquivo é
    da ferramenta, que relê JSONC sem problema, mas as chaves de
    configuração dela sobrevivem intactas."""
    document = _parse_jsonc(current) if current else {}
    document[MCP_KEYS[tool]] = payload
    return (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _parse_jsonc(raw: bytes) -> dict:
    text = raw.decode("utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return _strip_jsonc_comments(text)


def _strip_jsonc_comments(text: str) -> dict:
    """Parser tolerante de JSONC: remove `//...` e `/* ... */` fora de
    strings e cai de volta no `json` padrão."""
    stripped: list[str] = []
    in_string = False
    escape = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            stripped.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            stripped.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < len(text):
            nxt = text[index + 1]
            if nxt == "/":
                index = text.find("\n", index)
                index = len(text) if index == -1 else index
                continue
            if nxt == "*":
                end = text.find("*/", index + 2)
                index = len(text) if end == -1 else end + 2
                continue
        stripped.append(char)
        index += 1
    document = json.loads("".join(stripped) or "{}")
    if not isinstance(document, dict):
        raise ValueError("arquivo de config da ferramenta não é um objeto JSON")
    return document


_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.width = 4096


def merge_yaml(current: bytes | None, tool: str, payload: dict) -> bytes:
    """Merge em YAML com `ruamel.yaml` (tarefa 6.2): preserva comentários,
    ordem das chaves e formatação do que já existe no arquivo — só a chave
    de MCP é substituída."""
    from ruamel.yaml.comments import CommentedMap

    if current:
        document = _yaml.load(current.decode("utf-8"))
        if document is None:
            document = CommentedMap()
    else:
        document = CommentedMap()
    document[MCP_KEYS[tool]] = _to_commented(payload)
    buffer = io.BytesIO()
    _yaml.dump(document, buffer)
    return buffer.getvalue()


def _to_commented(value):
    """`ruamel` só preserva o que são tipos dele: converte o payload
    (dict/list puros, vindos do `json`) para CommentedMap/CommentedSeq."""
    from ruamel.yaml.comments import CommentedMap, CommentedSeq

    if isinstance(value, dict):
        result = CommentedMap()
        for key, item in value.items():
            result[key] = _to_commented(item)
        return result
    if isinstance(value, list):
        return CommentedSeq(_to_commented(item) for item in value)
    return value


def extract_mcp_payload(content: bytes, tool: str) -> dict:
    """Lê o arquivo de volta (pós-escrita, tarefa 7.4) e devolve só a
    chave de MCP, para a validação de schema."""
    if not content:
        return {}
    if tool == "hermes":
        document = _yaml.load(content.decode("utf-8"))
        if document is None:
            return {}
        payload = document.get(MCP_KEYS[tool]) or {}
        return json.loads(json.dumps(payload))  # normaliza p/ tipos puros
    document = _parse_jsonc(content)
    return document.get(MCP_KEYS[tool]) or {}


def build_archive(filename: str, content: bytes, *, uid: int = 0, gid: int = 0) -> bytes:
    """Tar de um arquivo só, para gravar via `put_archive` — mesmo formato
    de `agents_md.build_agents_md_archive`."""
    return build_nested_archive(filename, content, uid=uid, gid=gid)


def build_nested_archive(relative_path: str, content: bytes, *, uid: int = 0, gid: int = 0) -> bytes:
    """Tar com o arquivo em `relative_path` (relativo a /config) e os
    diretórios pais como membros de diretório — o `put_archive` do Docker
    exige que o destino exista, então caminhos aninhados (`.omp/agent/…`,
    `.hermes/…`) precisam nascer com o tar, como o `docker cp` faz. O
    destino da extração passa a ser o ponto de montagem do volume, não o
    diretório do arquivo."""
    buffer = io.BytesIO()
    now = int(time.time())
    parts = [part for part in relative_path.split("/") if part]
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for depth in range(1, len(parts)):
            info = tarfile.TarInfo(name="/".join(parts[:depth]))
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            info.uid = uid
            info.gid = gid
            info.mtime = now
            tar.addfile(info)
        info = tarfile.TarInfo(name="/".join(parts))
        info.size = len(content)
        info.mode = 0o644
        info.uid = uid
        info.gid = gid
        info.mtime = now
        tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()

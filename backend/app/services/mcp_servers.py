"""Biblioteca de servidores MCP gerenciada pelo administrador.

Cada servidor MCP é um cadastro genérico (transporte `stdio`, `http` ou
`sse`) vinculável a N imagens de agente de código — só a imagens com
`provision_kind == 'build'`, mesma regra de `agent_skills.py`. Diferente de
skills, MCP não precisa de build: é só configuração, injetada por merge
direto no arquivo nativo de cada ferramenta (ver `mcp_tool_configs.py` para
os tradutores e `instances.py`/rotas de vínculo para quem dispara a
injeção). `env`/`headers` são cifrados em repouso com a mesma
infraestrutura Fernet de `ssh_identity.py`, nunca devolvidos em claro numa
resposta de API.
"""

from __future__ import annotations

import json
import posixpath
import sqlite3

from cryptography.fernet import Fernet

from app.config import Settings
from app.services import mcp_tool_configs
from app.services.errors import ConflictError, NotFoundError, ValidationFailedError

_SELECT = """
    SELECT m.id, m.display_name, m.transport, m.command, m.args_json, m.url,
           m.env_encrypted, m.headers_encrypted, m.enabled,
           m.created_at, m.updated_at,
           (SELECT COUNT(*) FROM image_mcp_servers i WHERE i.mcp_server_id = m.id)
               AS linked_images
    FROM mcp_servers m
"""


def _fernet(settings: Settings) -> Fernet:
    return Fernet(settings.ssh_key_encryption_key.encode())


def _encrypt_dict(settings: Settings, value: dict[str, str] | None) -> bytes | None:
    if not value:
        return None
    return _fernet(settings).encrypt(json.dumps(value).encode())


def decrypt_dict(settings: Settings, encrypted: bytes | None) -> dict[str, str]:
    """Decifra `env`/`headers` — uso interno (montagem do payload a
    injetar). Nunca exposto a uma resposta de API."""
    if encrypted is None:
        return {}
    return json.loads(_fernet(settings).decrypt(encrypted))


def list_mcp_servers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(_SELECT + " ORDER BY m.display_name").fetchall()


def get_mcp_server(conn: sqlite3.Connection, mcp_server_id: int) -> sqlite3.Row:
    row = conn.execute(_SELECT + " WHERE m.id = ?", (mcp_server_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"servidor MCP não encontrado: {mcp_server_id}")
    return row


def has_secret(row: sqlite3.Row, field: str) -> bool:
    """Indica só a presença de `env`/`headers`, nunca o valor — usado pela
    resposta de API para o admin saber que um segredo foi cadastrado sem
    reexibi-lo."""
    return row[f"{field}_encrypted"] is not None


def _validate_transport_fields(
    transport: str,
    command: str | None,
    url: str | None,
) -> None:
    if transport not in ("stdio", "http", "sse"):
        raise ValidationFailedError(f"transporte inválido: {transport}")
    if transport == "stdio" and not (command and command.strip()):
        raise ValidationFailedError("servidor stdio exige comando")
    if transport in ("http", "sse") and not (url and url.strip()):
        raise ValidationFailedError("servidor http/sse exige URL")


def create_mcp_server(
    conn: sqlite3.Connection,
    display_name: str,
    transport: str,
    *,
    settings: Settings,
    command: str | None = None,
    args: list[str] | None = None,
    url: str | None = None,
    env: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    enabled: bool = True,
) -> int:
    if not display_name.strip():
        raise ValidationFailedError("nome de exibição do servidor MCP não pode ser vazio")
    _validate_transport_fields(transport, command, url)
    try:
        cur = conn.execute(
            """INSERT INTO mcp_servers
                   (display_name, transport, command, args_json, url,
                    env_encrypted, headers_encrypted, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                display_name,
                transport,
                command,
                json.dumps(args) if args else None,
                url,
                _encrypt_dict(settings, env),
                _encrypt_dict(settings, headers),
                int(enabled),
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise ConflictError(f"servidor MCP já cadastrado: {display_name}") from exc
    return cur.lastrowid


def update_mcp_server(
    conn: sqlite3.Connection,
    mcp_server_id: int,
    *,
    settings: Settings,
    display_name: str | None = None,
    transport: str | None = None,
    command: str | None = None,
    args: list[str] | None = None,
    url: str | None = None,
    env: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    enabled: bool | None = None,
) -> None:
    """Edita só as colunas recebidas, como `agent_skills.update_skill`."""
    current = get_mcp_server(conn, mcp_server_id)

    if display_name is not None:
        display_name = display_name.strip()
        if not display_name:
            raise ValidationFailedError("nome de exibição do servidor MCP não pode ser vazio")

    next_transport = transport if transport is not None else current["transport"]
    next_command = command if command is not None else current["command"]
    next_url = url if url is not None else current["url"]
    if transport is not None or command is not None or url is not None:
        _validate_transport_fields(next_transport, next_command, next_url)

    next_env_encrypted = _encrypt_dict(settings, env) if env is not None else current["env_encrypted"]
    next_headers_encrypted = (
        _encrypt_dict(settings, headers) if headers is not None else current["headers_encrypted"]
    )
    next_args_json = json.dumps(args) if args is not None else current["args_json"]

    try:
        conn.execute(
            """UPDATE mcp_servers
               SET display_name = ?, transport = ?, command = ?, args_json = ?,
                   url = ?, env_encrypted = ?, headers_encrypted = ?, enabled = ?,
                   updated_at = datetime('now')
               WHERE id = ?""",
            (
                display_name if display_name is not None else current["display_name"],
                next_transport,
                next_command,
                next_args_json,
                next_url,
                next_env_encrypted,
                next_headers_encrypted,
                int(enabled) if enabled is not None else current["enabled"],
                mcp_server_id,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise ConflictError("nome já usado por outro servidor MCP") from exc


def delete_mcp_server(conn: sqlite3.Connection, mcp_server_id: int) -> None:
    """Remove o servidor e qualquer vínculo com imagens, sem recusar por
    uso — mesma regra de `agent_skills.delete_skill`. A propagação da
    remoção às instâncias vivas é responsabilidade do chamador (rota),
    igual ao padrão de `set_image_document`/`unlink_skill`."""
    conn.execute("DELETE FROM image_mcp_servers WHERE mcp_server_id = ?", (mcp_server_id,))
    cur = conn.execute("DELETE FROM mcp_servers WHERE id = ?", (mcp_server_id,))
    if cur.rowcount == 0:
        raise NotFoundError(f"servidor MCP não encontrado: {mcp_server_id}")


def list_images_with_mcp_servers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Imagens de agente (`provision_kind = 'build'`) com os servidores
    MCP vinculados — mesma regra de `agent_skills.list_images_with_skills`:
    só essas imagens podem receber vínculo."""
    return conn.execute(
        """SELECT id, display_name, repository, tag FROM images
           WHERE provision_kind = 'build' ORDER BY id"""
    ).fetchall()


def linked_mcp_server_ids(conn: sqlite3.Connection, image_id: int) -> list[int]:
    return [
        row[0]
        for row in conn.execute(
            "SELECT mcp_server_id FROM image_mcp_servers WHERE image_id = ? ORDER BY mcp_server_id",
            (image_id,),
        )
    ]


def _require_build_image(conn: sqlite3.Connection, image_id: int) -> sqlite3.Row:
    from app.services.images import get_image  # import local: evita ciclo

    image = get_image(conn, image_id)
    if image["provision_kind"] != "build":
        raise ValidationFailedError(
            "servidores MCP só podem ser vinculados a imagens de agente de código"
        )
    return image


def link_mcp_server(conn: sqlite3.Connection, image_id: int, mcp_server_id: int) -> None:
    _require_build_image(conn, image_id)
    get_mcp_server(conn, mcp_server_id)  # 404 se o servidor não existe
    conn.execute(
        "INSERT OR IGNORE INTO image_mcp_servers (image_id, mcp_server_id) VALUES (?, ?)",
        (image_id, mcp_server_id),
    )


def unlink_mcp_server(conn: sqlite3.Connection, image_id: int, mcp_server_id: int) -> None:
    _require_build_image(conn, image_id)
    get_mcp_server(conn, mcp_server_id)  # 404 se o servidor não existe
    conn.execute(
        "DELETE FROM image_mcp_servers WHERE image_id = ? AND mcp_server_id = ?",
        (image_id, mcp_server_id),
    )


def resolve_image_mcp_servers(
    conn: sqlite3.Connection, settings: Settings, image_id: int
) -> list[dict]:
    """Servidores MCP vinculados à imagem, com `env`/`headers` já
    decifrados — pronto pra passar a um tradutor de `mcp_tool_configs.py`.
    Lista vazia (não `None`) quando a imagem não tem nenhum vinculado, para
    que o chamador sempre recompute o estado inteiro a partir do banco
    (ver design.md, "sempre recomputa")."""
    rows = conn.execute(
        """SELECT m.id, m.display_name, m.transport, m.command, m.args_json, m.url,
                  m.env_encrypted, m.headers_encrypted, m.enabled
           FROM image_mcp_servers i
           JOIN mcp_servers m ON m.id = i.mcp_server_id
           WHERE i.image_id = ?
           ORDER BY m.display_name""",
        (image_id,),
    ).fetchall()
    resolved = []
    for row in rows:
        resolved.append(
            {
                "display_name": row["display_name"],
                "transport": row["transport"],
                "command": row["command"],
                "args": json.loads(row["args_json"]) if row["args_json"] else [],
                "url": row["url"],
                "env": decrypt_dict(settings, row["env_encrypted"]),
                "headers": decrypt_dict(settings, row["headers_encrypted"]),
                "enabled": bool(row["enabled"]),
            }
        )
    return resolved


# ---------------------------------------------------------------------------
# Escrita do config nativo + validação pós-escrita (tarefas 7.4 e 8.1)
# ---------------------------------------------------------------------------


async def apply_mcp_config_to_container(
    conn: sqlite3.Connection,
    runtime,
    settings: Settings,
    image: sqlite3.Row,
    container_id: str,
) -> list[str]:
    """Escreve o arquivo nativo da ferramenta da imagem com os MCPs
    vinculados atuais (merge, tarefa 6) e valida o resultado lendo de volta
    (tarefa 7.4). Devolve as mensagens de quebra de contrato (`[]` quando
    válido); erros de runtime levantam, e quem chama isola por instância.

    A escrita não é desfeita mesmo com quebra de contrato (design.md): o
    arquivo já está no estado novo, e o admin corrige ciente do que há lá.
    """
    tool = mcp_tool_configs.tool_for_image(image)
    if tool is None:
        return []
    servers = resolve_image_mcp_servers(conn, settings, image["id"])
    translated = mcp_tool_configs.translate_servers(tool, servers)
    if tool == "hermes":
        payload, env_content = translated
    else:
        payload, env_content = translated, None

    path = mcp_tool_configs.CONFIG_PATHS[tool]
    current = await runtime.get_archive(container_id, path)
    merge = mcp_tool_configs.merge_yaml if tool == "hermes" else mcp_tool_configs.merge_json
    merged = merge(current, tool, payload)

    # A extração é a partir de /config (ponto de montagem do volume) e o
    # tar embute os diretórios pais: o put_archive do Docker exige que o
    # destino exista, e `/config/.omp/agent` etc. não nascem no container.
    relative = posixpath.relpath(path, "/config")
    await runtime.put_archive(
        container_id, "/config", mcp_tool_configs.build_nested_archive(relative, merged)
    )
    if env_content is not None:
        env_relative = posixpath.relpath(mcp_tool_configs.HERMES_ENV_PATH, "/config")
        await runtime.put_archive(
            container_id,
            "/config",
            mcp_tool_configs.build_nested_archive(env_relative, env_content.encode("utf-8")),
        )

    written = await runtime.get_archive(container_id, path)
    payload_read = mcp_tool_configs.extract_mcp_payload(written or b"", tool)
    return mcp_tool_configs.validate_tool_config(payload_read, mcp_tool_configs.MCP_JSON_SCHEMAS[tool])


def _live_instances_of_image(conn: sqlite3.Connection, image_id: int) -> list[sqlite3.Row]:
    """Instâncias vivas da imagem — mesma consulta de
    `agents_md._live_instances_of_image`: container criado e em execução
    (uma parada recebe a config nova no próximo start, via
    `_inject_mcp_servers`)."""
    return conn.execute(
        """SELECT id AS instance_id, container_id FROM instances
           WHERE image_id = ? AND deleted_at IS NULL
             AND container_id IS NOT NULL AND state = 'running'""",
        (image_id,),
    ).fetchall()


async def propagate_mcp_servers_to_live_instances(
    conn: sqlite3.Connection, runtime, settings: Settings, image_id: int
) -> tuple[list[dict], list[dict]]:
    """Reescreve o config de MCP em todas as instâncias vivas da imagem
    (tarefa 8.1), no padrão de
    `propagate_document_to_live_instances`. Retorna `(propagation_failures,
    schema_validation_errors)`: a primeira lista reúne falhas de runtime
    por instância, a segunda quebras de contrato com a mensagem por campo
    (tarefa 7.3), também por instância. Nunca levanta por falha
    individual."""
    image = conn.execute(
        "SELECT id, repository, provision_kind FROM images WHERE id = ?", (image_id,)
    ).fetchone()
    if image is None:
        return [], []

    propagation_failures: list[dict] = []
    schema_validation_errors: list[dict] = []
    for instance in _live_instances_of_image(conn, image_id):
        try:
            errors = await apply_mcp_config_to_container(
                conn, runtime, settings, image, instance["container_id"]
            )
        except Exception as exc:  # noqa: BLE001 - isolamento por instância
            propagation_failures.append(
                {"instance_id": instance["instance_id"], "error": str(exc)}
            )
            continue
        for message in errors:
            schema_validation_errors.append(
                {"instance_id": instance["instance_id"], "error": message}
            )
    return propagation_failures, schema_validation_errors


async def propagate_mcp_removal_to_live_instances(
    conn: sqlite3.Connection, runtime, settings: Settings, image_ids: list[int]
) -> tuple[list[dict], list[dict]]:
    """Propaga a remoção de um MCP (tarefa 3.2): recomputa o estado inteiro
    das imagens afetadas — que já não contêm o servidor removido, pois as
    linhas de vínculo foram apagadas antes — nas instâncias vivas delas."""
    propagation_failures: list[dict] = []
    schema_validation_errors: list[dict] = []
    for image_id in image_ids:
        image_failures, image_validation = await propagate_mcp_servers_to_live_instances(
            conn, runtime, settings, image_id
        )
        propagation_failures.extend(image_failures)
        schema_validation_errors.extend(image_validation)
    return propagation_failures, schema_validation_errors

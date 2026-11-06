"""Publicação das rotas de sessão no plano de dados externo.

O portal escreve um snippet por instância viva no diretório compartilhado que
o Caddyfile importa e recarrega o Caddy via `docker exec` — o comando é fixo
no código, nunca derivado de input de usuário. Sem `caddy_routes_dir`
configurado (dev/testes), a publicação é um no-op e as sessões continuam
sendo entregues pelo caminho dentro do portal.

Ver change external-stream-proxy (design.md D2).
"""

import asyncio
import os
import re
from pathlib import Path

from app.config import Settings
from app.db import DbConnection
from app.runtime.errors import ContainerNotFoundError, RuntimeOperationError
from app.runtime.protocol import ContainerRuntime
from app.services.audit_log import audit

CADDY_RELOAD_COMMAND = [
    "caddy",
    "reload",
    "--config",
    "/etc/caddy/Caddyfile",
    "--adapter",
    "caddyfile",
]

# O import do Caddyfile usa um glob; um arquivo sempre presente evita que o
# glob fique vazio (e o Caddy recuse a configuração por import sem match).
_PLACEHOLDER_NAME = "000-placeholder.caddy"
_PLACEHOLDER_CONTENT = (
    "# Rotas de sessão publicadas pelo portal; não editar.\n"
    "# Este placeholder mantém o glob do import do Caddyfile não vazio.\n"
)


# O id e o nome do container são gerados pelo portal (uuid e prefixo +
# uuid), mas o snippet é injetado num arquivo de configuração: qualquer
# caractere fora deste conjunto poderia quebrar a sintaxe do Caddyfile.
_SAFE_ROUTE_TOKEN = re.compile(r"^[A-Za-z0-9_.-]+$")


def route_path(routes_dir: Path, instance_id: str) -> Path:
    return routes_dir / f"{instance_id}.caddy"


def route_snippet(instance_id: str, container_name: str, port: int) -> str:
    if not _SAFE_ROUTE_TOKEN.fullmatch(instance_id):
        raise ValueError(f"id de instância inválido para rota: {instance_id!r}")
    if not _SAFE_ROUTE_TOKEN.fullmatch(container_name):
        raise ValueError(f"nome de container inválido para rota: {container_name!r}")
    port = int(port)
    return (
        f"# Instância {instance_id} — gerado pelo portal; não editar.\n"
        f"handle /i/{instance_id}/* {{\n"
        "\tforward_auth portal:8000 {\n"
        "\t\turi /internal/data-plane/authorize\n"
        # A subrequisição de autorização NÃO pode herdar o upgrade: sem
        # removê-lo o Caddy tenta um WebSocket contra o endpoint interno
        # (que só aceita HTTP) e a abertura do canal falha com 403.
        "\t\theader_up -Upgrade\n"
        "\t\theader_up -Connection\n"
        "\t\theader_up -Sec-WebSocket-Key\n"
        "\t\theader_up -Sec-WebSocket-Version\n"
        "\t\theader_up -Sec-WebSocket-Protocol\n"
        "\t\theader_up -Sec-WebSocket-Extensions\n"
        "\t\theader_up X-Data-Plane-Secret {$WCUI_DATA_PLANE_SECRET}\n"
        "\t\tcopy_headers Authorization\n"
        "\t}\n"
        f"\treverse_proxy {container_name}:{port} {{\n"
        "\t\ttransport http {\n"
        "\t\t\tread_timeout 3600s\n"
        "\t\t\twrite_timeout 3600s\n"
        "\t\t}\n"
        "\t}\n"
        "}\n"
    )


def _lock(runtime: ContainerRuntime) -> asyncio.Lock:
    """Serializa publicações no runtime da aplicação.

    O portal roda com um worker, mas as transições de ciclo de vida são
    assíncronas e podem intercalar: o lock garante que uma escrita de rota e
    o `reload` correspondente não se misturem com os de outra instância.
    Fica preso ao event loop corrente (e não ao runtime) para que um mesmo
    runtime usado por loops diferentes — como em testes — não reutilize um
    lock de outro loop."""
    loop = asyncio.get_running_loop()
    locks = getattr(loop, "_wcui_data_plane_locks", None)
    if locks is None:
        locks = {}
        setattr(loop, "_wcui_data_plane_locks", locks)
    lock = locks.get(id(runtime))
    if lock is None:
        lock = asyncio.Lock()
        locks[id(runtime)] = lock
    return lock


def _ensure_dir(routes_dir: Path) -> None:
    routes_dir.mkdir(parents=True, exist_ok=True)
    placeholder = routes_dir / _PLACEHOLDER_NAME
    if not placeholder.exists():
        placeholder.write_text(_PLACEHOLDER_CONTENT, encoding="utf-8")


def _write_atomic(path: Path, content: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


async def _reload(runtime: ContainerRuntime, settings: Settings) -> None:
    try:
        code, output = await runtime.exec(settings.caddy_container, CADDY_RELOAD_COMMAND)
    except (ContainerNotFoundError, RuntimeOperationError) as exc:
        # Sem Caddy no ambiente (dev/testes) ou container reiniciando: a
        # rota fica escrita e o próximo `reload` a aplica.
        audit("data_plane.reload", outcome="failure", detail=f"exec: {str(exc)[:300]}")
        return
    if code != 0:
        audit(
            "data_plane.reload",
            outcome="failure",
            detail=output.decode(errors="replace")[:300],
        )


async def publish_route(
    runtime: ContainerRuntime,
    settings: Settings,
    instance_id: str,
    container_name: str,
    port: int,
) -> None:
    """Publica (ou atualiza) a rota de uma instância e recarrega o Caddy.

    Idempotente: se o snippet já está com o conteúdo esperado, nem reescreve
    nem recarrega."""
    if settings.caddy_routes_dir is None:
        return
    async with _lock(runtime):
        _ensure_dir(settings.caddy_routes_dir)
        path = route_path(settings.caddy_routes_dir, instance_id)
        content = route_snippet(instance_id, container_name, port)
        if path.exists() and path.read_text(encoding="utf-8") == content:
            return
        _write_atomic(path, content)
        await _reload(runtime, settings)


async def withdraw_route(
    runtime: ContainerRuntime, settings: Settings, instance_id: str
) -> None:
    """Retira a rota de uma instância parada/excluída e recarrega o Caddy.

    Idempotente: sem arquivo, não há nada a fazer (nem reload)."""
    if settings.caddy_routes_dir is None:
        return
    async with _lock(runtime):
        path = route_path(settings.caddy_routes_dir, instance_id)
        try:
            path.unlink()
        except FileNotFoundError:
            return
        await _reload(runtime, settings)


async def publish_live_routes(
    conn: DbConnection, runtime: ContainerRuntime, settings: Settings
) -> None:
    """Sincroniza o diretório de rotas com o banco (startup/reconciliação).

    Escreve uma rota para cada instância `running` e remove as rotas de
    instâncias que já não estão em execução — os arquivos sobrevivem ao
    reinício do processo no volume compartilhado. Um único reload ao final.
    """
    if settings.caddy_routes_dir is None:
        return
    rows = conn.execute(
        """SELECT i.id AS instance_id, i.container_name, img.port AS image_port
           FROM instances i JOIN images img ON img.id = i.image_id
           WHERE i.state = 'running' AND i.deleted_at IS NULL
             AND i.container_name IS NOT NULL"""
    ).fetchall()
    async with _lock(runtime):
        routes_dir = settings.caddy_routes_dir
        _ensure_dir(routes_dir)
        live = {row["instance_id"] for row in rows}
        for path in routes_dir.glob("*.caddy"):
            if path.name == _PLACEHOLDER_NAME:
                continue
            if path.stem not in live:
                path.unlink(missing_ok=True)
        for row in rows:
            _write_atomic(
                route_path(routes_dir, row["instance_id"]),
                route_snippet(
                    row["instance_id"], row["container_name"], row["image_port"]
                ),
            )
        await _reload(runtime, settings)

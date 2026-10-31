"""Teste e2e: o documento AGENTS.md chega ao container com dono correto.

Opt-in (`pytest -m e2e`): o caso webtop percorre o fluxo real de
`create_instance` com um webtop de verdade (baixado); o caso agente usa um
container manual de `wcui-agent-base` com `sleep`, porque o entrypoint da
base (`ttyd`) sem comando de agente encerra o container logo após o start —
o mapeamento provision_kind→uid já é coberto em unidade, aqui interessa o
comportamento real do `put_archive`/`exec` com dono root.

As asserções usam código de saída (`grep -q`/`test` via exec): nesta versão
do aiodocker, `exec.start(detach=True)` devolve o corpo vazio para vários
comandos, mas o `ExitCode` via `inspect()` é confiável.
"""

import uuid

import aiodocker
import pytest

from app.config import Settings
from app.db import connect, init_db
from app.runtime.docker_runtime import AioDockerContainerRuntime
from app.services.agents_md import build_agents_md_archive
from app.services.agents_md import create_document, set_image_document
from app.services.instances import create_instance

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image

pytestmark = pytest.mark.e2e

_WEBTOP_REPOSITORY = "lscr.io/linuxserver/webtop"
_WEBTOP_TAG = "latest"
_AGENT_BASE_REPOSITORY = "wcui-agent-base"

_CONTENT = "# Regras do projeto\n\nCommits em português, no imperativo.\n"


async def _assert_exec(docker, container_id, command):
    """Roda `docker exec` e devolve o código de saída.

    `start(detach=True)` é assíncrono no daemon: o `inspect()` logo em
    seguida pode ainda ver `ExitCode` nulo, então espera em loop curto até
    o processo terminar (com teto para não travar o teste).
    """
    import asyncio

    container = docker.containers.container(container_id)
    exec_instance = await container.exec(cmd=command)
    await exec_instance.start(detach=True)
    for _ in range(50):
        info = await exec_instance.inspect()
        code = info.get("ExitCode")
        if code is not None:
            return int(code)
        await asyncio.sleep(0.1)
    return -1


async def test_webtop_via_fluxo_real_recebe_documento_com_dono_puid(tmp_path):
    # volume_prefix único por execução: nome determinístico colidia com
    # leftovers de execuções anteriores mal limpadas ("volume is in use").
    settings = Settings(
        db_path=tmp_path / "e2e-agents-md.db",
        uploads_dir=tmp_path / "uploads",
        docker_network="bridge",  # sem rede dedicada neste teste isolado
        volume_prefix=f"wcui-e2e-{uuid.uuid4().hex[:8]}",
        container_prefix=f"wcui-e2e-{uuid.uuid4().hex[:8]}",
    )
    conn = connect(settings.db_path)
    init_db(conn)
    user_id = conn.execute(
        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
        ("e2e2@exemplo.test", "hash"),
    ).lastrowid
    image_id = insert_image(conn, repository=_WEBTOP_REPOSITORY, tag=_WEBTOP_TAG)
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    document_id = create_document(conn, "Regras e2e", _CONTENT, settings=settings)
    set_image_document(conn, image_id, document_id)
    conn.close()

    runtime = AioDockerContainerRuntime()
    docker = aiodocker.Docker()
    try:
        conn = connect(settings.db_path)
        instance = await create_instance(conn, runtime, settings, user_id, image_id)
        conn.close()
        container_id = instance["container_id"]

        # conteúdo presente
        assert await _assert_exec(
            docker, container_id, ["grep", "-qF", "Commits em português", "/config/AGENTS.md"]
        ) == 0
        # dono PUID/PGID (provision_kind='pull')
        assert await _assert_exec(
            docker, container_id,
            ["sh", "-c", f'test "$(stat -c %u:%g /config/AGENTS.md)" = "{settings.puid}:{settings.pgid}"'],
        ) == 0
        # permissão 0644
        assert await _assert_exec(
            docker, container_id,
            ["sh", "-c", 'test "$(stat -c %a /config/AGENTS.md)" = "644"'],
        ) == 0

        conn = connect(settings.db_path)
        conn.execute("UPDATE instances SET deleted_at = datetime('now')")
        conn.close()
        await docker.containers.container(container_id).delete(force=True)
        await runtime.remove_volume(instance["volume_name"])
    finally:
        await docker.close()
        await runtime.close()


async def test_container_de_agente_recebe_documento_com_dono_root(tmp_path):
    """Container manual da base de agente (roda como root): o tar do
    documento é gravado e o dono conferido via `docker exec` real."""
    tar_bytes = build_agents_md_archive(_CONTENT, uid=0, gid=0)

    docker = aiodocker.Docker()
    volume_name = f"wcui-e2e-agents-md-{uuid.uuid4().hex[:8]}"
    await docker.volumes.create({"Name": volume_name})
    container = await docker.containers.run(
        config={
            "Image": f"{_AGENT_BASE_REPOSITORY}:latest",
            "Entrypoint": ["sleep", "60"],  # entrypoint real (ttyd) exige comando de agente
            "HostConfig": {"Binds": [f"{volume_name}:/config"]},
        }
    )
    try:
        # mesmo caminho que `_inject_agents_md`: put_archive em /config
        await container.put_archive("/config", tar_bytes)

        assert await _assert_exec(
            docker, container.id, ["grep", "-qF", "Commits em português", "/config/AGENTS.md"]
        ) == 0
        assert await _assert_exec(
            docker, container.id,
            ["sh", "-c", 'test "$(stat -c %u:%g /config/AGENTS.md)" = "0:0"'],
        ) == 0
    finally:
        await container.delete(force=True)
        volume = await docker.volumes.get(volume_name)
        await volume.delete()
        await docker.close()
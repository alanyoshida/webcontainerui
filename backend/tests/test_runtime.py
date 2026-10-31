import ast
import asyncio
from pathlib import Path

import pytest

from app.runtime.docker_runtime import AioDockerContainerRuntime
from app.runtime.errors import ContainerNotFoundError
from app.runtime.fake import FakeContainerRuntime
from app.runtime.protocol import ContainerRuntime, ContainerSpec, ContainerState


def _spec(name: str = "wcui-teste") -> ContainerSpec:
    return ContainerSpec(
        name=name,
        repository="lscr.io/linuxserver/webtop",
        tag="latest",
        network="wcui_net",
        volume_name="wcui_vol",
        volume_mount_path="/config",
        env={"CUSTOM_USER": "u", "PASSWORD": "p"},
        mem_limit_mb=2048,
        cpu_limit=2.0,
        shm_size_mb=1024,
    )


def test_fake_e_docker_runtime_satisfazem_o_protocolo():
    assert isinstance(FakeContainerRuntime(), ContainerRuntime)
    assert isinstance(AioDockerContainerRuntime.__new__(AioDockerContainerRuntime), ContainerRuntime)


async def test_fake_reproduz_a_maquina_de_estados():
    runtime = FakeContainerRuntime()

    container_id = await runtime.create_container(_spec())
    assert await runtime.inspect_container(container_id) == ContainerState.STOPPED

    await runtime.start_container(container_id)
    assert await runtime.inspect_container(container_id) == ContainerState.RUNNING

    await runtime.stop_container(container_id)
    assert await runtime.inspect_container(container_id) == ContainerState.STOPPED

    await runtime.remove_container(container_id)
    with pytest.raises(ContainerNotFoundError):
        await runtime.inspect_container(container_id)


async def test_fake_volume_e_idempotente():
    runtime = FakeContainerRuntime()

    await runtime.ensure_volume("vol-1")
    await runtime.ensure_volume("vol-1")  # repetir não é erro
    assert await runtime.volume_exists("vol-1")

    await runtime.remove_volume("vol-1")
    await runtime.remove_volume("vol-1")  # remover duas vezes não é erro
    assert not await runtime.volume_exists("vol-1")


async def test_fake_permite_injetar_falha_numa_operacao_especifica():
    runtime = FakeContainerRuntime()
    runtime.fail_next("start_container", RuntimeError("docker indisponível"))

    container_id = await runtime.create_container(_spec())
    with pytest.raises(RuntimeError, match="docker indisponível"):
        await runtime.start_container(container_id)

    # a falha é consumida uma vez; a chamada seguinte funciona normalmente
    await runtime.start_container(container_id)
    assert await runtime.inspect_container(container_id) == ContainerState.RUNNING


async def test_operacao_lenta_de_container_nao_bloqueia_trafego_concorrente():
    """Prova, sem Docker, a propriedade central de D3: nada no caminho de uma
    operação de container deve impedir o resto do sistema de continuar
    respondendo — o risco real sendo uma chamada síncrona escondida atrás de
    um `await`, que travaria o event loop inteiro."""
    runtime = FakeContainerRuntime()
    runtime.set_delay("create_container", 0.3)

    tick_count = 0
    stop = asyncio.Event()

    async def heartbeat():
        nonlocal tick_count
        while not stop.is_set():
            tick_count += 1
            await asyncio.sleep(0.01)

    heartbeat_task = asyncio.create_task(heartbeat())
    await runtime.create_container(_spec())
    stop.set()
    await heartbeat_task

    # com a operação levando 0.3s e o heartbeat batendo a cada 0.01s, uma
    # operação bloqueante deixaria tick_count em 0 ou 1; isso confirma que
    # o event loop continuou livre durante a operação de container.
    assert tick_count >= 10


def test_docker_runtime_nao_usa_chamada_sincrona_bloqueante():
    """Verificação por inspeção (5.3): o módulo não importa o SDK síncrono do
    Docker nem `subprocess`, e todo método que fala com o Docker é `async
    def` — a propriedade que D3 exige para não travar o event loop."""
    module_path = AioDockerContainerRuntime.__module__.replace(".", "/") + ".py"
    source_path = Path(__file__).resolve().parent.parent / module_path
    tree = ast.parse(source_path.read_text(encoding="utf-8"))

    proibidos = {"subprocess", "docker"}  # "docker" = SDK síncrono oficial, não aiodocker
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in proibidos, alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in proibidos, node.module

    class_def = next(
        n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "AioDockerContainerRuntime"
    )
    sync_methods = [
        n.name
        for n in class_def.body
        if isinstance(n, ast.FunctionDef) and n.name != "__init__"
    ]
    assert sync_methods == [], f"método síncrono no runtime: {sync_methods}"


async def test_fake_build_image_produz_a_sequencia_de_progresso_configurada():
    from app.runtime.protocol import PullProgress

    runtime = FakeContainerRuntime()
    runtime.set_build_progress(
        [
            PullProgress(status="Step 1/2", detail="FROM python:3.12-slim"),
            PullProgress(status="pronta", completed=True),
        ]
    )

    progress = [p async for p in runtime.build_image("/ctx", "wcui-agent-teste", "latest")]

    assert [p.status for p in progress] == ["Step 1/2", "pronta"]
    assert progress[-1].completed
    assert runtime.build_calls == [
        {"context_dir": "/ctx", "repository": "wcui-agent-teste", "tag": "latest"}
    ]


async def test_fake_build_image_propaga_falha_configurada():
    from app.runtime.errors import RuntimeOperationError

    runtime = FakeContainerRuntime()
    runtime.fail_next("build_image", RuntimeOperationError("Dockerfile inválido"))

    with pytest.raises(RuntimeOperationError, match="Dockerfile inválido"):
        async for _ in runtime.build_image("/ctx", "wcui-agent-teste", "latest"):
            pass

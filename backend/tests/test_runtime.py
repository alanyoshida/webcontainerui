import ast
import asyncio
from pathlib import Path

import pytest

from app.runtime.docker_runtime import AioDockerContainerRuntime
from app.runtime.errors import ContainerNotFoundError
from app.runtime.fake import FakeContainerRuntime
from app.runtime.protocol import ContainerRuntime, ContainerSpec, ContainerState, ImageInfo


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
        {
            "context_dir": "/ctx",
            "repository": "wcui-agent-teste",
            "tag": "latest",
            "buildargs": {},
        }
    ]


async def test_fake_build_image_propaga_falha_configurada():
    from app.runtime.errors import RuntimeOperationError

    runtime = FakeContainerRuntime()
    runtime.fail_next("build_image", RuntimeOperationError("Dockerfile inválido"))

    with pytest.raises(RuntimeOperationError, match="Dockerfile inválido"):
        async for _ in runtime.build_image("/ctx", "wcui-agent-teste", "latest"):
            pass


def _tar_of(name: str, content: bytes) -> bytes:
    import io
    import tarfile

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        info = tarfile.TarInfo(name=name)
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


async def test_fake_put_archive_registra_container_destino_e_conteudo():
    runtime = FakeContainerRuntime()
    container_id = await runtime.create_container(_spec())
    tar_bytes = _tar_of("arquivo.txt", b"tar-bytes-de-teste")

    await runtime.put_archive(container_id, "/config", tar_bytes)

    assert runtime.put_archive_calls == [
        {"container_id": container_id, "destination_path": "/config", "tar_bytes": tar_bytes}
    ]


async def test_fake_get_archive_le_de_volta_o_que_put_archive_escreveu():
    runtime = FakeContainerRuntime()
    container_id = await runtime.create_container(_spec())
    tar_bytes = _tar_of(".claude.json", b'{"mcpServers": {}}')

    await runtime.put_archive(container_id, "/config", tar_bytes)
    conteudo = await runtime.get_archive(container_id, "/config/.claude.json")

    assert conteudo == b'{"mcpServers": {}}'


async def test_fake_get_archive_caminho_inexistente_devolve_none():
    runtime = FakeContainerRuntime()
    container_id = await runtime.create_container(_spec())

    assert await runtime.get_archive(container_id, "/config/nao-existe.json") is None


async def test_fake_get_archive_em_container_inexistente_falha():
    runtime = FakeContainerRuntime()

    with pytest.raises(ContainerNotFoundError):
        await runtime.get_archive("nao-existe", "/config/x.json")


async def test_fake_get_archive_caminho_aninhado():
    runtime = FakeContainerRuntime()
    container_id = await runtime.create_container(_spec())
    tar_bytes = _tar_of(".config/opencode/opencode.jsonc", b'{"mcp": {}}')

    await runtime.put_archive(container_id, "/config", tar_bytes)
    conteudo = await runtime.get_archive(container_id, "/config/.config/opencode/opencode.jsonc")

    assert conteudo == b'{"mcp": {}}'


async def test_fake_put_archive_em_container_inexistente_falha():
    runtime = FakeContainerRuntime()

    with pytest.raises(ContainerNotFoundError):
        await runtime.put_archive("nao-existe", "/config", b"tar-bytes")


async def test_fake_exec_registra_chamada_e_retorna_sucesso():
    runtime = FakeContainerRuntime()
    container_id = await runtime.create_container(_spec())

    exit_code, output = await runtime.exec(container_id, ["rm", "-f", "/config/AGENTS.md"])

    assert exit_code == 0
    assert output == b""
    assert runtime.exec_calls == [
        {"container_id": container_id, "command": ["rm", "-f", "/config/AGENTS.md"]}
    ]


async def test_fake_exec_em_container_inexistente_falha():
    runtime = FakeContainerRuntime()

    with pytest.raises(ContainerNotFoundError):
        await runtime.exec("fake-inexistente", ["true"])


async def test_fake_exec_permite_injetar_falha():
    runtime = FakeContainerRuntime()
    container_id = await runtime.create_container(_spec())
    runtime.fail_next("exec", RuntimeError("docker exec indisponível"))

    with pytest.raises(RuntimeError):
        await runtime.exec(container_id, ["true"])


async def test_fake_inspect_image_devolve_labels_e_digest_configurados():
    runtime = FakeContainerRuntime()
    runtime.set_image_info(
        "lscr.io/linuxserver/vscode",
        "latest",
        labels={"build_version": "1.143.1-ls31"},
        digest="sha256:0123456789abcdef",
    )

    info = await runtime.inspect_image("lscr.io/linuxserver/vscode", "latest")

    assert info.labels["build_version"] == "1.143.1-ls31"
    assert info.digest == "sha256:0123456789abcdef"


async def test_fake_inspect_image_pull_registra_imagem_sem_info():
    runtime = FakeContainerRuntime()
    async for _ in runtime.pull_image("lscr.io/linuxserver/webtop", "latest"):
        pass

    info = await runtime.inspect_image("lscr.io/linuxserver/webtop", "latest")

    assert info == ImageInfo(labels={})


async def test_fake_inspect_image_em_imagem_inexistente_falha():
    runtime = FakeContainerRuntime()

    with pytest.raises(ContainerNotFoundError):
        await runtime.inspect_image("r/imagem", "latest")


def test_parse_do_label_build_version():
    from app.services.images import version_from_image_info

    info = ImageInfo(
        labels={"build_version": "1.143.1-ls31", "org.opencontainers.image.title": "vscode"},
        digest="sha256:0123456789abcdef0123456789abcdef",
    )

    assert version_from_image_info(info) == "1.143.1-ls31"


def test_parse_sem_label_usa_digest_curto():
    from app.services.images import version_from_image_info

    info = ImageInfo(labels={}, digest="sha256:0123456789abcdef0123456789abcdef")

    assert version_from_image_info(info) == "0123456789ab"


def test_parse_sem_label_nem_digest_retorna_none():
    from app.services.images import version_from_image_info

    assert version_from_image_info(ImageInfo(labels={})) is None

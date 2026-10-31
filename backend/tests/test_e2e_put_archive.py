"""Teste e2e de `put_archive` sobre o daemon Docker real.

Opt-in (`pytest -m e2e`), como os demais testes e2e: usa um Dockerfile
mínimo (`FROM scratch`) para não depender de rede nem baixar imagem base.
"""

import io
import tarfile

import pytest

from app.runtime.docker_runtime import AioDockerContainerRuntime
from app.runtime.protocol import ContainerSpec

pytestmark = pytest.mark.e2e

_REPOSITORY = "wcui-put-archive-fixture"
_TAG = "latest"


def _build_tar(name: str, content: bytes, mode: int) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        info = tarfile.TarInfo(name=name)
        info.size = len(content)
        info.mode = mode
        tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


async def test_put_archive_injeta_arquivo_com_conteudo_e_modo_corretos(tmp_path):
    # `CMD` só precisa existir na config da imagem para o Docker aceitar
    # `containers.create` — o container nunca é iniciado neste teste, então
    # o binário não precisa existir de verdade.
    (tmp_path / "Dockerfile").write_text('FROM scratch\nLABEL wcui.test=1\nCMD ["x"]\n', encoding="utf-8")

    runtime = AioDockerContainerRuntime()
    try:
        progress = [p async for p in runtime.build_image(str(tmp_path), _REPOSITORY, _TAG)]
        assert progress[-1].completed

        container_id = await runtime.create_container(
            ContainerSpec(
                name="wcui-teste-put-archive",
                repository=_REPOSITORY,
                tag=_TAG,
                network="bridge",
                volume_name="wcui-teste-put-archive-vol",
                volume_mount_path="/config",
                env={},
                mem_limit_mb=64,
                cpu_limit=0.5,
                shm_size_mb=64,
            )
        )
        try:
            tar_bytes = _build_tar("arquivo-de-teste", b"conteudo-de-teste\n", 0o600)

            await runtime.put_archive(container_id, "/config", tar_bytes)

            import aiodocker

            docker = aiodocker.Docker()
            try:
                container = docker.containers.container(container_id)
                archive = await container.get_archive("/config/arquivo-de-teste")
                member = archive.getmember("arquivo-de-teste")
                assert oct(member.mode) == "0o600"
                assert archive.extractfile("arquivo-de-teste").read() == b"conteudo-de-teste\n"
            finally:
                await docker.close()
        finally:
            await runtime.remove_container(container_id)
            await runtime.remove_volume("wcui-teste-put-archive-vol")
    finally:
        import aiodocker

        docker = aiodocker.Docker()
        try:
            await docker.images.delete(f"{_REPOSITORY}:{_TAG}", force=True)
        finally:
            await docker.close()
        await runtime.close()

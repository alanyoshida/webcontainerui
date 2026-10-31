"""Teste e2e de `exec` sobre o daemon Docker real.

Opt-in (`pytest -m e2e`), como os demais testes e2e. `exec` exige um
container em execução com um binário de verdade, então usa `alpine` com
`sleep` — exige pull de rede, como todo e2e que toca o daemon de verdade.
"""

import pytest

from app.runtime.docker_runtime import AioDockerContainerRuntime
from app.runtime.protocol import ContainerSpec

pytestmark = pytest.mark.e2e

_REPOSITORY = "wcui-exec-fixture"
_TAG = "latest"


async def test_exec_cria_verifica_e_remove_arquivo(tmp_path):
    (tmp_path / "Dockerfile").write_text(
        'FROM alpine:3.21\nCMD ["sleep", "60"]\n', encoding="utf-8"
    )

    runtime = AioDockerContainerRuntime()
    try:
        progress = [p async for p in runtime.build_image(str(tmp_path), _REPOSITORY, _TAG)]
        assert progress[-1].completed

        container_id = await runtime.create_container(
            ContainerSpec(
                name="wcui-teste-exec",
                repository=_REPOSITORY,
                tag=_TAG,
                network="bridge",
                volume_name="wcui-teste-exec-vol",
                volume_mount_path="/config",
                env={},
                mem_limit_mb=64,
                cpu_limit=0.5,
                shm_size_mb=64,
            )
        )
        try:
            await runtime.start_container(container_id)

            code, _ = await runtime.exec(container_id, ["touch", "/config/AGENTS.md"])
            assert code == 0

            code, _ = await runtime.exec(container_id, ["test", "-f", "/config/AGENTS.md"])
            assert code == 0

            code, _ = await runtime.exec(container_id, ["rm", "-f", "/config/AGENTS.md"])
            assert code == 0

            # arquivo removido: `test` falha com código != 0
            code, _ = await runtime.exec(container_id, ["test", "-f", "/config/AGENTS.md"])
            assert code != 0
        finally:
            await runtime.remove_container(container_id)
            await runtime.remove_volume("wcui-teste-exec-vol")
    finally:
        import aiodocker

        docker = aiodocker.Docker()
        try:
            await docker.images.delete(f"{_REPOSITORY}:{_TAG}", force=True)
        finally:
            await docker.close()
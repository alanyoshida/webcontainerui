"""Teste e2e do build de imagem sobre o daemon Docker real.

Opt-in (`pytest -m e2e`), como o teste e2e do webtop: usa um Dockerfile
mínimo (`FROM scratch`) para não depender de rede nem baixar imagem base.
"""

import aiodocker
import pytest

from app.runtime.docker_runtime import AioDockerContainerRuntime

pytestmark = pytest.mark.e2e

_REPOSITORY = "wcui-build-fixture"
_TAG = "latest"


async def test_build_image_de_fixture_cria_a_imagem_no_docker_local(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM scratch\nLABEL wcui.test=1\n", encoding="utf-8")

    runtime = AioDockerContainerRuntime()
    try:
        progress = [
            p async for p in runtime.build_image(str(tmp_path), _REPOSITORY, _TAG)
        ]
        assert progress[-1].completed

        docker = aiodocker.Docker()
        try:
            image = await docker.images.get(f"{_REPOSITORY}:{_TAG}")
            assert image["RepoTags"] == [f"{_REPOSITORY}:{_TAG}"]
        finally:
            await docker.images.delete(f"{_REPOSITORY}:{_TAG}", force=True)
            await docker.close()
    finally:
        await runtime.close()

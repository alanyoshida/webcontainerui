"""Teste e2e: a imagem base dos agentes resolve `~/.ssh` corretamente.

Opt-in (`pytest -m e2e`). Builda o Dockerfile real de `agent-images/_base`
(não um fixture mínimo) e confirma que o diretório home do usuário root,
tal como o `ssh`/`git` o resolvem (via /etc/passwd, não só `$HOME`), é
`/config` — o volume persistido da instância. Trava a regressão descoberta
ao verificar manualmente a injeção de identidade SSH (instance-ssh-keys):
`ENV HOME=/config` sozinho não bastava, porque o cliente `ssh` ignora a
variável de ambiente e usa o home cadastrado no passwd do usuário atual.
"""

from pathlib import Path

import aiodocker
import pytest

from app.runtime.docker_runtime import AioDockerContainerRuntime

pytestmark = pytest.mark.e2e

_REPOSITORY = "wcui-agent-base-ssh-home-fixture"
_TAG = "latest"
_BASE_CONTEXT = Path(__file__).resolve().parents[2] / "agent-images" / "_base"


async def test_home_do_root_resolvido_via_passwd_e_config():
    runtime = AioDockerContainerRuntime()
    try:
        progress = [p async for p in runtime.build_image(str(_BASE_CONTEXT), _REPOSITORY, _TAG)]
        assert progress[-1].completed

        docker = aiodocker.Docker()
        try:
            container = await docker.containers.run(
                config={
                    "Image": f"{_REPOSITORY}:{_TAG}",
                    "Entrypoint": ["getent"],
                    "Cmd": ["passwd", "root"],
                }
            )
            await container.wait()
            logs = "".join(await container.log(stdout=True, stderr=True))
            await container.delete(force=True)
            assert logs.strip() == "root:x:0:0:root:/config:/bin/bash"
        finally:
            await docker.images.delete(f"{_REPOSITORY}:{_TAG}", force=True)
            await docker.close()
    finally:
        await runtime.close()

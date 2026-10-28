"""Runtime sobre `aiodocker` (D7, D3).

Toda chamada aqui é `await` sobre `aiodocker`, que fala com o socket do
Docker via `aiohttp`. Nenhum método faz chamada síncrona — é isso que
impede uma operação de container de travar o event loop e congelar o
vídeo das sessões de outros usuários, conforme D3 em design.md.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import aiodocker
from aiodocker.exceptions import DockerError

from app.runtime.errors import ContainerNotFoundError, RuntimeOperationError
from app.runtime.protocol import ContainerSpec, ContainerState, PullProgress

# Depois de `container.delete(force=True)`, o Docker pode levar um
# instante para soltar as camadas de armazenamento do container — remover
# o volume logo em seguida esbarra em "volume is in use" mesmo com o
# container já removido do estado do daemon. Retry curto resolve; visto
# na prática num teste e2e real (não é uma suposição).
_REMOVE_VOLUME_RETRIES = 5
_REMOVE_VOLUME_BACKOFF_SECONDS = 0.5


class AioDockerContainerRuntime:
    def __init__(self, docker: aiodocker.Docker | None = None) -> None:
        self._docker = docker or aiodocker.Docker()

    async def close(self) -> None:
        await self._docker.close()

    async def ensure_volume(self, name: str) -> None:
        try:
            await self._docker.volumes.create({"Name": name})
        except DockerError as exc:
            if exc.status != 409:  # já existe
                raise RuntimeOperationError(str(exc)) from exc

    async def remove_volume(self, name: str) -> None:
        for attempt in range(_REMOVE_VOLUME_RETRIES):
            try:
                volume = await self._docker.volumes.get(name)
                await volume.delete()
                return
            except DockerError as exc:
                if exc.status == 404:
                    return
                is_last_attempt = attempt == _REMOVE_VOLUME_RETRIES - 1
                if exc.status != 409 or is_last_attempt:
                    raise RuntimeOperationError(str(exc)) from exc
                await asyncio.sleep(_REMOVE_VOLUME_BACKOFF_SECONDS * (attempt + 1))

    async def pull_image(self, repository: str, tag: str) -> AsyncIterator[PullProgress]:
        reference = f"{repository}:{tag}"
        try:
            async for message in self._docker.images.pull(reference, stream=True):
                error = message.get("error")
                if error:
                    raise RuntimeOperationError(error)
                yield PullProgress(status=message.get("status", ""), detail=message.get("progress"))
        except DockerError as exc:
            raise RuntimeOperationError(str(exc)) from exc
        yield PullProgress(status="pronta", completed=True)

    async def create_container(self, spec: ContainerSpec) -> str:
        config = {
            "Image": f"{spec.repository}:{spec.tag}",
            "Env": [f"{key}={value}" for key, value in spec.env.items()],
            "HostConfig": {
                "NetworkMode": spec.network,
                "Binds": [f"{spec.volume_name}:{spec.volume_mount_path}"],
                "ShmSize": spec.shm_size_mb * 1024 * 1024,
                "Memory": spec.mem_limit_mb * 1024 * 1024,
                "NanoCpus": int(spec.cpu_limit * 1_000_000_000),
            },
        }
        try:
            container = await self._docker.containers.create(config=config, name=spec.name)
        except DockerError as exc:
            raise RuntimeOperationError(str(exc)) from exc
        return container.id

    async def start_container(self, container_id: str) -> None:
        container = await self._get_container(container_id)
        try:
            await container.start()
        except DockerError as exc:
            raise RuntimeOperationError(str(exc)) from exc

    async def stop_container(self, container_id: str) -> None:
        container = await self._get_container(container_id)
        try:
            await container.stop()
        except DockerError as exc:
            raise RuntimeOperationError(str(exc)) from exc

    async def remove_container(self, container_id: str) -> None:
        try:
            container = await self._docker.containers.get(container_id)
            await container.delete(force=True)
        except DockerError as exc:
            if exc.status != 404:
                raise RuntimeOperationError(str(exc)) from exc

    async def inspect_container(self, container_id: str) -> ContainerState:
        container = await self._get_container(container_id)
        try:
            info = await container.show()
        except DockerError as exc:
            raise RuntimeOperationError(str(exc)) from exc
        return ContainerState.RUNNING if info["State"]["Running"] else ContainerState.STOPPED

    async def _get_container(self, container_id: str):
        try:
            return await self._docker.containers.get(container_id)
        except DockerError as exc:
            if exc.status == 404:
                raise ContainerNotFoundError(container_id) from exc
            raise RuntimeOperationError(str(exc)) from exc

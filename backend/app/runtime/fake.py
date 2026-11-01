"""Runtime em memória para testes, sem Docker (D7).

Permite simular atraso por operação — para testar que o restante do
sistema continua respondendo durante uma operação de container lenta — e
injetar falha numa operação específica, para exercitar os caminhos de
erro sem depender de um Docker real se comportando mal de propósito.
"""

from __future__ import annotations

import asyncio
import io
import itertools
import tarfile
from collections.abc import AsyncIterator, Mapping

from app.runtime.errors import ContainerNotFoundError
from app.runtime.protocol import ContainerSpec, ContainerState, ImageInfo, PullProgress


class FakeContainerRuntime:
    def __init__(self) -> None:
        self._containers: dict[str, dict] = {}
        self._volumes: set[str] = set()
        self._images: dict[str, ImageInfo] = {}
        self._ids = itertools.count(1)
        self._delays: dict[str, float] = {}
        self._failures: dict[str, Exception] = {}
        self._build_progress: list[PullProgress] | None = None
        self.build_calls: list[dict] = []
        self.pull_calls: list[dict] = []
        self.put_archive_calls: list[dict] = []
        self.exec_calls: list[dict] = []
        # Simula o sistema de arquivos do container pra `get_archive` ler o
        # que `put_archive` escreveu (mudança mcp-server-library: o merge
        # de config de MCP precisa de round-trip escrita->leitura nos
        # testes, sem depender de Docker real).
        self._files: dict[str, dict[str, bytes]] = {}

    def set_delay(self, operation: str, seconds: float) -> None:
        self._delays[operation] = seconds

    def fail_next(self, operation: str, exc: Exception) -> None:
        self._failures[operation] = exc

    def set_build_progress(self, progress: list[PullProgress]) -> None:
        self._build_progress = progress

    def set_image_info(
        self, repository: str, tag: str, *, labels: Mapping[str, str] | None = None, digest: str | None = None
    ) -> None:
        """Configura o que `inspect_image` devolve para a referência dada."""
        self._images[f"{repository}:{tag}"] = ImageInfo(labels=dict(labels or {}), digest=digest)

    async def _simulate(self, operation: str) -> None:
        delay = self._delays.get(operation, 0)
        if delay:
            await asyncio.sleep(delay)
        exc = self._failures.pop(operation, None)
        if exc is not None:
            raise exc

    async def ensure_volume(self, name: str) -> None:
        await self._simulate("ensure_volume")
        self._volumes.add(name)

    async def remove_volume(self, name: str) -> None:
        await self._simulate("remove_volume")
        self._volumes.discard(name)

    async def volume_exists(self, name: str) -> bool:
        return name in self._volumes

    async def pull_image(self, repository: str, tag: str) -> AsyncIterator[PullProgress]:
        self.pull_calls.append({"repository": repository, "tag": tag})
        await self._simulate("pull_image")
        # Registra a imagem como presente no host após o pull bem-sucedido,
        # imitando o Docker: `inspect_image` só funciona para o que foi baixado.
        self._images.setdefault(f"{repository}:{tag}", ImageInfo(labels={}))
        yield PullProgress(status="pronta", completed=True)

    async def build_image(
        self,
        context_dir: str,
        repository: str,
        tag: str,
        *,
        buildargs: Mapping[str, str] | None = None,
    ) -> AsyncIterator[PullProgress]:
        self.build_calls.append(
            {
                "context_dir": context_dir,
                "repository": repository,
                "tag": tag,
                "buildargs": dict(buildargs) if buildargs else {},
            }
        )
        await self._simulate("build_image")
        if self._build_progress is None:
            yield PullProgress(status="pronta", completed=True)
            return
        for progress in self._build_progress:
            yield progress

    async def put_archive(self, container_id: str, destination_path: str, tar_bytes: bytes) -> None:
        self._require(container_id)
        await self._simulate("put_archive")
        self.put_archive_calls.append(
            {"container_id": container_id, "destination_path": destination_path, "tar_bytes": tar_bytes}
        )
        base = destination_path.rstrip("/")
        files = self._files.setdefault(container_id, {})
        with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                extracted = tar.extractfile(member)
                if extracted is None:
                    continue
                full_path = f"{base}/{member.name.lstrip('/')}"
                files[full_path] = extracted.read()

    async def get_archive(self, container_id: str, path: str) -> bytes | None:
        self._require(container_id)
        await self._simulate("get_archive")
        return self._files.get(container_id, {}).get(path)

    async def exec(self, container_id: str, command: list[str]) -> tuple[int, bytes]:
        self._require(container_id)
        await self._simulate("exec")
        self.exec_calls.append({"container_id": container_id, "command": command})
        return 0, b""

    async def create_container(self, spec: ContainerSpec) -> str:
        await self._simulate("create_container")
        container_id = f"fake-{next(self._ids)}"
        self._containers[container_id] = {"spec": spec, "state": ContainerState.STOPPED}
        return container_id

    async def start_container(self, container_id: str) -> None:
        await self._simulate("start_container")
        self._require(container_id)["state"] = ContainerState.RUNNING

    async def stop_container(self, container_id: str) -> None:
        await self._simulate("stop_container")
        self._require(container_id)["state"] = ContainerState.STOPPED

    async def remove_container(self, container_id: str) -> None:
        await self._simulate("remove_container")
        self._containers.pop(container_id, None)

    async def inspect_container(self, container_id: str) -> ContainerState:
        await self._simulate("inspect_container")
        return self._require(container_id)["state"]

    async def inspect_image(self, repository: str, tag: str) -> ImageInfo:
        await self._simulate("inspect_image")
        try:
            return self._images[f"{repository}:{tag}"]
        except KeyError:
            raise ContainerNotFoundError(f"{repository}:{tag}") from None

    def _require(self, container_id: str) -> dict:
        try:
            return self._containers[container_id]
        except KeyError:
            raise ContainerNotFoundError(container_id) from None

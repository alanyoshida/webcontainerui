"""Protocolo estreito de runtime de containers (D7 em design.md).

Todo acesso ao Docker no projeto passa por esta interface. Isso é o que
permite a quase toda a suíte de testes rodar sem Docker instalado: os
testes usam `FakeContainerRuntime`, e só a suíte marcada como `e2e` usa a
implementação sobre `aiodocker`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


class ContainerState(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"


@dataclass(frozen=True)
class ContainerSpec:
    """Tudo que o runtime precisa para criar um container de desktop."""

    name: str
    repository: str
    tag: str
    network: str
    volume_name: str
    volume_mount_path: str
    env: Mapping[str, str]
    mem_limit_mb: int
    cpu_limit: float
    shm_size_mb: int


@dataclass(frozen=True)
class PullProgress:
    status: str
    detail: str | None = None
    completed: bool = False


@runtime_checkable
class ContainerRuntime(Protocol):
    async def ensure_volume(self, name: str) -> None: ...

    async def remove_volume(self, name: str) -> None: ...

    def pull_image(self, repository: str, tag: str) -> AsyncIterator[PullProgress]: ...

    def build_image(
        self, context_dir: str, repository: str, tag: str
    ) -> AsyncIterator[PullProgress]: ...

    async def create_container(self, spec: ContainerSpec) -> str: ...

    async def start_container(self, container_id: str) -> None: ...

    async def stop_container(self, container_id: str) -> None: ...

    async def remove_container(self, container_id: str) -> None: ...

    async def inspect_container(self, container_id: str) -> ContainerState: ...

"""Testa o retry de `remove_volume` contra um `self._docker` simulado —
sem precisar de Docker real — para a corrida descoberta no teste e2e
(13.1): remover o volume logo após o container some em "volume is in
use" porque a limpeza de armazenamento do Docker é assíncrona."""

import asyncio

import pytest
from aiodocker.exceptions import DockerError

from app.runtime.docker_runtime import AioDockerContainerRuntime, _REMOVE_VOLUME_RETRIES
from app.runtime.errors import RuntimeOperationError


class _FakeVolumeHandle:
    def __init__(self, fail_times: int, status: int = 409):
        self._fail_times = fail_times
        self._status = status
        self.calls = 0

    async def delete(self):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise DockerError(self._status, "volume is in use")


class _FakeVolumesApi:
    def __init__(self, handle: _FakeVolumeHandle):
        self._handle = handle

    async def get(self, name):
        return self._handle


class _FakeDocker:
    def __init__(self, handle: _FakeVolumeHandle):
        self.volumes = _FakeVolumesApi(handle)


async def _instant_sleep(*_args, **_kwargs) -> None:
    return None


async def test_remove_volume_tenta_de_novo_apos_volume_in_use(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", _instant_sleep)  # sem esperar de verdade no teste
    handle = _FakeVolumeHandle(fail_times=2)  # falha duas vezes, sucede na terceira
    runtime = AioDockerContainerRuntime(docker=_FakeDocker(handle))

    await runtime.remove_volume("vol-x")

    assert handle.calls == 3


async def test_remove_volume_desiste_apos_esgotar_as_tentativas(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", _instant_sleep)
    handle = _FakeVolumeHandle(fail_times=_REMOVE_VOLUME_RETRIES)  # nunca sucede
    runtime = AioDockerContainerRuntime(docker=_FakeDocker(handle))

    with pytest.raises(RuntimeOperationError):
        await runtime.remove_volume("vol-y")

    assert handle.calls == _REMOVE_VOLUME_RETRIES


async def test_remove_volume_404_e_idempotente_sem_retry(monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", _instant_sleep)
    handle = _FakeVolumeHandle(fail_times=1, status=404)
    runtime = AioDockerContainerRuntime(docker=_FakeDocker(handle))

    await runtime.remove_volume("vol-ja-sumiu")  # não deve levantar

    assert handle.calls == 1  # 404 não tenta de novo, só devolve

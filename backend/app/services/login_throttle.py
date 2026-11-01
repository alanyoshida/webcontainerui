"""Limitação de tentativas de login com falha (change harden-login, M2).

Janela deslizante por chave — a rota de login usa duas: e-mail normalizado
(conta) e IP do cliente (origem). Excedido o limiar de falhas dentro da janela,
a chave entra em recusa temporária: `retry_after_seconds` devolve quanto
esperar, e quem chama responde 429 com `Retry-After` antes de consultar o
banco ou rodar o Argon2 — a recusa é idêntica para conta existente ou não.

Estado vive em memória, no processo do portal (um worker, por design — mesmo
argumento do `ActivityTracker`): um restart zera a contagem, o que é aceitável
para janelas curtas. O relógio é injetável (`now`) para testes sem sleep.
"""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable

# Limite superior defensivo: dispara uma poda completa quando o número de
# chaves abandonadas (e-mails/IPs que nunca mais aparecem) cresce demais —
# a poda por acesso, sozinha, não alcança chaves que ninguém consulta mais.
_SWEEP_THRESHOLD = 10_000


class LoginThrottle:
    def __init__(
        self,
        *,
        max_failures: int,
        window_seconds: int,
        lock_seconds: int,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lock_seconds = lock_seconds
        self.now = now
        self._failures: dict[str, deque[float]] = {}
        self._locked_until: dict[str, float] = {}

    def retry_after_seconds(self, *keys: str) -> int | None:
        """Segundos até a liberação da chave mais restritiva, ou None.

        É também o ponto onde a recusa começa: uma chave com o limiar de
        falhas já atingido na janela é travada aqui, na primeira consulta
        seguinte — a tentativa que estoura o limiar ainda é processada
        normalmente e é a próxima que encontra a recusa.
        """
        current = self.now()
        wait: float | None = None
        for key in keys:
            release = self._release_at(key, current)
            if release is not None:
                wait = release - current if wait is None else min(wait, release - current)
        if wait is None:
            return None
        return max(1, math.ceil(wait))

    def record_failure(self, *keys: str) -> None:
        """Registra uma falha em cada chave informada (conta e origem)."""
        current = self.now()
        for key in keys:
            failures = self._failures.setdefault(key, deque())
            failures.append(current)
            self._prune(key, current)
        self._maybe_sweep(current)

    def record_success(self, key: str) -> None:
        """Zera a chave da conta após login bem-sucedido.

        Só a chave da conta é limpa — a de origem permanece, para conter o
        spraying de várias contas a partir de um mesmo IP.
        """
        self._failures.pop(key, None)
        self._locked_until.pop(key, None)

    def _release_at(self, key: str, current: float) -> float | None:
        """Instante de liberação da chave, travando-a se o limiar bateu.

        Recusa vencida zera também as falhas da janela: sem isso, falhas
        antigas ainda dentro da janela re-travariam a chave imediatamente a
        cada consulta seguinte (lock eterno disfarçado). Depois de esperar a
        recusa, a chave recomeça do zero.
        """
        locked_until = self._locked_until.get(key)
        if locked_until is not None:
            if locked_until > current:
                return locked_until
            del self._locked_until[key]
            self._failures.pop(key, None)

        self._prune(key, current)
        if len(self._failures.get(key, ())) >= self.max_failures:
            release = current + self.lock_seconds
            self._locked_until[key] = release
            return release
        return None

    def _prune(self, key: str, current: float) -> None:
        failures = self._failures.get(key)
        if failures is None:
            return
        horizon = current - self.window_seconds
        while failures and failures[0] <= horizon:
            failures.popleft()
        if not failures:
            del self._failures[key]

    def _maybe_sweep(self, current: float) -> None:
        if len(self._failures) < _SWEEP_THRESHOLD and len(self._locked_until) < _SWEEP_THRESHOLD:
            return
        for key in list(self._failures):
            self._prune(key, current)
        for key, until in list(self._locked_until.items()):
            if until <= current:
                del self._locked_until[key]

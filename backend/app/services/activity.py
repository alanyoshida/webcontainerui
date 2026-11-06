import time

from app.db import DbConnection, format_ts, utcnow


class ActivityTracker:
    """Acumula toques de atividade em memória e os persiste em lote (D8).

    O proxy vê centenas de mensagens por segundo; gravar `last_seen_at` a
    cada uma destruiria o SQLite. `touch` é barato e só atualiza um dict;
    `flush` é quem grava, chamado periodicamente por uma tarefa de fundo.
    """

    def __init__(self) -> None:
        self._pending: dict[str, object] = {}
        self._last_touch: dict[str, float] = {}

    def touch(self, instance_id: str) -> None:
        self._pending[instance_id] = format_ts(utcnow())

    def touch_throttled(self, instance_id: str, min_seconds: int) -> bool:
        """Toque com frequência limitada por instância.

        Usado pelo heartbeat da visão de sessão (change
        external-stream-proxy): o cliente pode repetir, mas o portal só
        considera um toque por janela. Devolve se o toque foi registrado."""
        now = time.monotonic()
        last = self._last_touch.get(instance_id)
        if last is not None and now - last < min_seconds:
            return False
        self._last_touch[instance_id] = now
        self.touch(instance_id)
        return True

    def flush(self, conn: DbConnection) -> int:
        pending = self._pending
        self._pending = {}
        for instance_id, timestamp in pending.items():
            conn.execute(
                "UPDATE instances SET last_seen_at = :now WHERE id = :instance_id",
                {"now": timestamp, "instance_id": instance_id},
            )
        return len(pending)

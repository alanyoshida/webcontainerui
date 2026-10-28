import sqlite3
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")


class ActivityTracker:
    """Acumula toques de atividade em memória e os persiste em lote (D8).

    O proxy vê centenas de mensagens por segundo; gravar `last_seen_at` a
    cada uma destruiria o SQLite. `touch` é barato e só atualiza um dict;
    `flush` é quem grava, chamado periodicamente por uma tarefa de fundo.
    """

    def __init__(self) -> None:
        self._pending: dict[str, str] = {}

    def touch(self, instance_id: str) -> None:
        self._pending[instance_id] = _now_iso()

    def flush(self, conn: sqlite3.Connection) -> int:
        pending = self._pending
        self._pending = {}
        for instance_id, timestamp in pending.items():
            conn.execute(
                "UPDATE instances SET last_seen_at = ? WHERE id = ?", (timestamp, instance_id)
            )
        return len(pending)

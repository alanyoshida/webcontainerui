import asyncio
import logging
from sqlalchemy.engine import Engine

from app.db import connect
from app.services.activity import ActivityTracker

logger = logging.getLogger(__name__)


async def run_activity_flusher(engine: Engine, tracker: ActivityTracker, interval_seconds: int) -> None:
    """Grava os toques pendentes a cada `interval_seconds`, indefinidamente.

    Cancelada pelo `lifespan` no desligamento (via `background.cancel_all`).
    Uma falha numa iteração não encerra o loop (10.3) — a próxima tenta de
    novo.
    """
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            conn = connect(engine)
            try:
                tracker.flush(conn)
            finally:
                conn.close()
        except Exception:
            logger.exception("falha numa iteração do flush de atividade")

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.engine import Engine, RowMapping

from app.config import Settings
from app.db import DbConnection, connect, format_ts, utcnow
from app.runtime.errors import ContainerNotFoundError
from app.runtime.protocol import ContainerRuntime, ContainerState
from app.services.instances import _close_run, stop_instance
from app.services.sessions import purge_sessions


def _cutoff(idle_timeout_minutes: int) -> str:
    return format_ts(utcnow() - timedelta(minutes=idle_timeout_minutes))


def find_idle_running_instances(
    conn: DbConnection, idle_timeout_minutes: int
) -> list[RowMapping]:
    """Instâncias em execução sem acesso há mais tempo que o limite.

    Uma instância nunca acessada (sem `last_seen_at`) conta a partir da
    criação, não é reaped instantaneamente.
    """
    return conn.execute(
        """SELECT id, user_id FROM instances
           WHERE state = 'running' AND deleted_at IS NULL
             AND COALESCE(last_seen_at, created_at) < :cutoff""",
        {"cutoff": _cutoff(idle_timeout_minutes)},
    ).fetchall()


async def reap_idle_instances(
    conn: DbConnection, runtime: ContainerRuntime, idle_timeout_minutes: int
) -> list[str]:
    """Para as instâncias ociosas encontradas, preservando os volumes
    (`stop_instance` nunca toca em volume)."""
    rows = find_idle_running_instances(conn, idle_timeout_minutes)
    for row in rows:
        await stop_instance(conn, runtime, row["id"], row["user_id"], reason="idle_timeout")
    return [row["id"] for row in rows]


async def reconcile_instance_states(conn: DbConnection, runtime: ContainerRuntime) -> list[str]:
    """Corrige o estado registrado quando ele diverge do container real.

    Chamada uma vez na inicialização (D8/design.md, seção de riscos):
    recupera a visão correta depois de um reinício do processo, quando
    containers podem ter sido encerrados por fora enquanto não havia
    ninguém observando.
    """
    rows = conn.execute(
        """SELECT id, container_id FROM instances
           WHERE state = 'running' AND deleted_at IS NULL AND container_id IS NOT NULL"""
    ).fetchall()

    reconciled = []
    for row in rows:
        try:
            state = await runtime.inspect_container(row["container_id"])
        except ContainerNotFoundError:
            state = None
        if state != ContainerState.RUNNING:
            _close_run(conn, row["id"], "reconciled")
            conn.execute(
                "UPDATE instances SET state = 'stopped' WHERE id = :instance_id",
                {"instance_id": row["id"]},
            )
            reconciled.append(row["id"])
    return reconciled


async def run_reaper(
    engine: Engine,
    runtime: ContainerRuntime,
    idle_timeout_minutes: int,
    interval_seconds: int,
    session_purge_grace_hours: int = 24,
    settings: Settings | None = None,
) -> None:
    """Loop periódico de ociosidade, reconciliação de estado e purga de
    sessões. Uma falha numa iteração não encerra o loop (D-risco "um worker
    é ponto único de falha", design.md) — a próxima iteração tenta de novo.

    Reconcilia antes de reaper: um container encerrado por fora (sem
    passar por `stop_instance`) precisa virar "stopped" no registro antes
    da checagem de ociosidade rodar sobre ele, senão a instância seria
    tratada como candidata a "parar por ociosidade" quando na verdade já
    parou por outro motivo — `reap_idle_instances` só considera
    `state = 'running'`, então a ordem é o que garante isso. A purga de
    sessões (change login-account-hygiene) fecha o ciclo: remove as linhas
    expiradas/revogadas além da carência, mantendo a tabela limitada.
    """
    logger = logging.getLogger(__name__)
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            conn = connect(engine)
            try:
                reconciled = await reconcile_instance_states(conn, runtime)
                stopped = await reap_idle_instances(conn, runtime, idle_timeout_minutes)
                if settings is not None:
                    from app.services.data_plane import withdraw_route

                    for instance_id in reconciled + stopped:
                        await withdraw_route(runtime, settings, instance_id)
                removidas = purge_sessions(conn, session_purge_grace_hours)
                if removidas:
                    logger.info("purga de sessões: %d linha(s) removida(s)", removidas)
            finally:
                conn.close()
        except Exception:
            logger.exception("falha numa iteração do reaper de ociosidade")

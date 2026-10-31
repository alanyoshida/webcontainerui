"""Consultas de métricas de uso de instâncias para o painel administrativo.

Todas as agregações por período tratam um run como pertencente ao período
quando seu intervalo (`started_at` até `ended_at`, ou agora se ainda aberto)
se sobrepõe a `[since, until]` — não é um corte estrito por `started_at`.
Isso é deliberado (D4/design.md): um run em curso contribui com sua duração
parcial, e um run de longa duração que começou antes do período ainda conta
integralmente, sem recorte, pela simplicidade de não precisar "fatiar"
durações na borda do período.
"""

import sqlite3
from datetime import datetime, time, timedelta, timezone

_RUN_SELECT = """
    SELECT r.id, r.instance_id, r.user_id, r.image_id, r.started_at, r.ended_at, r.ended_reason,
           u.email AS user_email,
           img.display_name AS image_display_name, img.repository AS image_repository,
           img.tag AS image_tag
    FROM instance_runs r
    JOIN users u ON u.id = r.user_id
    JOIN images img ON img.id = r.image_id
"""

_TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, _TS_FORMAT)


def default_period(days: int = 30) -> tuple[str, str]:
    """Janela padrão do painel: dos últimos `days` dias até agora."""
    until = _now_naive()
    since = until - timedelta(days=days)
    return since.strftime(_TS_FORMAT), until.strftime(_TS_FORMAT)


def duration_seconds(started_at: str, ended_at: str | None) -> float:
    start = _parse(started_at)
    end = _parse(ended_at) if ended_at else _now_naive()
    return (end - start).total_seconds()


def list_live_runs(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Instâncias com run aberto agora, usuário e imagem incluídos."""
    return conn.execute(_RUN_SELECT + " WHERE r.ended_at IS NULL ORDER BY r.started_at").fetchall()


def _runs_overlapping(conn: sqlite3.Connection, since: str, until: str) -> list[sqlite3.Row]:
    return conn.execute(
        _RUN_SELECT
        + """ WHERE r.started_at <= ? AND COALESCE(r.ended_at, datetime('now')) >= ?
              ORDER BY r.started_at""",
        (until, since),
    ).fetchall()


def list_runs(
    conn: sqlite3.Connection, since: str, until: str, *, limit: int = 50, offset: int = 0
) -> tuple[list[sqlite3.Row], int]:
    """Execuções (passadas e em curso) sobrepondo o período, paginadas,
    mais recentes primeiro."""
    total = conn.execute(
        """SELECT COUNT(*) FROM instance_runs
           WHERE started_at <= ? AND COALESCE(ended_at, datetime('now')) >= ?""",
        (until, since),
    ).fetchone()[0]
    rows = conn.execute(
        _RUN_SELECT
        + """ WHERE r.started_at <= ? AND COALESCE(r.ended_at, datetime('now')) >= ?
              ORDER BY r.started_at DESC LIMIT ? OFFSET ?""",
        (until, since, limit, offset),
    ).fetchall()
    return rows, total


def hours_by_user(conn: sqlite3.Connection, since: str, until: str) -> list[dict]:
    rows = _runs_overlapping(conn, since, until)
    totals: dict[int, dict] = {}
    for row in rows:
        entry = totals.setdefault(
            row["user_id"], {"user_id": row["user_id"], "email": row["user_email"], "seconds": 0.0}
        )
        entry["seconds"] += duration_seconds(row["started_at"], row["ended_at"])
    return sorted(totals.values(), key=lambda e: -e["seconds"])


def hours_by_group(conn: sqlite3.Connection, since: str, until: str) -> list[dict]:
    """Mesmo total de horas de `hours_by_user`, mas agregado por grupo.

    Um usuário em múltiplos grupos tem suas horas contadas em cada grupo a
    que pertence (D4/design.md) — os totais por grupo não necessariamente
    somam o total geral.
    """
    rows = _runs_overlapping(conn, since, until)
    user_seconds: dict[int, float] = {}
    for row in rows:
        user_seconds[row["user_id"]] = user_seconds.get(row["user_id"], 0.0) + duration_seconds(
            row["started_at"], row["ended_at"]
        )
    if not user_seconds:
        return []

    placeholders = ",".join("?" for _ in user_seconds)
    membership = conn.execute(
        f"""SELECT ug.user_id, g.id AS group_id, g.name FROM user_groups ug
            JOIN groups g ON g.id = ug.group_id
            WHERE ug.user_id IN ({placeholders})""",
        tuple(user_seconds.keys()),
    ).fetchall()

    totals: dict[int, dict] = {}
    for member in membership:
        entry = totals.setdefault(
            member["group_id"], {"group_id": member["group_id"], "name": member["name"], "seconds": 0.0}
        )
        entry["seconds"] += user_seconds[member["user_id"]]
    return sorted(totals.values(), key=lambda e: -e["seconds"])


def image_ranking(conn: sqlite3.Connection, since: str, until: str) -> list[dict]:
    rows = _runs_overlapping(conn, since, until)
    totals: dict[int, dict] = {}
    for row in rows:
        entry = totals.setdefault(
            row["image_id"],
            {
                "image_id": row["image_id"],
                "display_name": row["image_display_name"],
                "repository": row["image_repository"],
                "tag": row["image_tag"],
                "run_count": 0,
                "seconds": 0.0,
            },
        )
        entry["run_count"] += 1
        entry["seconds"] += duration_seconds(row["started_at"], row["ended_at"])
    return sorted(totals.values(), key=lambda e: -e["seconds"])


def reason_breakdown(conn: sqlite3.Connection, since: str, until: str) -> list[dict]:
    """Distribuição por motivo das execuções que terminaram dentro do
    período — diferente das demais agregações, que consideram sobreposição:
    aqui o que importa é quando o término aconteceu, não a duração."""
    rows = conn.execute(
        """SELECT ended_reason, COUNT(*) AS total FROM instance_runs
           WHERE ended_at IS NOT NULL AND ended_at >= ? AND ended_at <= ?
           GROUP BY ended_reason""",
        (since, until),
    ).fetchall()
    return [{"reason": row["ended_reason"], "count": row["total"]} for row in rows]


def daily_series(conn: sqlite3.Connection, since: str, until: str) -> list[dict]:
    """Quantidade de instâncias ativas em cada dia do período (intervalo do
    run sobrepondo aquele dia, não apenas o dia de início)."""
    rows = _runs_overlapping(conn, since, until)
    now = _now_naive()
    intervals = [
        (_parse(row["started_at"]), _parse(row["ended_at"]) if row["ended_at"] else now) for row in rows
    ]

    since_date = _parse(since).date()
    until_date = _parse(until).date()

    series = []
    day = since_date
    while day <= until_date:
        day_start = datetime.combine(day, time.min)
        day_end = datetime.combine(day, time.max)
        count = sum(1 for start, end in intervals if start <= day_end and end >= day_start)
        series.append({"date": day.isoformat(), "count": count})
        day += timedelta(days=1)
    return series


def peak_concurrency(conn: sqlite3.Connection, since: str, until: str) -> int:
    """Maior número de instâncias em execução ao mesmo tempo no período, por
    varredura (sweep-line) sobre os intervalos dos runs sobrepondo o
    período."""
    rows = _runs_overlapping(conn, since, until)
    now = _now_naive()
    events: list[tuple[datetime, int]] = []
    for row in rows:
        start = _parse(row["started_at"])
        end = _parse(row["ended_at"]) if row["ended_at"] else now
        events.append((start, 1))
        events.append((end, -1))
    # No empate de horário, processa início (+1) antes de fim (-1): dois
    # runs que se tocam exatamente no mesmo instante contam como
    # simultâneos naquele instante.
    events.sort(key=lambda e: (e[0], -e[1]))

    peak = current = 0
    for _, delta in events:
        current += delta
        peak = max(peak, current)
    return peak

"""Consultas de métricas de uso de instâncias para o painel administrativo.

Todas as agregações por período tratam um run como pertencente ao período
quando seu intervalo (`started_at` até `ended_at`, ou agora se ainda aberto)
se sobrepõe a `[since, until]` — não é um corte estrito por `started_at`.
Isso é deliberado (D4/design.md): um run em curso contribui com sua duração
parcial, e um run de longa duração que começou antes do período ainda conta
integralmente, sem recorte, pela simplicidade de não precisar "fatiar"
durações na borda do período.

Os parâmetros de período continuam chegando como texto (`YYYY-MM-DD HH:MM:SS`,
o contrato da API); as colunas são `DateTime` e voltam como `datetime` nos
dois motores — `_as_datetime` normaliza a borda (design.md D3).
"""

from datetime import datetime, time, timedelta, timezone

from sqlalchemy.engine import RowMapping

from app.db import DbConnection, as_datetime, format_ts

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


def default_period(days: int = 30) -> tuple[str, str]:
    """Janela padrão do painel: dos últimos `days` dias até agora.

    `until` avança para o próximo segundo inteiro: no PostgreSQL os defaults
    (`now()`) gravam microssegundos, e um run criado no mesmo segundo da
    consulta ficaria fora de uma janela truncada em segundos."""
    now = _now_naive()
    until = now.replace(microsecond=0) + timedelta(seconds=1)
    since = now - timedelta(days=days)
    return since.strftime(_TS_FORMAT), until.strftime(_TS_FORMAT)


def duration_seconds(started_at: datetime | str, ended_at: datetime | str | None) -> float:
    start = as_datetime(started_at)
    end = as_datetime(ended_at) if ended_at is not None else _now_naive()
    return (end - start).total_seconds()


def list_live_runs(conn: DbConnection) -> list[RowMapping]:
    """Instâncias com run aberto agora, usuário e imagem incluídos."""
    return conn.execute(_RUN_SELECT + " WHERE r.ended_at IS NULL ORDER BY r.started_at").fetchall()


def _runs_overlapping(
    conn: DbConnection, since: str, until: str
) -> list[RowMapping]:
    return conn.execute(
        _RUN_SELECT
        + """ WHERE r.started_at <= :until AND COALESCE(r.ended_at, :now) >= :since
              ORDER BY r.started_at""",
        {"until": format_ts(until), "since": format_ts(since), "now": format_ts(_now_naive())},
    ).fetchall()


def list_runs(
    conn: DbConnection, since: str, until: str, *, limit: int = 50, offset: int = 0
) -> tuple[list[RowMapping], int]:
    """Execuções (passadas e em curso) sobrepondo o período, paginadas,
    mais recentes primeiro."""
    params = {
        "until": format_ts(until),
        "since": format_ts(since),
        "now": format_ts(_now_naive()),
        "limit": limit,
        "offset": offset,
    }
    total = conn.execute(
        """SELECT COUNT(*) AS total FROM instance_runs
           WHERE started_at <= :until AND COALESCE(ended_at, :now) >= :since""",
        params,
    ).fetchone()["total"]
    rows = conn.execute(
        _RUN_SELECT
        + """ WHERE r.started_at <= :until AND COALESCE(r.ended_at, :now) >= :since
              ORDER BY r.started_at DESC LIMIT :limit OFFSET :offset""",
        params,
    ).fetchall()
    return rows, total


def hours_by_user(conn: DbConnection, since: str, until: str) -> list[dict]:
    rows = _runs_overlapping(conn, since, until)
    totals: dict[int, dict] = {}
    for row in rows:
        entry = totals.setdefault(
            row["user_id"], {"user_id": row["user_id"], "email": row["user_email"], "seconds": 0.0}
        )
        entry["seconds"] += duration_seconds(row["started_at"], row["ended_at"])
    return sorted(totals.values(), key=lambda e: -e["seconds"])


def hours_by_group(conn: DbConnection, since: str, until: str) -> list[dict]:
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

    user_params = {f"u{i}": user_id for i, user_id in enumerate(user_seconds)}
    placeholders = ", ".join(f":{key}" for key in user_params)
    membership = conn.execute(
        f"""SELECT ug.user_id, g.id AS group_id, g.name FROM user_groups ug
            JOIN groups g ON g.id = ug.group_id
            WHERE ug.user_id IN ({placeholders})""",
        user_params,
    ).fetchall()

    totals: dict[int, dict] = {}
    for member in membership:
        entry = totals.setdefault(
            member["group_id"], {"group_id": member["group_id"], "name": member["name"], "seconds": 0.0}
        )
        entry["seconds"] += user_seconds[member["user_id"]]
    return sorted(totals.values(), key=lambda e: -e["seconds"])


def image_ranking(conn: DbConnection, since: str, until: str) -> list[dict]:
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


def reason_breakdown(conn: DbConnection, since: str, until: str) -> list[dict]:
    """Distribuição por motivo das execuções que terminaram dentro do
    período — diferente das demais agregações, que consideram sobreposição:
    aqui o que importa é quando o término aconteceu, não a duração."""
    rows = conn.execute(
        """SELECT ended_reason, COUNT(*) AS total FROM instance_runs
           WHERE ended_at IS NOT NULL AND ended_at >= :since AND ended_at <= :until
           GROUP BY ended_reason""",
        {"since": format_ts(since), "until": format_ts(until)},
    ).fetchall()
    return [{"reason": row["ended_reason"], "count": row["total"]} for row in rows]


def daily_series(conn: DbConnection, since: str, until: str) -> list[dict]:
    """Quantidade de instâncias ativas em cada dia do período (intervalo do
    run sobrepondo aquele dia, não apenas o dia de início)."""
    rows = _runs_overlapping(conn, since, until)
    now = _now_naive()
    intervals = [
        (
            as_datetime(row["started_at"]),
            as_datetime(row["ended_at"]) if row["ended_at"] is not None else now,
        )
        for row in rows
    ]

    since_date = as_datetime(since).date()
    until_date = as_datetime(until).date()

    series = []
    day = since_date
    while day <= until_date:
        day_start = datetime.combine(day, time.min)
        day_end = datetime.combine(day, time.max)
        count = sum(1 for start, end in intervals if start <= day_end and end >= day_start)
        series.append({"date": day.isoformat(), "count": count})
        day += timedelta(days=1)
    return series


def peak_concurrency(conn: DbConnection, since: str, until: str) -> int:
    """Maior número de instâncias em execução ao mesmo tempo no período, por
    varredura (sweep-line) sobre os intervalos dos runs sobrepondo o
    período."""
    rows = _runs_overlapping(conn, since, until)
    now = _now_naive()
    events: list[tuple[datetime, int]] = []
    for row in rows:
        start = as_datetime(row["started_at"])
        end = as_datetime(row["ended_at"]) if row["ended_at"] is not None else now
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

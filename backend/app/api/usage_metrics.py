import sqlite3

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.deps import get_db, require_admin
from app.services import usage_metrics

router = APIRouter(dependencies=[Depends(require_admin)])


class LiveRunResponse(BaseModel):
    instance_id: str
    user_id: int
    user_email: str
    image_id: int
    image_display_name: str
    image_repository: str
    image_tag: str
    started_at: str
    duration_seconds: float


class RunResponse(BaseModel):
    id: int
    instance_id: str
    user_id: int
    user_email: str
    image_id: int
    image_display_name: str
    image_repository: str
    image_tag: str
    started_at: str
    ended_at: str | None
    ended_reason: str | None
    duration_seconds: float


class RunsPageResponse(BaseModel):
    items: list[RunResponse]
    total: int


class UserHoursResponse(BaseModel):
    user_id: int
    email: str
    seconds: float


class GroupHoursResponse(BaseModel):
    group_id: int
    name: str
    seconds: float


class ImageRankingResponse(BaseModel):
    image_id: int
    display_name: str
    repository: str
    tag: str
    run_count: int
    seconds: float


class ReasonBreakdownResponse(BaseModel):
    reason: str
    count: int


class DailySeriesPointResponse(BaseModel):
    date: str
    count: int


class SummaryResponse(BaseModel):
    by_user: list[UserHoursResponse]
    by_group: list[GroupHoursResponse]
    image_ranking: list[ImageRankingResponse]
    reason_breakdown: list[ReasonBreakdownResponse]
    daily_series: list[DailySeriesPointResponse]
    peak_concurrency: int


def _live_to_response(row: sqlite3.Row) -> LiveRunResponse:
    return LiveRunResponse(
        instance_id=row["instance_id"],
        user_id=row["user_id"],
        user_email=row["user_email"],
        image_id=row["image_id"],
        image_display_name=row["image_display_name"],
        image_repository=row["image_repository"],
        image_tag=row["image_tag"],
        started_at=row["started_at"],
        duration_seconds=usage_metrics.duration_seconds(row["started_at"], None),
    )


def _run_to_response(row: sqlite3.Row) -> RunResponse:
    return RunResponse(
        id=row["id"],
        instance_id=row["instance_id"],
        user_id=row["user_id"],
        user_email=row["user_email"],
        image_id=row["image_id"],
        image_display_name=row["image_display_name"],
        image_repository=row["image_repository"],
        image_tag=row["image_tag"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        ended_reason=row["ended_reason"],
        duration_seconds=usage_metrics.duration_seconds(row["started_at"], row["ended_at"]),
    )


@router.get("/usage/live", response_model=list[LiveRunResponse])
def list_live_usage_endpoint(db: sqlite3.Connection = Depends(get_db)) -> list[LiveRunResponse]:
    return [_live_to_response(row) for row in usage_metrics.list_live_runs(db)]


@router.get("/usage/runs", response_model=RunsPageResponse)
def list_usage_runs_endpoint(
    limit: int = 50, offset: int = 0, db: sqlite3.Connection = Depends(get_db)
) -> RunsPageResponse:
    since, until = usage_metrics.default_period()
    rows, total = usage_metrics.list_runs(db, since, until, limit=limit, offset=offset)
    return RunsPageResponse(items=[_run_to_response(row) for row in rows], total=total)


@router.get("/usage/summary", response_model=SummaryResponse)
def usage_summary_endpoint(db: sqlite3.Connection = Depends(get_db)) -> SummaryResponse:
    since, until = usage_metrics.default_period()
    return SummaryResponse(
        by_user=[UserHoursResponse(**entry) for entry in usage_metrics.hours_by_user(db, since, until)],
        by_group=[GroupHoursResponse(**entry) for entry in usage_metrics.hours_by_group(db, since, until)],
        image_ranking=[
            ImageRankingResponse(**entry) for entry in usage_metrics.image_ranking(db, since, until)
        ],
        reason_breakdown=[
            ReasonBreakdownResponse(**entry) for entry in usage_metrics.reason_breakdown(db, since, until)
        ],
        daily_series=[
            DailySeriesPointResponse(**entry) for entry in usage_metrics.daily_series(db, since, until)
        ],
        peak_concurrency=usage_metrics.peak_concurrency(db, since, until),
    )

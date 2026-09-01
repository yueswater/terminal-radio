"""Endpoints exposing the listening history."""

from __future__ import annotations

from fastapi import APIRouter, Query

from terminal_radio.dependencies import RadioServiceDep
from terminal_radio.schemas import HistoryRead, NowPlayingListRead, SummaryListRead

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=HistoryRead, summary="List history events")
def list_events(
    service: RadioServiceDep,
    limit: int | None = Query(default=None, gt=0, description="Newest events to return"),
) -> HistoryRead:
    """Return the most recent history events, newest first."""
    return HistoryRead.from_domain(service.history(limit))


@router.get("/summary", response_model=SummaryListRead, summary="Listening totals")
def list_summaries(
    service: RadioServiceDep,
    limit: int | None = Query(default=None, gt=0, description="Events to aggregate"),
) -> SummaryListRead:
    """Return listening totals per station, most listened first."""
    return SummaryListRead.from_domain(service.summaries(limit))


@router.get(
    "/now-playing",
    response_model=NowPlayingListRead,
    summary="Titles the stations announced",
)
def list_now_playing(
    service: RadioServiceDep,
    limit: int | None = Query(default=None, gt=0, description="Newest titles to return"),
) -> NowPlayingListRead:
    """Return what the stations said they were playing, newest first."""
    return NowPlayingListRead.from_domain(service.now_playing(limit))

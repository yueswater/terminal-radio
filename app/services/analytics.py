"""Aggregate completed plays into user-facing listening statistics."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, tzinfo

from app.constants.analytics import (
    BAND_ORDER,
    DAYPART_ORDER,
    OTHER_BAND,
    TOP_STATIONS_LIMIT,
    TREND_DAYS,
)
from app.enums import Daypart, HistoryEventType
from app.models import HistoryEvent
from app.services.history import StationSummary


@dataclass(frozen=True)
class DailyListening:
    """Listening seconds assigned to one local calendar date."""

    day: date
    seconds: float


@dataclass(frozen=True)
class ListeningStatistics:
    """All aggregates rendered by the listening statistics page."""

    total_listened_seconds: float
    play_count: int
    active_days: int
    longest_session_seconds: float
    average_session_seconds: float
    top_stations: tuple[StationSummary, ...]
    daily_trend: tuple[DailyListening, ...]
    weekday_seconds: tuple[float, ...]
    daypart_seconds: dict[Daypart, float]
    band_seconds: dict[str, float]


def build_listening_statistics(
    events: Iterable[HistoryEvent],
    *,
    today: date | None = None,
    timezone: tzinfo | None = None,
) -> ListeningStatistics:
    """Build statistics from completed plays, using local end times."""
    local_timezone = timezone or datetime.now().astimezone().tzinfo or UTC
    local_today = today or datetime.now(local_timezone).date()
    first_trend_day = local_today - timedelta(days=TREND_DAYS - 1)
    daily = {
        first_trend_day + timedelta(days=offset): 0.0
        for offset in range(TREND_DAYS)
    }
    weekdays = [0.0] * 7
    dayparts = {part: 0.0 for part in DAYPART_ORDER}
    bands: defaultdict[str, float] = defaultdict(float)
    grouped: defaultdict[str, list[HistoryEvent]] = defaultdict(list)
    active_dates: set[date] = set()
    durations: list[float] = []

    for event in events:
        if event.type is not HistoryEventType.PLAY_ENDED or not event.station_slug:
            continue
        local_at = _as_local(event.at, local_timezone)
        seconds = event.listened_seconds
        durations.append(seconds)
        active_dates.add(local_at.date())
        weekdays[local_at.weekday()] += seconds
        dayparts[_daypart(local_at.hour)] += seconds
        bands[_band(event.station_dial)] += seconds
        grouped[event.station_slug].append(event)
        if local_at.date() in daily:
            daily[local_at.date()] += seconds

    top_stations = tuple(
        sorted(
            (_summarize(slug, items) for slug, items in grouped.items()),
            key=lambda item: item.listened_seconds,
            reverse=True,
        )[:TOP_STATIONS_LIMIT]
    )
    total = sum(durations)
    ordered_bands = {
        name: bands[name]
        for name in (*BAND_ORDER, OTHER_BAND)
        if bands[name] > 0
    }
    return ListeningStatistics(
        total_listened_seconds=total,
        play_count=len(durations),
        active_days=len(active_dates),
        longest_session_seconds=max(durations, default=0.0),
        average_session_seconds=total / len(durations) if durations else 0.0,
        top_stations=top_stations,
        daily_trend=tuple(
            DailyListening(day=day, seconds=seconds)
            for day, seconds in daily.items()
        ),
        weekday_seconds=tuple(weekdays),
        daypart_seconds=dayparts,
        band_seconds=ordered_bands,
    )


def _as_local(value: datetime, timezone: tzinfo) -> datetime:
    source = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return source.astimezone(timezone)


def _daypart(hour: int) -> Daypart:
    if 5 <= hour < 12:
        return Daypart.MORNING
    if 12 <= hour < 18:
        return Daypart.AFTERNOON
    if 18 <= hour < 22:
        return Daypart.EVENING
    return Daypart.NIGHT


def _band(dial: str | None) -> str:
    normalized = (dial or "").strip().upper()
    for band in BAND_ORDER:
        if normalized.startswith(band):
            return band
    return OTHER_BAND


def _summarize(slug: str, events: list[HistoryEvent]) -> StationSummary:
    newest = max(events, key=lambda event: event.at)
    return StationSummary(
        station_slug=slug,
        station_name=newest.station_name or slug,
        station_dial=newest.station_dial,
        play_count=len(events),
        listened_seconds=sum(event.listened_seconds for event in events),
        paused_seconds=sum(event.paused_seconds or 0.0 for event in events),
        last_played_at=newest.at,
    )

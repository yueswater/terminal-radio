"""Append only history log of listening activity."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.enums import HistoryEventType
from app.models import HistoryEvent, Station


class StationSummary(BaseModel):
    """Aggregated listening time of one station."""

    station_slug: str
    station_name: str
    station_dial: str | None = None
    play_count: int = 0
    listened_seconds: float = 0.0
    paused_seconds: float = 0.0
    last_played_at: datetime | None = None


class HistoryLog:
    """Stores events as JSON lines and reads them back newest first."""

    def __init__(self, path: Path, limit: int = 200) -> None:
        self._path = path
        self._limit = limit

    def append(self, event: HistoryEvent) -> None:
        """Add one event, silently ignoring an unwritable location."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as stream:
                stream.write(event.model_dump_json() + "\n")
        except OSError:
            return

    def read(self, limit: int | None = None) -> tuple[HistoryEvent, ...]:
        """Return the most recent events, newest first."""
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return ()

        events: list[HistoryEvent] = []
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                events.append(HistoryEvent(**json.loads(line)))
            except (json.JSONDecodeError, TypeError, ValidationError):
                continue
            if len(events) >= (limit or self._limit):
                break

        return tuple(events)

    def clear(self) -> bool:
        """Remove every stored event and report whether it succeeded."""
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            return False
        return True

    def summarize(self, limit: int | None = None) -> tuple[StationSummary, ...]:
        """Aggregate finished plays per station, most listened first."""
        totals: dict[str, StationSummary] = {}
        grouped: dict[str, list[HistoryEvent]] = defaultdict(list)

        for event in self.read(limit):
            if event.type is HistoryEventType.PLAY_ENDED and event.station_slug:
                grouped[event.station_slug].append(event)

        for slug, events in grouped.items():
            summary = StationSummary(
                station_slug=slug,
                station_name=events[0].station_name or slug,
                station_dial=events[0].station_dial,
            )
            for event in events:
                summary.play_count += 1
                summary.listened_seconds += event.listened_seconds
                summary.paused_seconds += event.paused_seconds or 0.0
                if summary.last_played_at is None or event.at > summary.last_played_at:
                    summary.last_played_at = event.at
            totals[slug] = summary

        return tuple(
            sorted(totals.values(), key=lambda item: item.listened_seconds, reverse=True)
        )


def build_event(
    event_type: HistoryEventType,
    station: Station | None = None,
    duration_seconds: float | None = None,
    paused_seconds: float | None = None,
) -> HistoryEvent:
    """Build a timestamped event for the given station."""
    return HistoryEvent(
        at=datetime.now(UTC),
        type=event_type,
        station_slug=station.slug if station else None,
        station_name=station.name if station else None,
        station_dial=station.dial if station else None,
        duration_seconds=duration_seconds,
        paused_seconds=paused_seconds,
    )

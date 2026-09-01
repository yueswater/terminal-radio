"""Response payloads of the history endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from terminal_radio.enums import HistoryEventType
from terminal_radio.models import HistoryEvent
from terminal_radio.models.now_playing import NowPlayingEntry
from terminal_radio.services.history import StationSummary


class HistoryEventRead(BaseModel):
    """Public representation of one history event."""

    at: datetime
    type: HistoryEventType
    station_slug: str | None = None
    station_name: str | None = None
    station_dial: str | None = None
    duration_seconds: float | None = None
    paused_seconds: float | None = None
    listened_seconds: float

    @classmethod
    def from_domain(cls, event: HistoryEvent) -> "HistoryEventRead":
        """Build the payload from a domain event."""
        return cls(listened_seconds=event.listened_seconds, **event.model_dump())


class StationSummaryRead(BaseModel):
    """Public representation of the totals of one station."""

    station_slug: str
    station_name: str
    station_dial: str | None = None
    play_count: int
    listened_seconds: float
    paused_seconds: float
    last_played_at: datetime | None = None

    @classmethod
    def from_domain(cls, summary: StationSummary) -> "StationSummaryRead":
        """Build the payload from a domain summary."""
        return cls(**summary.model_dump())


class HistoryRead(BaseModel):
    """Envelope returned when listing history events."""

    total: int
    items: list[HistoryEventRead]

    @classmethod
    def from_domain(cls, events: tuple[HistoryEvent, ...]) -> "HistoryRead":
        """Build the payload from a tuple of domain events."""
        items = [HistoryEventRead.from_domain(event) for event in events]
        return cls(total=len(items), items=items)


class SummaryListRead(BaseModel):
    """Envelope returned when listing per station totals."""

    total: int
    items: list[StationSummaryRead]

    @classmethod
    def from_domain(cls, summaries: tuple[StationSummary, ...]) -> "SummaryListRead":
        """Build the payload from a tuple of domain summaries."""
        items = [StationSummaryRead.from_domain(summary) for summary in summaries]
        return cls(total=len(items), items=items)


class NowPlayingRead(BaseModel):
    """Public representation of one announced title."""

    at: datetime
    station_slug: str
    station_name: str
    title: str

    @classmethod
    def from_domain(cls, entry: NowPlayingEntry) -> "NowPlayingRead":
        """Build the payload from a domain entry."""
        return cls(**entry.model_dump())


class NowPlayingListRead(BaseModel):
    """Envelope returned when listing announced titles."""

    total: int
    items: list[NowPlayingRead]

    @classmethod
    def from_domain(
        cls, entries: tuple[NowPlayingEntry, ...]
    ) -> "NowPlayingListRead":
        """Build the payload from a tuple of domain entries."""
        items = [NowPlayingRead.from_domain(entry) for entry in entries]
        return cls(total=len(items), items=items)

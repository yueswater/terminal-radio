"""Models describing what the listener did and when."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

from terminal_radio.enums import HistoryEventType


class HistoryEvent(BaseModel):
    """One line of the history log."""

    at: datetime
    type: HistoryEventType
    station_slug: str | None = None
    station_name: str | None = None
    station_dial: str | None = None
    duration_seconds: float | None = Field(
        default=None, description="Wall clock time covered by the event"
    )
    paused_seconds: float | None = Field(
        default=None, description="Time spent paused inside the event"
    )
    interrupted_seconds: float = Field(
        default=0.0,
        ge=0,
        description="Time playback was unavailable while reconnecting",
    )

    @property
    def listened_seconds(self) -> float:
        """Return the time actually heard, excluding pauses and interruptions."""
        duration = self.duration_seconds or 0.0
        return max(
            duration - (self.paused_seconds or 0.0) - self.interrupted_seconds,
            0.0,
        )

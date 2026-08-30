"""Models describing what the listener did and when."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

from app.enums import HistoryEventType


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

    @property
    def listened_seconds(self) -> float:
        """Return the time actually heard, excluding pauses."""
        duration = self.duration_seconds or 0.0
        return max(duration - (self.paused_seconds or 0.0), 0.0)

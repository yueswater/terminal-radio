"""What a station said it was playing, and when it said so."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NowPlayingEntry(BaseModel):
    """One title a station advertised.

    This is the station's own timeline, not the listener's. It says what was on
    the air; the listening history says what the listener did about it.
    """

    model_config = {"frozen": True}

    at: datetime
    station_slug: str
    station_name: str
    title: str = Field(min_length=1)

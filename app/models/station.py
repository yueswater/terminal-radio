"""Domain models describing stations and playback state."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Band(StrEnum):
    """Broadcast band a station is transmitted on."""

    FM = "FM"
    AM = "AM"


class PlaybackState(StrEnum):
    """Lifecycle of the audio backend."""

    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class Station(BaseModel):
    """A single radio stream entry of the catalog."""

    model_config = {"frozen": True}

    slug: str = Field(description="Stable identifier used by the API and the UI")
    name: str
    band: Band
    url: str
    frequency: str | None = None
    description: str | None = None

    @property
    def dial(self) -> str:
        """Return the band and frequency as shown on a radio dial."""
        return f"{self.band} {self.frequency}" if self.frequency else str(self.band)


class PlayerStatus(BaseModel):
    """Snapshot of what the player is doing right now."""

    state: PlaybackState = PlaybackState.STOPPED
    station: Station | None = None
    program: str | None = Field(
        default=None, description="Title reported by the stream metadata"
    )
    elapsed_seconds: float = Field(
        default=0.0, description="Wall clock time since playback started"
    )
    paused_seconds: float = Field(
        default=0.0, description="Time spent paused since playback started"
    )
    volume: int = Field(default=100, ge=0, le=130)
    muted: bool = False
    device: str | None = Field(default=None, description="Audio output in use")

    @property
    def is_playing(self) -> bool:
        """Return whether a stream is loaded, playing or paused."""
        return self.state in (PlaybackState.PLAYING, PlaybackState.PAUSED)

    @property
    def is_paused(self) -> bool:
        """Return whether playback is paused."""
        return self.state is PlaybackState.PAUSED

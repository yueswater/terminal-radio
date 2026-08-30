"""Domain models describing stations and playback state."""

from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from app.enums import Band, PlaybackState


class Station(BaseModel):
    """A single radio stream entry of the catalog."""

    model_config = {"frozen": True}

    slug: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
        description="Stable identifier used by the API and the UI",
    )
    name: str = Field(min_length=1, max_length=80)
    band: Band
    url: str = Field(min_length=1)
    frequency: str | None = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=160)

    @field_validator("url")
    @classmethod
    def validate_stream_url(cls, value: str) -> str:
        """Accept only absolute HTTP(S) stream addresses."""
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError("station URL must use HTTP or HTTPS")
        return value

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
    reconnect_attempt: int = Field(default=0, ge=0)
    sleep_remaining_seconds: float | None = Field(default=None, ge=0)

    @property
    def is_playing(self) -> bool:
        """Return whether a stream is loaded, playing or paused."""
        return self.state in (
            PlaybackState.PLAYING,
            PlaybackState.PAUSED,
            PlaybackState.RECONNECTING,
        )

    @property
    def is_paused(self) -> bool:
        """Return whether playback is paused."""
        return self.state is PlaybackState.PAUSED

"""Request and response payloads of the player endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

from terminal_radio.enums import PlaybackState
from terminal_radio.models import PlayerStatus
from terminal_radio.schemas.station import StationRead


class PlayRequest(BaseModel):
    """Body of a play or toggle request."""

    slug: str = Field(min_length=1)


class VolumeRequest(BaseModel):
    """Body of a volume request: an absolute level, or a step to move by."""

    level: int | None = Field(default=None, ge=0, le=130)
    delta: int | None = Field(default=None, ge=-130, le=130)


class MuteRequest(BaseModel):
    """Body of a mute request."""

    muted: bool


class SleepRequest(BaseModel):
    """Body of a sleep timer request. Null minutes cancels the timer."""

    minutes: int | None = Field(default=None, ge=1, le=1440)


class PlayerStatusRead(BaseModel):
    """Public representation of the playback status."""

    state: PlaybackState
    station: StationRead | None = None
    program: str | None = None
    elapsed_seconds: float = 0.0
    paused_seconds: float = 0.0
    volume: int = 100
    muted: bool = False
    device: str | None = None
    reconnect_attempt: int = 0
    sleep_remaining_seconds: float | None = None
    stream_index: int = 0
    stream_count: int = 1
    using_fallback: bool = False

    @classmethod
    def from_domain(cls, status: PlayerStatus) -> "PlayerStatusRead":
        """Build the payload from a domain status."""
        station = StationRead.from_domain(status.station) if status.station else None
        return cls(
            state=status.state,
            station=station,
            program=status.program,
            elapsed_seconds=status.elapsed_seconds,
            paused_seconds=status.paused_seconds,
            volume=status.volume,
            muted=status.muted,
            device=status.device,
            reconnect_attempt=status.reconnect_attempt,
            sleep_remaining_seconds=status.sleep_remaining_seconds,
            stream_index=status.stream_index,
            stream_count=status.stream_count,
            using_fallback=status.using_fallback,
        )

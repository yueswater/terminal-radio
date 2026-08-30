"""Request and response payloads of the player endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models import PlaybackState, PlayerStatus
from app.schemas.station import StationRead


class PlayRequest(BaseModel):
    """Body of a play or toggle request."""

    slug: str = Field(min_length=1)


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
        )

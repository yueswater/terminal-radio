"""Domain models describing stations and playback state."""

from __future__ import annotations

import re
from collections.abc import Sequence
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from terminal_radio.enums import Band, Genre, PlaybackState, Region

# A BCP 47 tag: a two or three letter language, then any number of subtags.
# Matching the shape is enough here. The registry is not worth carrying, and a
# tag that parses but names nothing simply matches no filter.
LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


def unique(values: Sequence[object]) -> tuple[object, ...]:
    """Return the values with later duplicates dropped, keeping their order."""
    seen: list[object] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return tuple(seen)


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
    short_name: str | None = Field(default=None, min_length=1, max_length=40)
    band: Band
    url: str = Field(min_length=1, description="Address tried first")
    fallback_urls: tuple[str, ...] = Field(
        default=(),
        description="Addresses tried in turn when the one before it goes quiet",
    )
    frequency: str | None = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=160)
    network: str | None = Field(
        default=None,
        min_length=1,
        max_length=60,
        description="Family a station belongs to, which groups its frequencies",
    )
    regions: tuple[Region, ...] = Field(
        default=(), description="Areas the station mainly serves"
    )
    genres: tuple[Genre, ...] = Field(
        default=(), description="What the station mostly broadcasts"
    )
    languages: tuple[str, ...] = Field(
        default=(), description="BCP 47 tags of the languages heard on air"
    )

    @field_validator("url")
    @classmethod
    def validate_stream_url(cls, value: str) -> str:
        """Accept only absolute HTTP(S) stream addresses."""
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError("station URL must use HTTP or HTTPS")
        return value

    @field_validator("fallback_urls", mode="after")
    @classmethod
    def validate_fallback_urls(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Hold every backup to the same rule as the address it stands in for."""
        for url in value:
            cls.validate_stream_url(url)
        return unique(value)

    @field_validator("regions", "genres", "languages", mode="after")
    @classmethod
    def drop_repeats(cls, value: tuple[object, ...]) -> tuple[object, ...]:
        """Keep a listed order but never the same entry twice."""
        return unique(value)

    @field_validator("languages", mode="after")
    @classmethod
    def validate_language_tags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Accept only well shaped BCP 47 tags."""
        for tag in value:
            if not LANGUAGE_TAG.match(tag):
                raise ValueError(f"not a BCP 47 language tag: {tag}")
        return value

    @property
    def stream_urls(self) -> tuple[str, ...]:
        """Return every address of this station, the one to try first ahead."""
        return (self.url, *(item for item in self.fallback_urls if item != self.url))

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
    stream_index: int = Field(
        default=0, ge=0, description="Which address of the station is playing"
    )
    stream_count: int = Field(
        default=1, ge=1, description="How many addresses the station offers"
    )

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

    @property
    def using_fallback(self) -> bool:
        """Return whether the address playing is a backup rather than the first."""
        return self.stream_index > 0

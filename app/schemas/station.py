"""Request and response payloads of the stations endpoints."""

from __future__ import annotations

from pydantic import BaseModel

from app.enums import Band
from app.models import Station


class StationRead(BaseModel):
    """Public representation of a station."""

    slug: str
    name: str
    short_name: str | None = None
    band: Band
    dial: str
    url: str
    frequency: str | None = None
    description: str | None = None

    @classmethod
    def from_domain(cls, station: Station) -> "StationRead":
        """Build the payload from a domain station."""
        return cls(dial=station.dial, **station.model_dump())


class StationListRead(BaseModel):
    """Envelope returned when listing stations."""

    total: int
    items: list[StationRead]

    @classmethod
    def from_domain(cls, stations: tuple[Station, ...]) -> "StationListRead":
        """Build the payload from a tuple of domain stations."""
        items = [StationRead.from_domain(station) for station in stations]
        return cls(total=len(items), items=items)

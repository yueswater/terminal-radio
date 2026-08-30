"""Loading and lookup of the station catalog."""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from pathlib import Path

from pydantic import ValidationError

from app.core.exceptions import CatalogError, StationNotFoundError
from app.models import Band, Station


class StationCatalog:
    """An ordered, immutable collection of stations keyed by slug."""

    def __init__(self, stations: list[Station]) -> None:
        if not stations:
            raise CatalogError("Station catalog is empty")

        self._stations = tuple(stations)
        self._by_slug = {station.slug: station for station in self._stations}

        if len(self._by_slug) != len(self._stations):
            raise CatalogError("Station slugs must be unique")

    @classmethod
    def from_file(cls, path: Path) -> "StationCatalog":
        """Read a TOML catalog file and build a catalog out of it."""
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise CatalogError(f"Cannot read station catalog: {path}") from error
        except tomllib.TOMLDecodeError as error:
            raise CatalogError(f"Malformed station catalog: {path}") from error

        try:
            stations = [Station(**entry) for entry in raw.get("stations", [])]
        except (TypeError, ValidationError) as error:
            raise CatalogError(f"Invalid station entry in {path}") from error

        return cls(stations)

    def all(self) -> tuple[Station, ...]:
        """Return every station in declaration order."""
        return self._stations

    def get(self, slug: str) -> Station:
        """Return the station with the given slug or raise StationNotFoundError."""
        try:
            return self._by_slug[slug]
        except KeyError:
            raise StationNotFoundError(slug) from None

    def by_band(self, band: Band) -> tuple[Station, ...]:
        """Return every station of one broadcast band, in declaration order."""
        return tuple(station for station in self._stations if station.band is band)

    def bands(self) -> tuple[Band, ...]:
        """Return the bands present in the catalog, in declaration order."""
        ordered: list[Band] = []
        for station in self._stations:
            if station.band not in ordered:
                ordered.append(station.band)
        return tuple(ordered)

    def first(self) -> Station:
        """Return the station used as the initial selection."""
        return self._stations[0]

    def __iter__(self) -> Iterator[Station]:
        return iter(self._stations)

    def __len__(self) -> int:
        return len(self._stations)

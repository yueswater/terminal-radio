"""Ranked, filterable search over the station catalog.

One grammar serves every caller. The terminal UI, the command line and the HTTP
API all hand a raw string to :func:`search_stations`, so a query learned in one
place works in the others:

    genre:news region:taipei 廣播

A ``key:value`` term narrows the result, a bare word ranks what is left. Terms
that name the same key widen it, terms that name different keys narrow it: the
query above asks for the news stations of Taipei, not for either of them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from terminal_radio.enums import Band, Genre, Region
from terminal_radio.models import Station

# Match qualities, best first. A station is placed in the first band it
# satisfies, so a dial the listener typed in full always outranks the same
# digits happening to appear in somebody's description.
EXACT_FREQUENCY = 0
FREQUENCY_PREFIX = 1
NAME_PREFIX = 2
DIAL_MATCH = 3
NAME_MATCH = 4
METADATA_MATCH = 5
OTHER_MATCH = 6

# The filters a query may name, and the plural spelling each one accepts.
FILTER_KEYS = {
    "band": "bands",
    "genre": "genres",
    "language": "languages",
    "lang": "languages",
    "network": "networks",
    "region": "regions",
}


@dataclass(frozen=True)
class StationQuery:
    """A parsed query: the filters to satisfy, and the text to rank by."""

    text: str = ""
    bands: frozenset[str] = frozenset()
    genres: frozenset[str] = frozenset()
    languages: frozenset[str] = frozenset()
    networks: frozenset[str] = frozenset()
    regions: frozenset[str] = frozenset()
    # Terms naming a filter that has no such value, such as genre:banana. They
    # match nothing, and are kept so a caller can say why the result is empty.
    unknown: tuple[str, ...] = field(default=())

    @property
    def is_empty(self) -> bool:
        """Return whether the query asks for nothing at all."""
        return not (
            self.text
            or self.bands
            or self.genres
            or self.languages
            or self.networks
            or self.regions
            or self.unknown
        )


def parse_query(query: str) -> StationQuery:
    """Split a raw query into its filters and its free text."""
    collected: dict[str, set[str]] = {name: set() for name in FILTER_KEYS.values()}
    unknown: list[str] = []
    words: list[str] = []

    for token in query.split():
        key, separator, value = token.partition(":")
        field_name = FILTER_KEYS.get(key.casefold()) if separator else None
        if field_name is None or not value:
            # Anything that is not a filter is text to rank by, colon and all,
            # so a pasted URL or a station named "Hit:FM" still searches.
            words.append(token)
            continue

        wanted = value.casefold()
        if _is_known(field_name, wanted):
            collected[field_name].add(wanted)
        else:
            unknown.append(token)

    return StationQuery(
        text=" ".join(words).strip().casefold(),
        bands=frozenset(collected["bands"]),
        genres=frozenset(collected["genres"]),
        languages=frozenset(collected["languages"]),
        networks=frozenset(collected["networks"]),
        regions=frozenset(collected["regions"]),
        unknown=tuple(unknown),
    )


def _is_known(field_name: str, value: str) -> bool:
    """Return whether a filter value names something the catalog can hold.

    A network is written by whoever wrote the catalog, so any text is allowed
    there. The rest are closed sets, and a typo in one is worth reporting.
    """
    match field_name:
        case "bands":
            return value.upper() in tuple(Band)
        case "genres":
            return value in tuple(Genre)
        case "regions":
            return value in tuple(Region)
        case _:
            return True


def matches_filters(station: Station, query: StationQuery) -> bool:
    """Return whether a station satisfies every filter the query names."""
    if query.unknown:
        return False
    if query.bands and station.band.value.casefold() not in query.bands:
        return False
    if query.genres and not query.genres & {str(item) for item in station.genres}:
        return False
    if query.regions and not query.regions & {str(item) for item in station.regions}:
        return False
    if query.languages and not query.languages & {
        item.casefold() for item in station.languages
    }:
        return False
    if query.networks and not any(
        wanted in (station.network or "").casefold() for wanted in query.networks
    ):
        return False
    return True


def station_terms(station: Station) -> tuple[str, ...]:
    """Return every field free text is matched against."""
    return (
        station.dial,
        station.name,
        station.short_name or "",
        station.description or "",
        station.band.value,
        station.network or "",
        *(str(item) for item in station.regions),
        *(str(item) for item in station.genres),
        *station.languages,
    )


def rank_station(station: Station, wanted: str) -> int | None:
    """Return how well a station answers a folded query, or None when it does not."""
    frequency = (station.frequency or "").casefold()
    names = tuple(
        value.casefold()
        for value in (station.name, station.short_name or "")
        if value
    )
    metadata = (
        station.network or "",
        *(str(item) for item in station.regions),
        *(str(item) for item in station.genres),
        *station.languages,
    )

    if frequency and frequency == wanted:
        return EXACT_FREQUENCY
    if frequency and frequency.startswith(wanted):
        return FREQUENCY_PREFIX
    if any(name.startswith(wanted) for name in names):
        return NAME_PREFIX
    if wanted in station.dial.casefold():
        return DIAL_MATCH
    if any(wanted in name for name in names):
        return NAME_MATCH
    if any(wanted in item.casefold() for item in metadata if item):
        return METADATA_MATCH
    if wanted in " ".join(station_terms(station)).casefold():
        return OTHER_MATCH
    return None


def search_stations(stations: Sequence[Station], query: str) -> tuple[Station, ...]:
    """Return the stations answering a query, closest match first."""
    parsed = parse_query(query)
    if parsed.is_empty:
        return tuple(stations)

    kept = tuple(item for item in stations if matches_filters(item, parsed))
    if not parsed.text:
        return kept

    ranked: list[tuple[int, Station]] = []
    for station in kept:
        rank = rank_station(station, parsed.text)
        if rank is not None:
            ranked.append((rank, station))

    # sorted is stable, so stations sharing a rank keep their catalog order.
    return tuple(station for _, station in sorted(ranked, key=lambda pair: pair[0]))

"""Read only endpoints exposing the station catalog."""

from __future__ import annotations

from fastapi import APIRouter, Query

from terminal_radio.dependencies import RadioServiceDep
from terminal_radio.enums import Band, Genre, Region
from terminal_radio.schemas import StationListRead, StationRead

router = APIRouter(prefix="/stations", tags=["stations"])


@router.get("", response_model=StationListRead, summary="List stations")
def list_stations(
    service: RadioServiceDep,
    q: str | None = Query(
        default=None,
        description=(
            "Search query. Mixes key:value filters with free text to rank by, "
            "for example: genre:news region:taipei 廣播. The parameters below "
            "are shorthand for the same filters and are folded into it."
        ),
    ),
    band: Band | None = Query(default=None, description="Restrict to FM or AM"),
    genre: list[Genre] | None = Query(
        default=None, description="Restrict to these genres, any of which may match"
    ),
    region: list[Region] | None = Query(
        default=None, description="Restrict to these service areas"
    ),
    language: list[str] | None = Query(
        default=None, description="Restrict to these BCP 47 language tags"
    ),
    network: list[str] | None = Query(
        default=None, description="Restrict to these station families"
    ),
) -> StationListRead:
    """Return the stations answering the query, closest match first."""
    terms = [q] if q else []
    for key, values in (
        ("band", [band] if band else []),
        ("genre", genre or []),
        ("region", region or []),
        ("language", language or []),
        ("network", network or []),
    ):
        terms.extend(f"{key}:{value}" for value in values)

    query = " ".join(terms)
    stations = service.search_stations(query) if query else service.list_stations()
    return StationListRead.from_domain(stations)


@router.get("/{slug}", response_model=StationRead, summary="Get one station")
def get_station(slug: str, service: RadioServiceDep) -> StationRead:
    """Return a single station by slug."""
    return StationRead.from_domain(service.get_station(slug))

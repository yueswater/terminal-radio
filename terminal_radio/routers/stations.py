"""Read only endpoints exposing the station catalog."""

from __future__ import annotations

from fastapi import APIRouter, Query

from terminal_radio.dependencies import RadioServiceDep
from terminal_radio.enums import Band
from terminal_radio.schemas import StationListRead, StationRead

router = APIRouter(prefix="/stations", tags=["stations"])


@router.get("", response_model=StationListRead, summary="List stations")
def list_stations(
    service: RadioServiceDep,
    band: Band | None = Query(default=None, description="Restrict to FM or AM"),
    q: str | None = Query(default=None, description="Search station fields"),
) -> StationListRead:
    """Return every station of the catalog, optionally filtered by band."""
    stations = service.search_stations(q) if q is not None else service.list_stations()
    if band is not None:
        stations = tuple(item for item in stations if item.band is band)
    return StationListRead.from_domain(stations)


@router.get("/{slug}", response_model=StationRead, summary="Get one station")
def get_station(slug: str, service: RadioServiceDep) -> StationRead:
    """Return a single station by slug."""
    return StationRead.from_domain(service.get_station(slug))

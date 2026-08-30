"""Read only endpoints exposing the station catalog."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.dependencies import RadioServiceDep
from app.enums import Band
from app.schemas import StationListRead, StationRead

router = APIRouter(prefix="/stations", tags=["stations"])


@router.get("", response_model=StationListRead, summary="List stations")
def list_stations(
    service: RadioServiceDep,
    band: Band | None = Query(default=None, description="Restrict to FM or AM"),
) -> StationListRead:
    """Return every station of the catalog, optionally filtered by band."""
    return StationListRead.from_domain(service.list_stations(band))


@router.get("/{slug}", response_model=StationRead, summary="Get one station")
def get_station(slug: str, service: RadioServiceDep) -> StationRead:
    """Return a single station by slug."""
    return StationRead.from_domain(service.get_station(slug))

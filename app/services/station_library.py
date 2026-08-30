"""Merged built-in and user-defined station library."""

from __future__ import annotations

from uuid import uuid4

from pydantic import ValidationError

from app.core.exceptions import CatalogError
from app.enums import Band
from app.models import Station
from app.services.catalog import StationCatalog
from app.services.custom_stations import CustomStationStore


class StationLibrary:
    """Own an immutable built-in catalog and a replaceable custom collection."""

    def __init__(
        self,
        built_in: StationCatalog,
        store: CustomStationStore,
    ) -> None:
        self._built_in = built_in
        self._store = store
        self._custom = store.load()
        self._catalog = self._merge(self._custom)

    @property
    def catalog(self) -> StationCatalog:
        return self._catalog

    @property
    def custom_stations(self) -> tuple[Station, ...]:
        return self._custom

    def search(self, query: str) -> tuple[Station, ...]:
        """Search all display fields while preserving catalog order."""
        wanted = query.strip().casefold()
        if not wanted:
            return self._catalog.all()
        return tuple(
            item
            for item in self._catalog.all()
            if wanted
            in " ".join(
                (
                    item.dial,
                    item.name,
                    item.short_name or "",
                    item.description or "",
                    item.band.value,
                )
            ).casefold()
        )

    def add_custom(
        self,
        *,
        name: str,
        band: Band,
        url: str,
        frequency: str | None = None,
        description: str | None = None,
    ) -> Station:
        """Create, persist, and return a custom station."""
        known = {item.slug for item in self._catalog.all()}
        while True:
            slug = f"custom-{uuid4().hex[:12]}"
            if slug not in known:
                break
        item = self._build_station(
            slug,
            name=name,
            band=band,
            url=url,
            frequency=frequency,
            description=description,
        )
        self._replace((*self._custom, item))
        return item

    def update_custom(
        self,
        slug: str,
        *,
        name: str,
        band: Band,
        url: str,
        frequency: str | None = None,
        description: str | None = None,
    ) -> Station:
        """Replace a custom station while retaining its stable slug."""
        indexes = {item.slug: index for index, item in enumerate(self._custom)}
        if slug not in indexes:
            raise CatalogError("Only custom stations can be edited")
        item = self._build_station(
            slug,
            name=name,
            band=band,
            url=url,
            frequency=frequency,
            description=description,
        )
        changed = list(self._custom)
        changed[indexes[slug]] = item
        self._replace(tuple(changed))
        return item

    def delete_custom(self, slug: str) -> Station:
        """Delete and return one custom station."""
        selected = next((item for item in self._custom if item.slug == slug), None)
        if selected is None:
            raise CatalogError("Only custom stations can be deleted")
        self._replace(tuple(item for item in self._custom if item.slug != slug))
        return selected

    def replace_custom(self, stations: tuple[Station, ...]) -> None:
        """Replace every custom station after validating the complete collection."""
        self._replace(stations)

    def _replace(self, stations: tuple[Station, ...]) -> None:
        catalog = self._merge(stations)
        self._store.save(stations)
        self._custom = stations
        self._catalog = catalog

    def _merge(self, custom: tuple[Station, ...]) -> StationCatalog:
        try:
            return StationCatalog([*self._built_in.all(), *custom])
        except CatalogError as error:
            raise CatalogError("Custom station slug conflicts with the catalog") from error

    @staticmethod
    def _build_station(
        slug: str,
        *,
        name: str,
        band: Band,
        url: str,
        frequency: str | None,
        description: str | None,
    ) -> Station:
        values = {
            "slug": slug,
            "name": name.strip(),
            "band": band,
            "url": url.strip(),
            "frequency": frequency.strip() if frequency and frequency.strip() else None,
            "description": (
                description.strip() if description and description.strip() else None
            ),
        }
        try:
            return Station.model_validate(values)
        except ValidationError as error:
            raise CatalogError("Invalid custom station") from error

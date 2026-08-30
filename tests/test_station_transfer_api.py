"""Station transfer compatibility and read-only API search tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from terminal_radio.core.config import Settings
from terminal_radio.core.exceptions import RadioError
from terminal_radio.enums import Band
from terminal_radio.models import Station
from terminal_radio.routers.stations import list_stations
from terminal_radio.services import (
    CustomStationStore,
    HistoryLog,
    PersistedState,
    RadioService,
    StateStore,
    StationCatalog,
    StationLibrary,
    read_export,
    read_preferences,
    write_export,
)


class MemoryPlayer:
    def __init__(self) -> None:
        self.running = False
        self.paused = False
        self._volume = 100
        self._muted = False

    is_running = property(lambda self: self.running)
    is_paused = property(lambda self: self.running and self.paused)
    volume = property(lambda self: self._volume)
    is_muted = property(lambda self: self._muted)

    def start(self, _url: str) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def set_paused(self, paused: bool) -> None:
        self.paused = paused

    def set_volume(self, volume: int) -> None:
        self._volume = volume

    def set_muted(self, muted: bool) -> None:
        self._muted = muted

    def program(self) -> str | None:
        return None

    def device(self) -> str | None:
        return None


def make_station(slug: str, name: str, band: Band = Band.FM) -> Station:
    return Station(
        slug=slug,
        name=name,
        band=band,
        frequency="99.9" if band is Band.FM else "1000",
        url=f"https://example.com/{slug}",
        description=f"{name} description",
    )


class StationTransferTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.settings = Settings(data_dir=self.root / "data")
        self.custom = make_station("custom-exported", "匯出電台", Band.AM)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_export_and_import_include_custom_stations(self) -> None:
        target = write_export(
            self.root,
            self.settings,
            PersistedState(favorites=[self.custom.slug]),
            (self.custom,),
        )

        imported = read_export(target)

        self.assertEqual(imported.preferences.favorites, [self.custom.slug])
        self.assertEqual(imported.custom_stations, (self.custom,))
        self.assertEqual(read_preferences(target), imported.preferences)

    def test_legacy_export_without_custom_stations_is_compatible(self) -> None:
        path = self.root / "legacy.radio.config"
        path.write_text(
            json.dumps({"preferences": {"volume": 55}}),
            encoding="utf-8",
        )
        imported = read_export(path)
        self.assertEqual(imported.preferences.volume, 55)
        self.assertIsNone(imported.custom_stations)

    def test_duplicate_custom_slugs_reject_the_entire_import(self) -> None:
        path = self.root / "bad.radio.config"
        payload = self.custom.model_dump(mode="json")
        path.write_text(
            json.dumps(
                {
                    "preferences": {"volume": 55},
                    "custom_stations": [payload, payload],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(RadioError):
            read_export(path)

    def test_catalog_collision_does_not_apply_imported_preferences(self) -> None:
        built_in = make_station("builtin", "Built in")
        store = CustomStationStore(self.root / "custom.toml")
        library = StationLibrary(StationCatalog([built_in]), store)
        state = StateStore(self.root / "state.json")
        state.save(PersistedState(volume=100))
        service = RadioService(
            library.catalog,
            MemoryPlayer(),
            HistoryLog(self.root / "history.jsonl"),
            state,
            station_library=library,
        )

        with self.assertRaises(RadioError):
            service.apply_import(PersistedState(volume=55), (built_in,))

        self.assertEqual(service.preferences().volume, 100)
        self.assertEqual(service.custom_stations(), ())


class StationApiSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.built_in = make_station("builtin-news", "News FM")
        self.custom = make_station("custom-talk", "Talk AM", Band.AM)
        store = CustomStationStore(root / "custom.toml")
        store.save((self.custom,))
        library = StationLibrary(StationCatalog([self.built_in]), store)
        self.service = RadioService(
            library.catalog,
            MemoryPlayer(),
            HistoryLog(root / "history.jsonl"),
            StateStore(root / "state.json"),
            autoplay_last_station=False,
            station_library=library,
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_api_returns_merged_catalog_and_optional_query(self) -> None:
        merged = list_stations(service=self.service, band=None, q=None)
        searched = list_stations(service=self.service, band=None, q="talk")
        filtered = list_stations(service=self.service, band=Band.FM, q="news")

        self.assertEqual([item.slug for item in merged.items], ["builtin-news", "custom-talk"])
        self.assertEqual([item.slug for item in searched.items], ["custom-talk"])
        self.assertEqual([item.slug for item in filtered.items], ["builtin-news"])


if __name__ == "__main__":
    unittest.main()

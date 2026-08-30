"""Custom station, search, and health-check behavior."""

from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app.core.config import Settings, get_settings
from app.core.exceptions import CatalogError, StationNotFoundError
from app.enums import Band, StationHealth
from app.models import Station
from app.services import HistoryLog, RadioService, StateStore, StationCatalog, build_radio_service
from app.services.custom_stations import CustomStationStore
from app.services.station_library import StationLibrary
from app.services.station_health import StationHealthService


def station(
    slug: str = "custom-first",
    *,
    name: str = "第一電台",
    band: Band = Band.FM,
    frequency: str | None = "99.9",
    url: str = "https://example.com/live",
    description: str | None = "音樂與新聞",
) -> Station:
    return Station(
        slug=slug,
        name=name,
        band=band,
        frequency=frequency,
        url=url,
        description=description,
    )


class CustomStationStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "custom-stations.toml"
        self.store = CustomStationStore(self.path)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_missing_file_is_an_empty_collection(self) -> None:
        self.assertEqual(self.store.load(), ())

    def test_unicode_round_trip_preserves_order_and_optional_values(self) -> None:
        expected = (
            station(),
            station(
                "custom-second",
                name="Second AM",
                band=Band.AM,
                frequency=None,
                description=None,
                url="http://example.org/am",
            ),
        )
        self.store.save(expected)
        self.assertEqual(self.store.load(), expected)
        self.assertIn("第一電台", self.path.read_text(encoding="utf-8"))

    def test_malformed_toml_and_duplicate_slugs_are_rejected(self) -> None:
        self.path.write_text("[[stations]\n", encoding="utf-8")
        with self.assertRaises(CatalogError):
            self.store.load()

        self.path.write_text(
            """
[[stations]]
slug = "duplicate"
name = "One"
band = "FM"
url = "https://example.com/one"

[[stations]]
slug = "duplicate"
name = "Two"
band = "AM"
url = "https://example.com/two"
""".strip(),
            encoding="utf-8",
        )
        with self.assertRaises(CatalogError):
            self.store.load()

    def test_failed_atomic_replace_keeps_previous_file(self) -> None:
        self.store.save((station(),))
        before = self.path.read_bytes()

        with patch("app.services.custom_stations.os.replace", side_effect=OSError):
            with self.assertRaises(CatalogError):
                self.store.save((station("custom-new", name="New"),))

        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(
            [path.name for path in self.path.parent.iterdir()],
            [self.path.name],
        )


class StationLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "custom-stations.toml"
        self.store = CustomStationStore(self.path)
        self.built_in = station(
            "builtin-news",
            name="News 98",
            band=Band.FM,
            frequency="98.1",
            description="Breaking News",
            url="https://example.com/news",
        )
        self.library = StationLibrary(StationCatalog([self.built_in]), self.store)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_crud_preserves_built_in_order_and_custom_slug(self) -> None:
        added = self.library.add_custom(
            name="臺灣之聲",
            band=Band.AM,
            frequency="1000",
            url="https://example.com/voice",
            description="談話節目",
        )
        self.assertRegex(added.slug, r"^custom-[0-9a-f]{12}$")
        self.assertEqual(
            [item.slug for item in self.library.catalog.all()],
            ["builtin-news", added.slug],
        )

        changed = self.library.update_custom(
            added.slug,
            name="臺灣新聲",
            band=Band.FM,
            frequency="101.1",
            url="https://example.com/new-voice",
            description=None,
        )
        self.assertEqual(changed.slug, added.slug)
        self.assertEqual(self.store.load(), (changed,))

        removed = self.library.delete_custom(added.slug)
        self.assertEqual(removed.slug, added.slug)
        self.assertEqual(self.library.catalog.all(), (self.built_in,))

    def test_search_matches_every_field_with_casefolding(self) -> None:
        custom = self.library.add_custom(
            name="ÉCHO Radio",
            band=Band.AM,
            frequency="1000",
            url="https://example.com/echo",
            description="夜間 Music",
        )
        for query in ("écho", "AM 1000", "music", "am", "  ÉCHO  "):
            with self.subTest(query=query):
                self.assertEqual(self.library.search(query), (custom,))
        self.assertEqual(
            self.library.search(""),
            (self.built_in, custom),
        )

    def test_collisions_built_in_edits_and_invalid_urls_are_rejected(self) -> None:
        self.store.save((station("builtin-news"),))
        with self.assertRaises(CatalogError):
            StationLibrary(StationCatalog([self.built_in]), self.store)

        clean = StationLibrary(
            StationCatalog([self.built_in]),
            CustomStationStore(Path(self.directory.name) / "clean.toml"),
        )
        with self.assertRaises(CatalogError):
            clean.update_custom(
                "builtin-news",
                name="No",
                band=Band.FM,
                frequency=None,
                url="https://example.com/no",
                description=None,
            )
        with self.assertRaises(CatalogError):
            clean.add_custom(
                name="Bad",
                band=Band.FM,
                frequency=None,
                url="file:///tmp/audio",
                description=None,
            )


class MemoryPlayer:
    def __init__(self) -> None:
        self.running = False
        self.paused = False
        self._volume = 100
        self._muted = False

    @property
    def is_running(self) -> bool:
        return self.running

    @property
    def is_paused(self) -> bool:
        return self.running and self.paused

    def start(self, _url: str) -> None:
        self.running = True
        self.paused = False

    def stop(self) -> None:
        self.running = False
        self.paused = False

    def set_paused(self, paused: bool) -> None:
        self.paused = paused

    @property
    def volume(self) -> int:
        return self._volume

    def set_volume(self, volume: int) -> None:
        self._volume = volume

    @property
    def is_muted(self) -> bool:
        return self._muted

    def set_muted(self, muted: bool) -> None:
        self._muted = muted

    def program(self) -> str | None:
        return None

    def device(self) -> str | None:
        return None


class RadioStationLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        built_in = station("builtin")
        self.library = StationLibrary(
            StationCatalog([built_in]),
            CustomStationStore(root / "custom-stations.toml"),
        )
        self.player = MemoryPlayer()
        self.state = StateStore(root / "state.json")
        self.service = RadioService(
            self.library.catalog,
            self.player,
            HistoryLog(root / "history.jsonl"),
            self.state,
            autoplay_last_station=False,
            station_library=self.library,
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_service_crud_search_and_delete_cleanup_are_immediate(self) -> None:
        added = self.service.add_custom_station(
            name="Talk AM",
            band=Band.AM,
            frequency="1000",
            url="https://example.com/talk",
            description="Late talk",
        )
        self.assertEqual(self.service.search_stations("late"), (added,))
        self.service.toggle_favorite(added.slug)
        self.service.play(added.slug)

        self.service.delete_custom_station(added.slug)

        self.assertFalse(self.player.running)
        self.assertEqual(self.service.favorites(), ())
        self.assertIsNone(self.service.preferences().last_station_slug)
        with self.assertRaises(StationNotFoundError):
            self.service.get_station(added.slug)

    def test_default_builder_loads_the_custom_station_file(self) -> None:
        settings = Settings(
            data_dir=Path(self.directory.name) / "app-data",
            autoplay_last_station=False,
        )
        CustomStationStore(settings.custom_stations_file).save(
            (station("custom-loaded", name="Loaded"),)
        )

        service = build_radio_service(settings)

        self.assertEqual(service.get_station("custom-loaded").name, "Loaded")


class FakeResponse:
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int) -> bytes:
        if size != 1:
            raise AssertionError("health probe must read only one byte")
        return b"x"


class FakeOpener:
    def __init__(
        self,
        clock: list[float],
        *,
        elapsed: float = 0.1,
        error: Exception | None = None,
    ) -> None:
        self.clock = clock
        self.elapsed = elapsed
        self.error = error
        self.calls = 0
        self.requests: list[object] = []

    def __call__(self, request: object, *, timeout: float) -> FakeResponse:
        self.calls += 1
        self.requests.append(request)
        if timeout != 4:
            raise AssertionError("health timeout changed")
        self.clock[0] += self.elapsed
        if self.error is not None:
            raise self.error
        return FakeResponse()


class StationHealthServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = [100.0]
        self.station = station()

    def test_online_slow_and_offline_results_use_ranged_get(self) -> None:
        for elapsed, error, expected in (
            (0.2, None, StationHealth.ONLINE),
            (1.5, None, StationHealth.SLOW),
            (0.1, TimeoutError(), StationHealth.OFFLINE),
        ):
            with self.subTest(expected=expected):
                opener = FakeOpener(self.clock, elapsed=elapsed, error=error)
                service = StationHealthService(opener=opener, clock=lambda: self.clock[0])
                result = service.check(self.station)
                self.assertEqual(result.health, expected)
                request = opener.requests[0]
                self.assertEqual(request.get_header("Range"), "bytes=0-0")

    def test_cache_lives_five_minutes_and_force_bypasses_it(self) -> None:
        opener = FakeOpener(self.clock)
        service = StationHealthService(opener=opener, clock=lambda: self.clock[0])

        first = service.check(self.station)
        self.clock[0] += 299
        self.assertIs(service.check(self.station), first)
        self.assertEqual(opener.calls, 1)

        service.check(self.station, force=True)
        self.assertEqual(opener.calls, 2)
        self.clock[0] += 300
        service.check(self.station)
        self.assertEqual(opener.calls, 3)

    def test_batch_checks_use_no_more_than_four_workers(self) -> None:
        opener = FakeOpener(self.clock, elapsed=0)
        service = StationHealthService(opener=opener, clock=lambda: self.clock[0])
        stations = tuple(
            station(f"custom-{index}", name=f"Station {index}")
            for index in range(8)
        )

        with patch(
            "app.services.station_health.ThreadPoolExecutor",
            wraps=ThreadPoolExecutor,
        ) as executor:
            results = service.check_many(stations, force=True)

        executor.assert_called_once_with(max_workers=4)
        self.assertEqual(len(results), 8)

    def test_auto_health_defaults_on_and_has_environment_override(self) -> None:
        self.assertTrue(Settings().auto_health_check)
        with patch.dict("os.environ", {"RADIO_AUTO_HEALTH_CHECK": "false"}):
            get_settings.cache_clear()
            self.assertFalse(get_settings().auto_health_check)
        get_settings.cache_clear()

    def test_radio_service_persists_toggle_and_exposes_health_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            opener = FakeOpener(self.clock)
            health = StationHealthService(
                opener=opener, clock=lambda: self.clock[0]
            )
            state = StateStore(root / "state.json")
            service = RadioService(
                StationCatalog([self.station]),
                MemoryPlayer(),
                HistoryLog(root / "history.jsonl"),
                state,
                auto_health_check=True,
                station_health=health,
            )

            self.assertTrue(service.auto_health_check)
            self.assertFalse(service.set_auto_health_check(False))
            self.assertFalse(state.load().auto_health_check)
            result = service.check_station_health((self.station,), force=True)
            self.assertEqual(result[0].health, StationHealth.ONLINE)


if __name__ == "__main__":
    unittest.main()

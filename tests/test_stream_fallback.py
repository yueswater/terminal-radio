"""Backup streams: the model, the rotation policy, and the health probe."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from terminal_radio.core.exceptions import PlayerError
from terminal_radio.enums import Band, PlaybackState, StationHealth
from terminal_radio.models import Station
from terminal_radio.services import HistoryLog, RadioService, StateStore, StationCatalog
from terminal_radio.services.reconnect import ReconnectSchedule
from terminal_radio.services.station_health import StationHealthService

PRIMARY = "https://primary.example/live"
BACKUP_ONE = "https://backup1.example/live"
BACKUP_TWO = "https://backup2.example/live"


def station(slug: str = "alpha", fallbacks: tuple[str, ...] = ()) -> Station:
    return Station(
        slug=slug,
        name="Alpha",
        band=Band.FM,
        frequency="99.9",
        url=PRIMARY,
        fallback_urls=fallbacks,
    )


class StreamUrlTests(unittest.TestCase):
    def test_a_station_without_backups_offers_only_its_own_address(self) -> None:
        self.assertEqual(station().stream_urls, (PRIMARY,))

    def test_the_primary_always_comes_first(self) -> None:
        item = station(fallbacks=(BACKUP_ONE, BACKUP_TWO))

        self.assertEqual(item.stream_urls, (PRIMARY, BACKUP_ONE, BACKUP_TWO))

    def test_a_backup_repeating_the_primary_is_not_tried_twice(self) -> None:
        item = station(fallbacks=(BACKUP_ONE, PRIMARY, BACKUP_ONE))

        self.assertEqual(item.stream_urls, (PRIMARY, BACKUP_ONE))

    def test_a_backup_is_held_to_the_same_rule_as_the_primary(self) -> None:
        with self.assertRaises(ValidationError):
            station(fallbacks=("ftp://backup.example/live",))


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class RecordingPlayer:
    """A player that reports the stream dead until it is told otherwise."""

    def __init__(self) -> None:
        self.started: list[str] = []
        self.alive = False
        self.raises = False

    @property
    def is_running(self) -> bool:
        return self.alive

    @property
    def is_paused(self) -> bool:
        return False

    def start(self, url: str) -> None:
        self.started.append(url)
        if self.raises:
            raise PlayerError("cannot start player")
        self.alive = True

    def stop(self) -> None:
        self.alive = False

    def set_paused(self, paused: bool) -> None:
        pass

    @property
    def volume(self) -> int:
        return 100

    def set_volume(self, volume: int) -> None:
        pass

    @property
    def is_muted(self) -> bool:
        return False

    def set_muted(self, muted: bool) -> None:
        pass

    def program(self) -> str | None:
        return None

    def device(self) -> str | None:
        return None

    def fade_out(self, seconds: float) -> None:
        self.faded = seconds

    def drain_program_changes(self) -> tuple[str, ...]:
        announced, self.announced = tuple(getattr(self, "announced", ())), []
        return announced


class FallbackRotationTests(unittest.TestCase):
    """Each retry moves to the next address; the retry schedule is untouched."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.clock = Clock()
        self.player = RecordingPlayer()
        self.station = station(fallbacks=(BACKUP_ONE, BACKUP_TWO))
        self.service = RadioService(
            catalog=StationCatalog([self.station]),
            player=self.player,
            history=HistoryLog(root / "history.jsonl"),
            state=StateStore(root / "state.json"),
            autoplay_last_station=False,
            clock=self.clock,
            reconnect=ReconnectSchedule(self.clock),
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def _die_and_retry(self, delay: float) -> None:
        """Report the stream gone, then let the schedule come due."""
        self.player.alive = False
        self.service.status()
        self.clock.advance(delay)
        self.service.status()

    def test_playing_a_station_always_starts_at_the_primary(self) -> None:
        self.service.play("alpha")

        self.assertEqual(self.player.started, [PRIMARY])
        self.assertEqual(self.service.status().stream_index, 0)

    def test_each_retry_moves_to_the_next_address(self) -> None:
        self.service.play("alpha")

        self._die_and_retry(1.0)
        self._die_and_retry(2.0)
        self._die_and_retry(4.0)

        self.assertEqual(
            self.player.started, [PRIMARY, BACKUP_ONE, BACKUP_TWO, PRIMARY]
        )

    def test_the_retry_schedule_is_unchanged_by_the_rotation(self) -> None:
        """A backup is tried when the next delay elapses, not sooner."""
        self.service.play("alpha")
        self.player.alive = False
        self.service.status()

        self.clock.advance(0.9)
        self.service.status()
        self.assertEqual(self.player.started, [PRIMARY])

        self.clock.advance(0.1)
        self.service.status()
        self.assertEqual(self.player.started, [PRIMARY, BACKUP_ONE])

    def test_a_working_backup_is_left_alone(self) -> None:
        """Nothing switches back to the primary while the sound is playing."""
        self.service.play("alpha")
        self._die_and_retry(1.0)

        self.clock.advance(60)
        status = self.service.status()

        self.assertEqual(self.player.started, [PRIMARY, BACKUP_ONE])
        self.assertEqual(status.state, PlaybackState.PLAYING)
        self.assertEqual(status.stream_index, 1)
        self.assertTrue(status.using_fallback)

    def test_asking_for_the_station_again_returns_to_the_primary(self) -> None:
        """A deliberate request is the one moment the primary is retried."""
        self.service.play("alpha")
        self._die_and_retry(1.0)
        self.assertEqual(self.service.status().stream_index, 1)

        self.service.play("alpha")

        self.assertEqual(self.player.started[-1], PRIMARY)
        self.assertEqual(self.service.status().stream_index, 0)

    def test_the_status_counts_the_addresses_the_station_offers(self) -> None:
        self.service.play("alpha")
        status = self.service.status()

        self.assertEqual(status.stream_count, 3)
        self.assertFalse(status.using_fallback)

    def test_a_backend_that_will_not_start_never_escapes_the_status_call(
        self,
    ) -> None:
        """status() is polled by the interface and must not raise into it."""
        self.service.play("alpha")
        self.player.raises = True

        self._die_and_retry(1.0)

        self.assertEqual(self.service.status().state, PlaybackState.RECONNECTING)

    def test_stopping_forgets_which_address_was_in_use(self) -> None:
        self.service.play("alpha")
        self._die_and_retry(1.0)

        self.service.stop()

        self.assertEqual(self.service.status().stream_index, 0)


class FakeResponse:
    def __init__(self) -> None:
        self.read_calls = 0

    def read(self, size: int) -> bytes:
        self.read_calls += 1
        return b"\x00"

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None


class HealthAcrossEndpointsTests(unittest.TestCase):
    def _service(self, alive: set[str]) -> tuple[StationHealthService, list[str]]:
        tried: list[str] = []

        def opener(request: object, *, timeout: float) -> FakeResponse:
            url = request.full_url  # type: ignore[attr-defined]
            tried.append(url)
            if url not in alive:
                raise OSError("refused")
            return FakeResponse()

        return StationHealthService(opener=opener, clock=lambda: 0.0), tried

    def test_a_healthy_station_still_costs_one_request(self) -> None:
        service, tried = self._service({PRIMARY})

        result = service.check(station(fallbacks=(BACKUP_ONE, BACKUP_TWO)))

        self.assertEqual(result.health, StationHealth.ONLINE)
        self.assertEqual(result.endpoint_index, 0)
        self.assertEqual(tried, [PRIMARY])

    def test_a_backup_keeps_the_station_online(self) -> None:
        service, tried = self._service({BACKUP_TWO})

        result = service.check(station(fallbacks=(BACKUP_ONE, BACKUP_TWO)))

        self.assertEqual(result.health, StationHealth.ONLINE)
        self.assertEqual(result.endpoint_index, 2)
        self.assertEqual(tried, [PRIMARY, BACKUP_ONE, BACKUP_TWO])

    def test_a_station_is_offline_only_when_every_address_is(self) -> None:
        service, tried = self._service(set())

        result = service.check(station(fallbacks=(BACKUP_ONE,)))

        self.assertEqual(result.health, StationHealth.OFFLINE)
        self.assertIsNone(result.endpoint_index)
        self.assertEqual(tried, [PRIMARY, BACKUP_ONE])

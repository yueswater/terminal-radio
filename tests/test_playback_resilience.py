"""Playback resilience contracts and deterministic helper tests."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from app.core.config import Settings, get_settings
from app.core.exceptions import PlayerError
from app.enums import Band, HistoryEventType, PlaybackState
from app.models import HistoryEvent, PlayerStatus, Station
from app.services import HistoryLog, PersistedState, RadioService, StateStore, StationCatalog
from app.services.reconnect import ReconnectSchedule
from app.services.sleep_timer import SleepTimer


class PlaybackModelTests(unittest.TestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    def test_enums_are_owned_by_app_enums(self) -> None:
        self.assertEqual(Band.FM, "FM")
        self.assertEqual(HistoryEventType.PLAY_ENDED, "play_ended")
        self.assertEqual(PlaybackState.RECONNECTING, "reconnecting")
        self.assertEqual(Band.__module__, "app.enums.station")
        self.assertEqual(PlaybackState.__module__, "app.enums.playback")
        self.assertEqual(HistoryEventType.__module__, "app.enums.history")

    def test_reconnect_fields_have_backward_compatible_defaults(self) -> None:
        status = PlayerStatus()
        self.assertEqual(status.reconnect_attempt, 0)
        self.assertIsNone(status.sleep_remaining_seconds)

    def test_auto_reconnect_defaults_on_and_can_be_disabled_by_environment(self) -> None:
        self.assertTrue(Settings().auto_reconnect)
        with patch.dict(os.environ, {"RADIO_AUTO_RECONNECT": "false"}):
            get_settings.cache_clear()
            self.assertFalse(get_settings().auto_reconnect)


class SleepTimerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = 100.0
        self.timer = SleepTimer(lambda: self.now)

    def test_counts_down_and_expires(self) -> None:
        self.timer.set_minutes(15)
        self.now += 899
        self.assertEqual(self.timer.remaining_seconds(), 1)
        self.assertFalse(self.timer.expired())
        self.now += 1
        self.assertTrue(self.timer.expired())

    def test_none_cancels_and_invalid_minutes_are_rejected(self) -> None:
        self.timer.set_minutes(30)
        self.timer.set_minutes(None)
        self.assertIsNone(self.timer.remaining_seconds())
        for value in (0, 1441):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.timer.set_minutes(value)


class ReconnectScheduleTests(unittest.TestCase):
    def test_uses_each_delay_once_then_exhausts(self) -> None:
        now = [10.0]
        schedule = ReconnectSchedule(lambda: now[0])
        schedule.start()

        for expected_attempt, delay in enumerate((1, 2, 4, 8, 15), start=1):
            now[0] += delay
            self.assertTrue(schedule.ready)
            self.assertEqual(schedule.record_attempt(), expected_attempt)
            self.assertEqual(schedule.record_failure(), expected_attempt < 5)

        self.assertFalse(schedule.active)

    def test_success_requires_five_stable_seconds(self) -> None:
        now = [0.0]
        schedule = ReconnectSchedule(lambda: now[0])
        schedule.start()
        now[0] = 1.0
        schedule.record_attempt()
        now[0] = 5.9
        self.assertFalse(schedule.stable)
        now[0] = 6.0
        self.assertTrue(schedule.stable)

    def test_reset_clears_every_phase(self) -> None:
        now = [0.0]
        schedule = ReconnectSchedule(lambda: now[0])
        schedule.start()
        now[0] = 1.0
        schedule.record_attempt()
        schedule.reset()
        self.assertFalse(schedule.active)
        self.assertFalse(schedule.ready)
        self.assertFalse(schedule.stabilizing)
        self.assertEqual(schedule.attempt, 0)


class MutableClock:
    def __init__(self, value: float = 100.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class ControllablePlayer:
    def __init__(self) -> None:
        self.running = False
        self.paused = False
        self.start_calls = 0
        self.fail_starts = 0
        self._volume = 100
        self._muted = False

    @property
    def is_running(self) -> bool:
        return self.running

    @property
    def is_paused(self) -> bool:
        return self.running and self.paused

    def start(self, _url: str) -> None:
        self.start_calls += 1
        if self.fail_starts:
            self.fail_starts -= 1
            raise PlayerError("failed")
        self.running = True
        self.paused = False

    def stop(self) -> None:
        self.running = False
        self.paused = False

    def crash(self) -> None:
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


class RadioServiceResilienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.clock = MutableClock()
        self.player = ControllablePlayer()
        self.history = HistoryLog(root / "history.jsonl")
        self.state = StateStore(root / "state.json")
        self.station = Station(
            slug="station",
            name="Station",
            short_name="Short Station",
            band=Band.FM,
            frequency="99.9",
            url="https://example.com/radio",
        )
        self.other = Station(
            slug="other",
            name="Other",
            band=Band.AM,
            frequency="1000",
            url="https://example.com/other",
        )
        self.service = RadioService(
            StationCatalog([self.station, self.other]),
            self.player,
            self.history,
            self.state,
            autoplay_last_station=False,
            auto_reconnect=True,
            reconnect=ReconnectSchedule(self.clock),
            sleep_timer=SleepTimer(self.clock),
            clock=self.clock,
        )

    def test_listening_statistics_use_the_catalog_short_name(self) -> None:
        """Existing history adopts the current alias without rewriting the log."""
        self.history.append(
            HistoryEvent(
                at=datetime(2026, 8, 30, tzinfo=UTC),
                type=HistoryEventType.PLAY_ENDED,
                station_slug="station",
                station_name="An Older Long Station Name",
                station_dial="FM 99.9",
                duration_seconds=60,
            )
        )

        report = self.service.listening_statistics()

        self.assertEqual(report.top_stations[0].station_name, "Short Station")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_unexpected_exit_retries_and_recovers_without_a_second_play(self) -> None:
        self.service.play("station")
        self.clock.advance(10)
        self.player.crash()
        self.assertEqual(self.service.status().state, PlaybackState.RECONNECTING)

        self.clock.advance(1)
        self.assertEqual(self.service.status().reconnect_attempt, 1)
        self.clock.advance(5)
        self.assertEqual(self.service.status().state, PlaybackState.PLAYING)
        self.service.stop()

        self.assertEqual(self.service.summaries()[0].play_count, 1)
        ended = [
            event
            for event in self.service.history()
            if event.type is HistoryEventType.PLAY_ENDED
        ]
        self.assertEqual(len(ended), 1)
        self.assertEqual(ended[0].interrupted_seconds, 1)

    def test_expired_sleep_timer_stops_and_cancels_reconnect(self) -> None:
        self.service.play("station")
        self.service.set_sleep_timer(15)
        self.clock.advance(900)

        status = self.service.status()

        self.assertEqual(status.state, PlaybackState.STOPPED)
        self.assertIsNone(status.sleep_remaining_seconds)
        self.assertFalse(self.player.running)

    def test_interruption_is_not_listened_or_paused_time(self) -> None:
        event = HistoryEvent(
            at=datetime(2026, 8, 30, tzinfo=UTC),
            type=HistoryEventType.PLAY_ENDED,
            duration_seconds=100,
            paused_seconds=10,
            interrupted_seconds=20,
        )
        self.assertEqual(event.listened_seconds, 70)

    def test_legacy_history_defaults_interruption_to_zero(self) -> None:
        event = HistoryEvent.model_validate(
            {
                "at": "2026-08-30T00:00:00Z",
                "type": "play_ended",
                "duration_seconds": 12,
                "paused_seconds": 2,
            }
        )
        self.assertEqual(event.interrupted_seconds, 0)
        self.assertEqual(event.listened_seconds, 10)

    def test_disabled_reconnect_finishes_immediately(self) -> None:
        self.service.set_auto_reconnect(False)
        self.service.play("station")
        self.clock.advance(4)
        self.player.crash()

        self.assertEqual(self.service.status().state, PlaybackState.STOPPED)
        self.assertEqual(self.player.start_calls, 1)

    def test_manual_stop_cancels_retry_and_sleep(self) -> None:
        self.service.play("station")
        self.service.set_sleep_timer(15)
        self.player.crash()
        self.service.status()

        status = self.service.stop()
        self.clock.advance(60)

        self.assertEqual(status.state, PlaybackState.STOPPED)
        self.assertIsNone(self.service.sleep_remaining_seconds())
        self.assertEqual(self.player.start_calls, 1)

    def test_switching_station_preserves_sleep_deadline(self) -> None:
        self.service.play("station")
        self.service.set_sleep_timer(15)
        self.clock.advance(60)
        self.service.play("other")
        self.assertEqual(self.service.sleep_remaining_seconds(), 840)

    def test_synchronous_player_error_is_retried_without_escaping(self) -> None:
        self.service.play("station")
        self.player.crash()
        self.service.status()
        self.player.fail_starts = 1
        self.clock.advance(1)

        status = self.service.status()

        self.assertEqual(status.state, PlaybackState.RECONNECTING)
        self.assertEqual(status.reconnect_attempt, 1)
        self.clock.advance(2)
        self.assertEqual(self.service.status().reconnect_attempt, 2)

    def test_five_failed_attempts_exhaust_reconnect(self) -> None:
        self.service.play("station")
        self.player.crash()
        self.service.status()
        self.player.fail_starts = 5

        for delay in (1, 2, 4, 8, 15):
            self.clock.advance(delay)
            status = self.service.status()

        self.assertEqual(status.state, PlaybackState.STOPPED)
        self.assertEqual(self.player.start_calls, 6)
        self.assertEqual(self.service.summaries()[0].play_count, 1)

    def test_persisted_reconnect_choice_overrides_default(self) -> None:
        self.state.save(PersistedState(auto_reconnect=False))
        service = RadioService(
            StationCatalog([self.station]),
            self.player,
            self.history,
            self.state,
            auto_reconnect=True,
            reconnect=ReconnectSchedule(self.clock),
            sleep_timer=SleepTimer(self.clock),
            clock=self.clock,
        )
        self.assertFalse(service.auto_reconnect)


if __name__ == "__main__":
    unittest.main()

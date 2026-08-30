"""Playback resilience contracts and deterministic helper tests."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.core.config import Settings, get_settings
from app.enums import Band, HistoryEventType, PlaybackState
from app.models import PlayerStatus
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


if __name__ == "__main__":
    unittest.main()

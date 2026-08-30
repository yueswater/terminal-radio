"""Playback resilience contracts and deterministic helper tests."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.core.config import Settings, get_settings
from app.enums import Band, HistoryEventType, PlaybackState
from app.models import PlayerStatus


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


if __name__ == "__main__":
    unittest.main()

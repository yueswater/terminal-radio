"""Regression tests for stateful terminal UI widgets."""

from __future__ import annotations

import unittest

from textual.app import App, ComposeResult
from textual.widgets import Static

from app.core.i18n import Locale, Translator
from app.enums import Band, PlaybackState
from app.models import PlayerStatus, Station
from app.services import StationSummary
from app.tui.widgets import HistoryTable, NowPlayingBar, SettingsTable


TRANSLATOR = Translator(Locale(code="en", name="English"))
PLAYER_TRANSLATOR = Translator(
    Locale(
        code="en",
        name="English",
        messages={
            "player.reconnecting": "RECONNECTING",
            "player.no_station": "No station",
            "player.volume": "VOL",
            "player.sleep": "Sleep {duration}",
        },
    )
)


class SettingsApp(App[None]):
    """Minimal mounted context for exercising the real settings table."""

    def compose(self) -> ComposeResult:
        yield SettingsTable(TRANSLATOR)


class HistoryApp(App[None]):
    """Minimal mounted context for the real listening history table."""

    def compose(self) -> ComposeResult:
        yield HistoryTable(TRANSLATOR)


class NowPlayingApp(App[None]):
    """Minimal mounted context for the bottom playback controller."""

    def compose(self) -> ComposeResult:
        yield NowPlayingBar(PLAYER_TRANSLATOR)


class HistoryTableTests(unittest.IsolatedAsyncioTestCase):
    async def test_times_always_include_hours(self) -> None:
        """History durations must use HH:MM:SS even below one hour."""
        summary = StationSummary(
            station_slug="example",
            station_name="Example FM",
            listened_seconds=255,
            paused_seconds=2,
        )

        async with HistoryApp().run_test(size=(100, 20)) as pilot:
            table = pilot.app.query_one(HistoryTable)
            table.show((summary,))
            await pilot.pause()

            row = table.get_row("example")
            self.assertEqual(row[3], "00:04:15")
            self.assertEqual(row[4], "00:00:02")


class SettingsTableTests(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_keeps_the_selected_setting(self) -> None:
        """Changing one value must not send the cursor back to the first row."""
        rows = (
            ("autoplay", "Autoplay", "On", ""),
            ("language", "Language", "English", ""),
            ("theme", "Theme", "green", ""),
            ("volume", "Volume", "50%", ""),
        )

        async with SettingsApp().run_test(size=(100, 20)) as pilot:
            table = pilot.app.query_one(SettingsTable)
            table.show(rows)
            table.move_cursor(row=2)
            await pilot.pause()
            self.assertEqual(table.selected_key, "theme")

            changed_rows = rows[:2] + (("theme", "Theme", "nord", ""),) + rows[3:]
            table.show(changed_rows)
            await pilot.pause()

            self.assertEqual(table.selected_key, "theme")


class NowPlayingBarTests(unittest.IsolatedAsyncioTestCase):
    async def test_reconnect_and_sleep_are_visible(self) -> None:
        """The controller renders reconnect state and the active deadline."""
        station = Station(
            slug="example",
            name="Example",
            band=Band.FM,
            frequency="99.9",
            url="https://example.com",
        )
        status = PlayerStatus(
            state=PlaybackState.RECONNECTING,
            station=station,
            reconnect_attempt=2,
            sleep_remaining_seconds=90,
        )

        async with NowPlayingApp().run_test(size=(100, 8)) as pilot:
            bar = pilot.app.query_one(NowPlayingBar)
            bar.show(status)
            await pilot.pause()

            self.assertIn(
                "RECONNECTING",
                str(pilot.app.query_one("#np-state", Static).content),
            )
            self.assertEqual(
                str(pilot.app.query_one("#np-sleep", Static).content),
                "Sleep 01:30",
            )

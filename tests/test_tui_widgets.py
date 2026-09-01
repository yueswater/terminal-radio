"""Regression tests for stateful terminal UI widgets."""

from __future__ import annotations

import unittest

from textual.app import App, ComposeResult
from textual.widgets import Static

from terminal_radio.core.i18n import Locale, Translator
from terminal_radio.enums import Band, PlaybackState, StationHealth
from terminal_radio.models import PlayerStatus, Station
from terminal_radio.services import StationSummary
from rich.cells import cell_len

from terminal_radio.constants.tui import MARQUEE_HOLD_TICKS
from terminal_radio.tui.widgets import (
    HistoryTable,
    MarqueeLabel,
    NowPlayingBar,
    SettingsTable,
    StationTable,
)


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


class MarqueeApp(App[None]):
    """A slot exactly twenty cells wide, to make overflow deterministic."""

    CSS = "MarqueeLabel { width: 20; height: 1; }"

    def compose(self) -> ComposeResult:
        yield MarqueeLabel("♪ ", id="marquee")


class StationTableApp(App[None]):
    """Minimal mounted context for station health cells."""

    def compose(self) -> ComposeResult:
        yield StationTable(
            Translator(
                Locale(
                    code="en",
                    name="English",
                    messages={
                        "column.health": "Health",
                        "column.dial": "Dial",
                        "column.station": "Station",
                        "column.info": "Info",
                    },
                )
            ),
            (
                Station(
                    slug="example",
                    name="Example",
                    band=Band.FM,
                    url="https://example.com",
                ),
            ),
        )


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


class StationTableTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_glyph_updates_without_rebuilding_rows(self) -> None:
        """Every health enum has a stable compact cell glyph."""
        expected = {
            StationHealth.UNKNOWN: "·",
            StationHealth.CHECKING: "…",
            StationHealth.ONLINE: "●",
            StationHealth.SLOW: "◐",
            StationHealth.OFFLINE: "×",
        }
        async with StationTableApp().run_test(size=(100, 12)) as pilot:
            table = pilot.app.query_one(StationTable)
            for health, glyph in expected.items():
                table.set_health("example", health)
                await pilot.pause()
                self.assertEqual(table.get_cell("example", "health"), glyph)



class NowPlayingBarLayoutTests(unittest.IsolatedAsyncioTestCase):
    """The title belongs beside the station, not on the line below it."""

    async def test_the_title_sits_on_the_same_row_as_the_station(self) -> None:
        async with NowPlayingApp().run_test(size=(118, 8)) as pilot:
            bar = pilot.app.query_one(NowPlayingBar)
            bar.show(
                PlayerStatus(
                    state=PlaybackState.PLAYING, program="ALL-4-ONE - I SWEAR"
                )
            )
            await pilot.pause()

            station = pilot.app.query_one("#np-station", Static)
            program = pilot.app.query_one("#np-program", Static)

            self.assertIs(program.parent, station.parent)
            self.assertEqual(program.region.y, station.region.y)
            self.assertGreater(program.region.x, station.region.x)

    async def test_the_title_is_marked_as_one(self) -> None:
        async with NowPlayingApp().run_test(size=(118, 8)) as pilot:
            bar = pilot.app.query_one(NowPlayingBar)
            bar.show(PlayerStatus(state=PlaybackState.PLAYING, program="王菲 - 如願"))
            await pilot.pause()

            self.assertEqual(
                str(pilot.app.query_one("#np-program", Static).render()),
                "♪ 王菲 - 如願",
            )

    async def test_a_station_announcing_nothing_leaves_the_slot_empty(self) -> None:
        """A dash beside the name would read as part of the name."""
        async with NowPlayingApp().run_test(size=(118, 8)) as pilot:
            bar = pilot.app.query_one(NowPlayingBar)
            bar.show(PlayerStatus(state=PlaybackState.PLAYING, program=None))
            await pilot.pause()

            rendered = str(pilot.app.query_one("#np-program", Static).render())

            self.assertEqual(rendered.strip(), "")


class MarqueeTests(unittest.IsolatedAsyncioTestCase):
    """A title too long for its slot slides along, the way a car stereo does."""

    LONG = "ALL-4-ONE - I SWEAR (Extended Radio Mix)"
    ROOM = 18  # twenty cells, less the two the prefix takes

    async def _label(self, pilot: object) -> MarqueeLabel:
        """Return the label with its own clock stopped.

        Every test here drives the slide by hand, so the interval that also
        drives it in real use would otherwise add steps of its own.
        """
        label = pilot.app.query_one("#marquee", MarqueeLabel)  # type: ignore[attr-defined]
        if label._timer is not None:
            label._timer.stop()
        return label

    def _shown(self, label: MarqueeLabel) -> str:
        return str(label.render())

    async def test_a_title_that_fits_is_simply_written_out(self) -> None:
        async with MarqueeApp().run_test(size=(40, 4)) as pilot:
            label = await self._label(pilot)
            label.set_text("Short")
            await pilot.pause()

            first = self._shown(label)
            for _ in range(MARQUEE_HOLD_TICKS + 5):
                label._step()
            await pilot.pause()

            self.assertEqual(first, "♪ Short")
            self.assertEqual(self._shown(label), first)

    async def test_a_long_title_holds_still_before_it_moves(self) -> None:
        """The opening has to be readable before anything slides."""
        async with MarqueeApp().run_test(size=(40, 4)) as pilot:
            label = await self._label(pilot)
            label.set_text(self.LONG)
            await pilot.pause()
            opening = self._shown(label)

            for _ in range(MARQUEE_HOLD_TICKS):
                label._step()
            await pilot.pause()
            self.assertEqual(self._shown(label), opening)

            label._step()
            await pilot.pause()
            self.assertNotEqual(self._shown(label), opening)

    async def test_the_title_comes_round_again(self) -> None:
        async with MarqueeApp().run_test(size=(40, 4)) as pilot:
            label = await self._label(pilot)
            label.set_text(self.LONG)
            await pilot.pause()
            opening = self._shown(label)

            for _ in range(MARQUEE_HOLD_TICKS + len(self.LONG) + 7):
                label._step()
            await pilot.pause()

            self.assertEqual(self._shown(label), opening)

    async def test_redrawing_the_same_title_does_not_send_it_back(self) -> None:
        """The bar is refreshed every second and must not reset the slide."""
        async with MarqueeApp().run_test(size=(40, 4)) as pilot:
            label = await self._label(pilot)
            label.set_text(self.LONG)
            for _ in range(MARQUEE_HOLD_TICKS + 4):
                label._step()
            await pilot.pause()
            moved = self._shown(label)

            offset = label._offset
            label.set_text(self.LONG)
            await pilot.pause()

            self.assertEqual(label._offset, offset)
            self.assertEqual(self._shown(label), moved)

    async def test_a_new_title_starts_from_its_beginning(self) -> None:
        async with MarqueeApp().run_test(size=(40, 4)) as pilot:
            label = await self._label(pilot)
            label.set_text(self.LONG)
            for _ in range(MARQUEE_HOLD_TICKS + 4):
                label._step()
            await pilot.pause()

            label.set_text("王菲 - 如願 (2021 央視獻禮片主題曲)")
            await pilot.pause()

            self.assertTrue(self._shown(label).startswith("♪ 王菲"))

    async def test_a_chinese_title_keeps_the_slot_exactly_full(self) -> None:
        """A double width character must never be cut in half at the edge."""
        async with MarqueeApp().run_test(size=(40, 4)) as pilot:
            label = await self._label(pilot)
            label.set_text("周杰倫 - 稻香 (2008 魔杰座專輯收錄曲)")
            await pilot.pause()

            for _ in range(MARQUEE_HOLD_TICKS):
                label._step()
            for _ in range(12):
                label._step()
                await pilot.pause()
                shown = self._shown(label)

                self.assertEqual(cell_len(shown), self.ROOM + cell_len("♪ "))

    async def test_an_empty_title_shows_nothing_and_stays_still(self) -> None:
        async with MarqueeApp().run_test(size=(40, 4)) as pilot:
            label = await self._label(pilot)
            label.set_text("")
            await pilot.pause()

            for _ in range(MARQUEE_HOLD_TICKS + 5):
                label._step()
            await pilot.pause()

            self.assertEqual(self._shown(label), "")


class MarqueeSwitchTests(unittest.IsolatedAsyncioTestCase):
    """The slide can be turned off from the settings page."""

    LONG = "ALL-4-ONE - I SWEAR (Extended Radio Mix)"

    async def test_a_long_title_stands_still_when_the_slide_is_off(self) -> None:
        async with MarqueeApp().run_test(size=(40, 4)) as pilot:
            label = pilot.app.query_one("#marquee", MarqueeLabel)
            if label._timer is not None:
                label._timer.stop()
            label.set_scrolling(False)
            label.set_text(self.LONG)
            await pilot.pause()
            standing = str(label.render())

            for _ in range(MARQUEE_HOLD_TICKS + 10):
                label._step()
            await pilot.pause()

            self.assertEqual(str(label.render()), standing)

    async def test_a_title_left_standing_is_cut_rather_than_spilling(self) -> None:
        """It shares its row with the timer, which must not be pushed off."""
        async with MarqueeApp().run_test(size=(40, 4)) as pilot:
            label = pilot.app.query_one("#marquee", MarqueeLabel)
            label.set_scrolling(False)
            label.set_text(self.LONG)
            await pilot.pause()

            self.assertLessEqual(cell_len(str(label.render())), 20)

    async def test_a_short_title_picks_up_no_padding(self) -> None:
        async with MarqueeApp().run_test(size=(40, 4)) as pilot:
            label = pilot.app.query_one("#marquee", MarqueeLabel)
            label.set_scrolling(False)
            label.set_text("Short")
            await pilot.pause()

            self.assertEqual(str(label.render()), "♪ Short")

    async def test_turning_it_back_on_starts_from_the_beginning(self) -> None:
        async with MarqueeApp().run_test(size=(40, 4)) as pilot:
            label = pilot.app.query_one("#marquee", MarqueeLabel)
            if label._timer is not None:
                label._timer.stop()
            label.set_text(self.LONG)
            for _ in range(MARQUEE_HOLD_TICKS + 5):
                label._step()

            label.set_scrolling(False)
            label.set_scrolling(True)
            await pilot.pause()

            self.assertEqual(label._offset, 0)

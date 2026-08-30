"""End-to-end behavior tests for the terminal application."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from textual.widgets import Button, Static, TabbedContent, TabPane

from app.core.config import Settings
from app.core.i18n import LocaleRepository
from app.models import Band, PlaybackState
from app.services import (
    HistoryLog,
    PersistedState,
    RadioService,
    StateStore,
    StationCatalog,
    StationSummary,
    ThemeRepository,
    build_radio_service,
)
from app.tui.app import HISTORY_TAB, HOME_TAB, SETTINGS_TAB, RadioApp
from app.tui.widgets import HistoryTable, SettingsTable


class MemoryPlayer:
    """Small in-memory replacement for the external mpv process."""

    def __init__(self) -> None:
        self._running = False
        self._paused = False
        self._volume = 100
        self._muted = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._running and self._paused

    def start(self, _url: str) -> None:
        self._running = True
        self._paused = False

    def stop(self) -> None:
        self._running = False
        self._paused = False

    def set_paused(self, paused: bool) -> None:
        self._paused = paused

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


class RadioAppTests(unittest.IsolatedAsyncioTestCase):
    async def test_history_and_settings_tables_reserve_twenty_four_centered_rows(
        self,
    ) -> None:
        """Both pages reserve twenty-four rows with compact symmetric spacing."""
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                data_dir=Path(directory),
                autoplay_last_station=False,
                status_refresh_seconds=60,
            )
            app = RadioApp(
                build_radio_service(settings),
                ThemeRepository.from_file(settings.themes_file),
                LocaleRepository.from_directory(
                    settings.locales_dir, settings.locale
                ),
                settings,
            )

            async with app.run_test(size=(160, 48)) as pilot:
                for tab_id, table_type in (
                    (HISTORY_TAB, HistoryTable),
                    (SETTINGS_TAB, SettingsTable),
                ):
                    with self.subTest(tab=tab_id):
                        app.query_one(TabbedContent).active = tab_id
                        await pilot.pause()

                        pane = app.query_one(f"#{tab_id}", TabPane)
                        table = app.query_one(table_type)
                        action_id = (
                            "#history-actions"
                            if tab_id == HISTORY_TAB
                            else "#settings-actions"
                        )
                        top_gap = table.region.y - pane.content_region.y
                        bottom_gap = pane.content_region.bottom - table.region.bottom

                        self.assertAlmostEqual(top_gap, bottom_gap, delta=1)
                        self.assertEqual(
                            table.region.height - table.header_height,
                            24,
                        )
                        self.assertEqual(
                            pane.query_one(".table-action-spacer").region.height,
                            1,
                        )
                        self.assertEqual(pane.query_one(action_id).region.height, 1)
                        self.assertLess(table.region.height, pane.content_region.height)

    async def test_long_tables_scroll_inside_their_page_only(self) -> None:
        """Overflowing rows must scroll without moving either compact page."""
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                data_dir=Path(directory),
                autoplay_last_station=False,
                status_refresh_seconds=60,
            )
            app = RadioApp(
                build_radio_service(settings),
                ThemeRepository.from_file(settings.themes_file),
                LocaleRepository.from_directory(
                    settings.locales_dir, settings.locale
                ),
                settings,
            )

            async with app.run_test(size=(120, 24)) as pilot:
                for tab_id, table_type in (
                    (HISTORY_TAB, HistoryTable),
                    (SETTINGS_TAB, SettingsTable),
                ):
                    with self.subTest(tab=tab_id):
                        app.query_one(TabbedContent).active = tab_id
                        table = app.query_one(table_type)
                        for _ in range(20):
                            if table.has_focus:
                                break
                            await pilot.pause()
                        self.assertTrue(table.has_focus)
                        if isinstance(table, HistoryTable):
                            table.show(
                                tuple(
                                    StationSummary(
                                        station_slug=f"station-{index}",
                                        station_name=f"Station {index}",
                                    )
                                    for index in range(40)
                                )
                            )
                            await pilot.pause()
                        elif isinstance(table, SettingsTable):
                            table.show(
                                tuple(
                                    (
                                        f"setting-{index}",
                                        f"Setting {index}",
                                        "Value",
                                        "Note",
                                    )
                                    for index in range(40)
                                )
                            )
                            await pilot.pause()
                        pane = app.query_one(f"#{tab_id}", TabPane)
                        for _ in range(20):
                            if table.max_scroll_y > 0:
                                break
                            await pilot.pause()
                        self.assertGreater(table.max_scroll_y, 0)
                        self.assertEqual(pane.max_scroll_y, 0)

                        table.focus()
                        await pilot.press("pagedown")

                        self.assertGreater(table.scroll_y, 0)
                        self.assertEqual(pane.scroll_y, 0)

    async def test_button_focus_does_not_reverse_any_label(self) -> None:
        """Keyboard or mouse focus must not mark button text in reverse video."""
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                data_dir=Path(directory),
                autoplay_last_station=False,
                status_refresh_seconds=60,
            )
            app = RadioApp(
                build_radio_service(settings),
                ThemeRepository.from_file(settings.themes_file),
                LocaleRepository.from_directory(
                    settings.locales_dir, settings.locale
                ),
                settings,
            )

            async with app.run_test(size=(160, 48)) as pilot:
                for tab_id, button_id in (
                    (HISTORY_TAB, "#clear-history"),
                    (SETTINGS_TAB, "#reset-settings"),
                ):
                    app.query_one(TabbedContent).active = tab_id
                    await pilot.pause()
                    button = app.query_one(button_id, Button)
                    button.focus()
                    await pilot.pause()
                    self.assertFalse(button.styles.text_style.reverse)

                app.query_one(TabbedContent).active = HISTORY_TAB
                await pilot.pause()
                await pilot.click("#clear-history")
                for button_id in ("#confirm-cancel", "#confirm-accept"):
                    button = app.screen.query_one(button_id, Button)
                    button.focus()
                    await pilot.pause()
                    self.assertFalse(button.styles.text_style.reverse)

    async def test_active_tab_is_filled_without_an_underline(self) -> None:
        """The selected tab must stay filled while the underline stays hidden."""
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                data_dir=Path(directory),
                autoplay_last_station=False,
                status_refresh_seconds=60,
            )
            app = RadioApp(
                build_radio_service(settings),
                ThemeRepository.from_file(settings.themes_file),
                LocaleRepository.from_directory(
                    settings.locales_dir, settings.locale
                ),
                settings,
            )

            async with app.run_test(size=(160, 48)) as pilot:
                app.query_one("#home").focus()
                await pilot.pause()

                tabs = app.query_one(TabbedContent)
                active = tabs.get_tab(HOME_TAB)
                inactive = tabs.get_tab(app.band_tab(Band.FM))
                self.assertNotEqual(active.styles.background, inactive.styles.background)
                self.assertEqual(app.query_one("Underline").styles.display, "none")

    async def test_reactivating_the_playing_station_leaves_it_playing(self) -> None:
        """The station list must not double as the playback pause control."""
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                data_dir=Path(directory),
                autoplay_last_station=False,
                status_refresh_seconds=60,
            )
            service = RadioService(
                catalog=StationCatalog.from_file(settings.stations_file),
                player=MemoryPlayer(),
                history=HistoryLog(settings.history_file),
                state=StateStore(settings.state_file),
                autoplay_last_station=False,
            )
            app = RadioApp(
                service,
                ThemeRepository.from_file(settings.themes_file),
                LocaleRepository.from_directory(
                    settings.locales_dir, settings.locale
                ),
                settings,
            )

            async with app.run_test(size=(160, 48)) as pilot:
                app.query_one(TabbedContent).active = app.band_tab(Band.FM)
                await pilot.pause()

                app.play_selected_station()
                self.assertEqual(service.status().state, PlaybackState.PLAYING)

                app.play_selected_station()
                self.assertEqual(service.status().state, PlaybackState.PLAYING)

    async def test_clicking_the_playback_state_pauses_it(self) -> None:
        """The playback label at bottom left must pause the active stream."""
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                data_dir=Path(directory),
                autoplay_last_station=False,
                status_refresh_seconds=60,
            )
            service = RadioService(
                catalog=StationCatalog.from_file(settings.stations_file),
                player=MemoryPlayer(),
                history=HistoryLog(settings.history_file),
                state=StateStore(settings.state_file),
                autoplay_last_station=False,
            )
            app = RadioApp(
                service,
                ThemeRepository.from_file(settings.themes_file),
                LocaleRepository.from_directory(
                    settings.locales_dir, settings.locale
                ),
                settings,
            )

            async with app.run_test(size=(160, 48)) as pilot:
                app.query_one(TabbedContent).active = app.band_tab(Band.FM)
                await pilot.pause()
                app.play_selected_station()

                await pilot.click("#np-state")

                self.assertEqual(service.status().state, PlaybackState.PAUSED)

    async def test_clear_history_waits_for_centered_confirmation(self) -> None:
        """History must remain until the centered confirmation is accepted."""
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                data_dir=Path(directory),
                autoplay_last_station=False,
                status_refresh_seconds=60,
            )
            service = RadioService(
                catalog=StationCatalog.from_file(settings.stations_file),
                player=MemoryPlayer(),
                history=HistoryLog(settings.history_file),
                state=StateStore(settings.state_file),
                autoplay_last_station=False,
            )
            station = service.list_stations(Band.FM)[0]
            service.play(station.slug)
            service.stop()
            app = RadioApp(
                service,
                ThemeRepository.from_file(settings.themes_file),
                LocaleRepository.from_directory(
                    settings.locales_dir, settings.locale
                ),
                settings,
            )

            async with app.run_test(size=(160, 48)) as pilot:
                app.query_one(TabbedContent).active = HISTORY_TAB
                await pilot.pause()
                self.assertTrue(app.query("#clear-history"))
                clear_button = app.query_one("#clear-history")
                self.assertGreater(
                    clear_button.region.y, app.query_one(HistoryTable).region.y
                )
                self.assertLessEqual(
                    clear_button.region.bottom, app.query_one("#now-playing").region.y
                )

                await pilot.click("#clear-history")

                self.assertTrue(service.history())
                dialog = app.screen.query_one("#confirm-dialog")
                self.assertAlmostEqual(
                    dialog.region.center[0], app.screen.region.center[0], delta=0.5
                )
                self.assertAlmostEqual(
                    dialog.region.center[1], app.screen.region.center[1], delta=0.5
                )

                await pilot.click("#confirm-cancel")
                self.assertTrue(service.history())
                await pilot.click("#clear-history")
                await pilot.click("#confirm-accept")

                self.assertEqual(service.history(), ())
                self.assertEqual(app.query_one(HistoryTable).row_count, 0)

    async def test_reset_settings_waits_for_confirmation_and_preserves_library(self) -> None:
        """Confirmed reset restores defaults without deleting the user's library."""
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                data_dir=Path(directory),
                autoplay_last_station=True,
                enable_animations=False,
                status_refresh_seconds=60,
            )
            catalog = StationCatalog.from_file(settings.stations_file)
            station = catalog.by_band(Band.FM)[0]
            state = StateStore(settings.state_file)
            state.save(
                PersistedState(
                    last_station_slug=station.slug,
                    theme_name="nord",
                    favorites=[station.slug],
                    volume=55,
                    muted=True,
                    autoplay_last_station=False,
                    enable_animations=True,
                    locale="en",
                )
            )
            service = RadioService(
                catalog=catalog,
                player=MemoryPlayer(),
                history=HistoryLog(settings.history_file),
                state=state,
                autoplay_last_station=settings.autoplay_last_station,
                enable_animations=settings.enable_animations,
            )
            app = RadioApp(
                service,
                ThemeRepository.from_file(settings.themes_file),
                LocaleRepository.from_directory(
                    settings.locales_dir, settings.locale
                ),
                settings,
            )

            async with app.run_test(size=(160, 48)) as pilot:
                app.query_one(TabbedContent).active = SETTINGS_TAB
                await pilot.pause()
                self.assertTrue(app.query("#reset-settings"))
                reset_button = app.query_one("#reset-settings")
                self.assertGreater(
                    reset_button.region.y, app.query_one(SettingsTable).region.y
                )
                self.assertLessEqual(
                    reset_button.region.bottom, app.query_one("#now-playing").region.y
                )

                await pilot.click("#reset-settings")

                self.assertEqual(service.preferences().volume, 55)
                await pilot.click("#confirm-accept")

                restored = service.preferences()
                self.assertEqual(restored.volume, 100)
                self.assertFalse(restored.muted)
                self.assertTrue(restored.autoplay_last_station)
                self.assertFalse(restored.enable_animations)
                self.assertEqual(restored.locale, "zh-Hant")
                self.assertEqual(restored.theme_name, "sonic")
                self.assertEqual(restored.favorites, [station.slug])
                self.assertEqual(restored.last_station_slug, station.slug)
                self.assertEqual(app.t.code, "zh-Hant")
                self.assertEqual(str(app.theme), "sonic")

    async def test_volume_adjustment_keeps_both_readouts_in_sync(self) -> None:
        """A volume key must refresh the settings value as well as the footer."""
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                data_dir=Path(directory),
                autoplay_last_station=False,
                status_refresh_seconds=60,
            )
            service = build_radio_service(settings)
            app = RadioApp(
                service,
                ThemeRepository.from_file(settings.themes_file),
                LocaleRepository.from_directory(
                    settings.locales_dir, settings.locale
                ),
                settings,
            )

            async with app.run_test(size=(160, 48)) as pilot:
                app.query_one(TabbedContent).active = SETTINGS_TAB
                await pilot.pause()

                app.action_volume_down()
                await pilot.pause()

                table = app.query_one(SettingsTable)
                self.assertEqual(table.get_cell("volume", "value"), "95%")
                self.assertIn("95%", str(app.query_one("#np-volume", Static).render()))

"""End-to-end behavior tests for the terminal application."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rich.cells import cell_len
from textual.content import Content
from textual.widgets import Button, Input, Select, Static, TabbedContent, TabPane

from terminal_radio.core.config import Settings
from terminal_radio.core.i18n import LocaleRepository
from terminal_radio.enums import Band, PlaybackState
from terminal_radio.models import Station
from terminal_radio.services import (
    HistoryLog,
    PersistedState,
    RadioService,
    StateStore,
    StationCatalog,
    StationSummary,
    ThemeRepository,
    build_radio_service,
)
from terminal_radio.tui.screens import StationSearchScreen
from terminal_radio.tui.app import (
    FAVORITES_TAB,
    HISTORY_TAB,
    HOME_TAB,
    SETTINGS_TAB,
    STATISTICS_TAB,
    RadioApp,
)
from terminal_radio.tui.widgets import (
    HistoryTable,
    ListeningStatsPanel,
    SettingsTable,
    StationTable,
)


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

    def fade_out(self, seconds: float) -> None:
        self.faded = seconds

    def drain_program_changes(self) -> tuple[str, ...]:
        announced, self.announced = tuple(getattr(self, "announced", ())), []
        return announced


class RadioAppTests(unittest.IsolatedAsyncioTestCase):
    async def test_statistics_tab_renders_and_scrolls_inside_its_page(self) -> None:
        """The charts refresh on activation and own their vertical scrolling."""
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                data_dir=Path(directory),
                autoplay_last_station=False,
                status_refresh_seconds=60,
            )
            elapsed = [0.0]
            service = RadioService(
                catalog=StationCatalog.from_file(settings.stations_file),
                player=MemoryPlayer(),
                history=HistoryLog(settings.history_file),
                state=StateStore(settings.state_file),
                autoplay_last_station=False,
                clock=lambda: elapsed[0],
            )
            station = service.list_stations(Band.FM)[0]
            service.play(station.slug)
            elapsed[0] = 120
            service.stop()
            app = RadioApp(
                service,
                ThemeRepository.from_file(settings.themes_file),
                LocaleRepository.from_directory(
                    settings.locales_dir, settings.locale
                ),
                settings,
            )

            async with app.run_test(size=(120, 24)) as pilot:
                app.query_one(TabbedContent).active = STATISTICS_TAB
                await pilot.pause()

                pane = app.query_one(f"#{STATISTICS_TAB}", TabPane)
                panel = pane.query_one(ListeningStatsPanel)
                report_widget = panel.query_one("#statistics-report", Static)
                for _ in range(20):
                    if report_widget.content_region.width > 0:
                        break
                    await pilot.pause()
                self.assertGreater(report_widget.content_region.width, 0)
                rendered_report = report_widget.render()
                self.assertIsInstance(rendered_report, Content)
                report = str(rendered_report)

                self.assertIn("聆聽統計", report)
                self.assertIn("警廣全國網", report)
                self.assertNotIn(station.name, report)
                for heading in (
                    "聆聽統計",
                    "最常聽前十名",
                    "近 14 天趨勢",
                    "每週收聽分布",
                    "時段分布",
                    "波段占比",
                ):
                    offset = rendered_report.plain.index(heading)
                    self.assertTrue(
                        rendered_report.get_style_at_offset(offset).bold,
                        f"{heading} should be bold",
                    )
                self.assertLessEqual(
                    max(cell_len(line) for line in report.splitlines()),
                    report_widget.content_region.width,
                )
                self.assertEqual(report_widget.styles.text_wrap, "nowrap")
                self.assertEqual(panel.styles.scrollbar_size_vertical, 0)
                self.assertEqual(pane.max_scroll_y, 0)
                self.assertGreater(panel.max_scroll_y, 0)

                panel.focus()
                for _ in range(10):
                    if panel.has_focus:
                        break
                    await pilot.pause()
                self.assertTrue(panel.has_focus)
                panel.action_scroll_down()
                for _ in range(20):
                    if panel.scroll_y > 0:
                        break
                    await pilot.pause()
                self.assertGreater(panel.scroll_y, 0)
                self.assertEqual(pane.scroll_y, 0)

    async def test_shortcut_help_opens_from_key_and_settings(self) -> None:
        """A centered localized shortcut card is available from both entry points."""
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

            async with app.run_test(size=(120, 32)) as pilot:
                await pilot.press("question_mark")
                dialog = app.screen.query_one("#shortcut-dialog")
                content = str(app.screen.query_one("#shortcut-content", Static).render())
                self.assertAlmostEqual(
                    dialog.region.center[0], app.screen.region.center[0], delta=0.5
                )
                self.assertIn("搜尋電台", content)
                self.assertIn("/", content)
                await pilot.press("escape")

                app.query_one(TabbedContent).active = SETTINGS_TAB
                await pilot.pause()
                table = app.query_one(SettingsTable)
                table.move_cursor(row=table.get_row_index("shortcuts"))
                await pilot.press("enter")

                self.assertTrue(app.screen.query("#shortcut-dialog"))

    async def test_custom_station_add_edit_and_confirmed_delete(self) -> None:
        """Settings manages only local stations and confirms deletion."""
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
                settings_table = app.query_one(SettingsTable)
                settings_table.move_cursor(
                    row=settings_table.get_row_index("custom_stations")
                )
                await pilot.press("enter")
                manager = app.screen.query_one("#custom-station-list", StationTable)
                self.assertEqual(manager.row_count, 0)

                await pilot.click("#custom-station-add")
                app.screen.query_one("#custom-name", Input).value = "我的電台"
                app.screen.query_one("#custom-band", Select).value = Band.AM
                app.screen.query_one("#custom-frequency", Input).value = "1000"
                app.screen.query_one("#custom-url", Input).value = (
                    "https://example.com/my-radio"
                )
                app.screen.query_one("#custom-description", Input).value = "談話"
                await pilot.click("#custom-save")
                await pilot.pause()

                added = service.custom_stations()[0]
                self.assertEqual(added.name, "我的電台")
                self.assertEqual(
                    app.screen.query_one("#custom-station-list", StationTable).row_count,
                    1,
                )

                await pilot.click("#custom-station-edit")
                app.screen.query_one("#custom-name", Input).value = "我的新電台"
                await pilot.click("#custom-save")
                await pilot.pause()
                self.assertEqual(service.custom_stations()[0].name, "我的新電台")

                await pilot.click("#custom-station-delete")
                self.assertTrue(app.screen.query("#confirm-dialog"))
                await pilot.click("#confirm-accept")
                await pilot.pause()
                self.assertEqual(service.custom_stations(), ())

    async def test_slash_search_filters_and_plays_a_result(self) -> None:
        """Slash opens global live search and Enter plays its highlighted row."""
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
                await pilot.press("slash")
                field = app.screen.query_one("#station-search-input", Input)
                self.assertTrue(field.has_focus)
                field.value = "Hit FM"
                await pilot.pause()
                results = app.screen.query_one("#station-search-results", StationTable)
                self.assertEqual(results.row_count, 1)

                await pilot.press("enter")

                status = service.status()
                self.assertEqual(status.state, PlaybackState.PLAYING)
                self.assertEqual(status.station.slug, "hitfm-taipei")

    async def test_escape_closes_search_without_playing(self) -> None:
        """Dismissing search leaves playback unchanged."""
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
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.press("slash")
                await pilot.press("escape")
                self.assertFalse(app.query("#station-search-input"))
                self.assertEqual(app._service.status().state, PlaybackState.STOPPED)

    async def test_settings_toggle_reconnect_and_set_sleep_preset(self) -> None:
        """Reconnect and the sleep timer are controlled from Settings."""
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
                app.query_one(TabbedContent).active = SETTINGS_TAB
                await pilot.pause()
                table = app.query_one(SettingsTable)
                self.assertEqual(table.get_cell("reconnect", "value"), "開")

                table.move_cursor(row=table.get_row_index("reconnect"))
                await pilot.press("enter")
                self.assertFalse(service.auto_reconnect)
                self.assertEqual(table.get_cell("reconnect", "value"), "關")

                self.assertEqual(table.get_cell("health_auto", "value"), "開")
                table.move_cursor(row=table.get_row_index("health_auto"))
                await pilot.press("enter")
                self.assertFalse(service.auto_health_check)
                self.assertEqual(table.get_cell("health_auto", "value"), "關")
                self.assertEqual(
                    table.get_cell("health_check_all", "name"),
                    "立即檢查所有電台",
                )

                table.move_cursor(row=table.get_row_index("sleep_timer"))
                await pilot.press("enter")
                await pilot.click("#sleep-15")

                remaining = service.sleep_remaining_seconds()
                self.assertIsNotNone(remaining)
                self.assertGreater(remaining or 0, 899)
                # A live countdown, so the exact second depends on the machine.
                self.assertRegex(
                    str(table.get_cell("sleep_timer", "value")), r"1[45]:\d{2}"
                )

    async def test_custom_sleep_timer_rejects_invalid_minutes(self) -> None:
        """Custom sleep minutes stay in range and keep invalid input visible."""
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
                app.query_one(TabbedContent).active = SETTINGS_TAB
                await pilot.pause()
                table = app.query_one(SettingsTable)
                table.move_cursor(row=table.get_row_index("sleep_timer"))
                await pilot.press("enter")

                field = app.screen.query_one("#sleep-custom", Input)
                field.value = "0"
                await pilot.click("#sleep-custom-submit")
                self.assertTrue(str(app.screen.query_one("#sleep-error", Static).content))
                self.assertIsNone(service.sleep_remaining_seconds())

                field.value = "45"
                await pilot.pause()
                await pilot.press("enter")
                self.assertGreater(service.sleep_remaining_seconds() or 0, 2699)

    async def test_station_history_and_settings_tables_share_centered_layout(
        self,
    ) -> None:
        """All table pages reserve twenty-four rows with symmetric spacing."""
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
                for tab_id, table_type, footer_selector in (
                    (
                        app.band_tab(Band.FM),
                        StationTable,
                        ".table-action-footer-spacer",
                    ),
                    (
                        app.band_tab(Band.AM),
                        StationTable,
                        ".table-action-footer-spacer",
                    ),
                    (
                        FAVORITES_TAB,
                        StationTable,
                        ".table-action-footer-spacer",
                    ),
                    (HISTORY_TAB, HistoryTable, "#history-actions"),
                    (SETTINGS_TAB, SettingsTable, "#settings-actions"),
                ):
                    with self.subTest(tab=tab_id):
                        app.query_one(TabbedContent).active = tab_id
                        await pilot.pause()

                        pane = app.query_one(f"#{tab_id}", TabPane)
                        table = pane.query_one(table_type)
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
                        self.assertEqual(
                            pane.query_one(footer_selector).region.height,
                            1,
                        )
                        self.assertLess(table.region.height, pane.content_region.height)

    async def test_long_tables_scroll_inside_their_page_only(self) -> None:
        """Overflowing rows must scroll without moving any table page."""
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
                    (app.band_tab(Band.FM), StationTable),
                    (app.band_tab(Band.AM), StationTable),
                    (FAVORITES_TAB, StationTable),
                    (HISTORY_TAB, HistoryTable),
                    (SETTINGS_TAB, SettingsTable),
                ):
                    with self.subTest(tab=tab_id):
                        app.query_one(TabbedContent).active = tab_id
                        pane = app.query_one(f"#{tab_id}", TabPane)
                        table = pane.query_one(table_type)
                        for _ in range(20):
                            if table.has_focus:
                                break
                            await pilot.pause()
                        self.assertTrue(table.has_focus)
                        if isinstance(table, StationTable):
                            rows = tuple(
                                Station(
                                    slug=f"station-{index}",
                                    name=f"Station {index}",
                                    band=Band.FM,
                                    frequency=f"{88 + index / 10:.1f}",
                                    url=f"https://example.com/{index}",
                                )
                                for index in range(40)
                            )
                        elif isinstance(table, HistoryTable):
                            rows = tuple(
                                StationSummary(
                                    station_slug=f"station-{index}",
                                    station_name=f"Station {index}",
                                )
                                for index in range(40)
                            )
                        elif isinstance(table, SettingsTable):
                            rows = tuple(
                                (
                                    f"setting-{index}",
                                    f"Setting {index}",
                                    "Value",
                                    "Note",
                                )
                                for index in range(40)
                            )
                        for _ in range(20):
                            # A queued TabActivated handler may legitimately
                            # refresh the table once. Reapply the fixture until
                            # both its rows and layout are observable together.
                            if isinstance(table, StationTable):
                                table.set_stations(rows)
                            else:
                                table.show(rows)
                            await pilot.pause()
                            if table.row_count == 40 and table.max_scroll_y > 0:
                                break
                        self.assertGreater(table.max_scroll_y, 0)
                        self.assertEqual(pane.max_scroll_y, 0)

                        # Reassert the fixture and the focus on every attempt:
                        # a queued handler may refresh the table away, and the
                        # key only lands once the focus change has been seen.
                        for _ in range(20):
                            if table.max_scroll_y == 0:
                                if isinstance(table, StationTable):
                                    table.set_stations(rows)
                                else:
                                    table.show(rows)
                                await pilot.pause()
                            table.focus()
                            await pilot.pause()
                            await pilot.press("pagedown")
                            if table.scroll_y > 0:
                                break
                            await pilot.pause()

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

    async def test_history_csv_headers_follow_current_interface_language(self) -> None:
        """History CSV uses the translator active when the export begins."""
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                data_dir=Path(directory),
                autoplay_last_station=False,
                status_refresh_seconds=60,
            )
            service = build_radio_service(settings)
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
                await pilot.click("#export-history")

                filename = str(
                    app.screen.query_one("#export-filename", Static).render()
                )
                app.screen.dismiss(Path(directory))
                await pilot.pause()

                with (Path(directory) / filename).open(
                    encoding="utf-8-sig", newline=""
                ) as stream:
                    header = stream.readline().strip()
                self.assertEqual(
                    header,
                    "頻率,電台,次數,收聽時間,暫停時間,最後收聽",
                )

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
                    auto_reconnect=False,
                    auto_health_check=False,
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
                self.assertTrue(restored.auto_reconnect)
                self.assertTrue(restored.auto_health_check)
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


class StationSearchTests(unittest.IsolatedAsyncioTestCase):
    """The search modal, and the tab bar icon that opens it."""

    def _app(self, directory: str) -> tuple[RadioApp, Settings]:
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
            LocaleRepository.from_directory(settings.locales_dir, settings.locale),
            settings,
        )
        return app, settings

    async def test_the_icon_floats_over_the_tab_bar_without_shortening_it(self) -> None:
        """The overlay layer must not take a row away from the tabbed content."""
        with tempfile.TemporaryDirectory() as directory:
            app, _ = self._app(directory)
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()

                icon = app.query_one("#search-button")
                tabs = app.query_one("#tabs", TabbedContent)

                self.assertEqual(icon.region.y, 0)
                self.assertEqual(tabs.region.y, 0)
                self.assertEqual(icon.region.height, 1)
                # The icon sits at the right edge, clear of the leftmost tabs.
                self.assertGreater(icon.region.x, tabs.region.width // 2)

    async def test_clicking_the_icon_opens_the_search_modal(self) -> None:
        """The icon is the pointer equivalent of the slash key."""
        with tempfile.TemporaryDirectory() as directory:
            app, _ = self._app(directory)
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()

                await pilot.click("#search-button")
                await pilot.pause()

                self.assertIsInstance(app.screen, StationSearchScreen)

                await pilot.press("escape")
                await pilot.pause()
                self.assertNotIsInstance(app.screen, StationSearchScreen)

    async def test_the_icon_gives_way_on_a_narrow_terminal(self) -> None:
        """Below the compact breakpoint every column of the tab bar is needed."""
        with tempfile.TemporaryDirectory() as directory:
            app, _ = self._app(directory)
            async with app.run_test(size=(70, 24)) as pilot:
                await pilot.pause()
                self.assertFalse(app.query_one("#search-button").display)

    async def test_typing_a_query_does_not_fire_the_global_shortcuts(self) -> None:
        """Letters bound to stop, favorite and quit have to reach the field."""
        with tempfile.TemporaryDirectory() as directory:
            app, _ = self._app(directory)
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await pilot.press("slash")
                await pilot.pause()

                await pilot.press(*"news")
                await pilot.pause()

                field = app.screen.query_one("#station-search-input", Input)
                self.assertEqual(field.value, "news")
                self.assertIsInstance(app.screen, StationSearchScreen)

    async def test_a_frequency_query_lists_the_dial_before_prose_matches(self) -> None:
        """Typing 98 has to find FM 98.1, not a description that mentions it."""
        with tempfile.TemporaryDirectory() as directory:
            app, _ = self._app(directory)
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                await pilot.press("slash")
                await pilot.pause()

                await pilot.press(*"98")
                await pilot.pause()

                results = app.screen.query_one("#station-search-results", StationTable)
                first = results.selected_station
                self.assertIsNotNone(first)
                assert first is not None
                self.assertTrue(first.dial.startswith("FM 98"))


class ProgramTabTests(unittest.IsolatedAsyncioTestCase):
    """The tab showing what the stations have been announcing."""

    def _app(self, directory: str) -> tuple[RadioApp, RadioService]:
        from terminal_radio.services import NowPlayingLog

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
            now_playing=NowPlayingLog(settings.now_playing_file),
        )
        app = RadioApp(
            service,
            ThemeRepository.from_file(settings.themes_file),
            LocaleRepository.from_directory(settings.locales_dir, settings.locale),
            settings,
        )
        return app, service

    async def test_announced_titles_appear_newest_first(self) -> None:
        from terminal_radio.tui.widgets import NowPlayingTable

        with tempfile.TemporaryDirectory() as directory:
            app, service = self._app(directory)
            settings = Settings(data_dir=Path(directory))
            from terminal_radio.services import NowPlayingLog

            log = NowPlayingLog(settings.now_playing_file)
            log.record(service.get_station("icrt"), "Coldplay - Yellow")
            log.record(service.get_station("icrt"), "Dua Lipa - Houdini")

            async with app.run_test(size=(160, 48)) as pilot:
                app.query_one(TabbedContent).active = "tab-now-playing"
                await pilot.pause()
                await pilot.pause()

                table = app.query_one("#now-playing-log", NowPlayingTable)

                self.assertEqual(table.row_count, 2)
                self.assertEqual(
                    table.get_row_at(0)[2], "Dua Lipa - Houdini"
                )
                self.assertEqual(table.get_row_at(1)[2], "Coldplay - Yellow")

    async def test_an_empty_log_leaves_an_empty_table(self) -> None:
        from terminal_radio.tui.widgets import NowPlayingTable

        with tempfile.TemporaryDirectory() as directory:
            app, _ = self._app(directory)
            async with app.run_test(size=(160, 48)) as pilot:
                app.query_one(TabbedContent).active = "tab-now-playing"
                await pilot.pause()

                self.assertEqual(
                    app.query_one("#now-playing-log", NowPlayingTable).row_count, 0
                )

    async def test_clearing_asks_first_and_then_empties_the_table(self) -> None:
        from terminal_radio.services import NowPlayingLog
        from terminal_radio.tui.widgets import NowPlayingTable

        with tempfile.TemporaryDirectory() as directory:
            app, service = self._app(directory)
            settings = Settings(data_dir=Path(directory))
            NowPlayingLog(settings.now_playing_file).record(
                service.get_station("icrt"), "Coldplay - Yellow"
            )

            async with app.run_test(size=(160, 48)) as pilot:
                app.query_one(TabbedContent).active = "tab-now-playing"
                await pilot.pause()
                await pilot.pause()
                table = app.query_one("#now-playing-log", NowPlayingTable)
                self.assertEqual(table.row_count, 1)

                await pilot.click("#clear-now-playing")
                await pilot.pause()
                # Cancel takes the keyboard, so confirming has to be deliberate.
                await pilot.click("#confirm-accept")
                await pilot.pause()

                self.assertEqual(table.row_count, 0)

    async def test_the_headings_follow_the_interface_language(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app, _ = self._app(directory)
            async with app.run_test(size=(160, 48)) as pilot:
                app.query_one(TabbedContent).active = "tab-now-playing"
                await pilot.pause()

                app.apply_locale("en")
                await pilot.pause()

                tab = app.query_one(TabbedContent).get_tab("tab-now-playing")
                self.assertEqual(str(tab.label), "Tracks")
                self.assertEqual(
                    str(app.query_one("#clear-now-playing", Button).label),
                    "Clear tracks",
                )


class ScrollTitlesSettingTests(unittest.IsolatedAsyncioTestCase):
    """The sliding title is a preference, remembered between runs."""

    def _app(self, directory: str, **overrides: object) -> tuple[RadioApp, RadioService]:
        settings = Settings(
            data_dir=Path(directory),
            autoplay_last_station=False,
            status_refresh_seconds=60,
            **overrides,
        )
        service = RadioService(
            catalog=StationCatalog.from_file(settings.stations_file),
            player=MemoryPlayer(),
            history=HistoryLog(settings.history_file),
            state=StateStore(settings.state_file),
            autoplay_last_station=False,
            scroll_titles=settings.scroll_titles,
        )
        app = RadioApp(
            service,
            ThemeRepository.from_file(settings.themes_file),
            LocaleRepository.from_directory(settings.locales_dir, settings.locale),
            settings,
        )
        return app, service

    async def test_the_settings_page_toggles_it(self) -> None:
        from terminal_radio.tui.widgets import MarqueeLabel

        with tempfile.TemporaryDirectory() as directory:
            app, service = self._app(directory)
            async with app.run_test(size=(160, 48)) as pilot:
                app.query_one(TabbedContent).active = SETTINGS_TAB
                await pilot.pause()
                table = app.query_one(SettingsTable)
                keys = [key for key, *_ in table._rows]
                self.assertIn("scroll_titles", keys)

                self.assertTrue(service.scroll_titles)
                app.toggle_setting("scroll_titles")
                await pilot.pause()

                self.assertFalse(service.scroll_titles)
                label = app.query_one("#np-program", MarqueeLabel)
                self.assertFalse(label._scrolling)

    async def test_the_choice_outlives_the_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app, service = self._app(directory)
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                app.toggle_setting("scroll_titles")

            # A second run, with the environment default still saying on.
            app, service = self._app(directory)
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()

                self.assertFalse(service.scroll_titles)

    async def test_the_environment_can_turn_it_off_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, service = self._app(directory, scroll_titles=False)

            self.assertFalse(service.scroll_titles)

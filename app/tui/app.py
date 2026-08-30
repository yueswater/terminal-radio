"""Textual application driving the radio from the terminal."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.timer import Timer
from textual.widgets import Button, Static, TabbedContent, TabPane

from app.core.config import Settings, get_settings
from app.constants.tui import (
    ABOUT_TAB,
    COMPACT_WIDTH,
    FAVORITES_TAB,
    HISTORY_TAB,
    HOME_TAB,
    SETTINGS_TAB,
    STATISTICS_TAB,
    TAB_LABELS,
    THEMES_TAB,
    VOLUME_STEP,
    WIDE_WIDTH,
)
from app.core.exceptions import RadioError
from app.core.i18n import LocaleRepository, Translator
from app.enums import Band, StationHealth
from app.models import Station
from app.services import (
    RadioService,
    ThemeRepository,
    build_radio_service,
    find_config_files,
    history_csv_filename,
    read_export,
    write_export,
    write_history_csv,
    StationHealthSnapshot,
)
from app.tui.formatting import format_duration, format_path
from app.tui.screens import (
    ConfirmationScreen,
    CustomStationFormScreen,
    CustomStationManagerScreen,
    ExportScreen,
    GoodbyeScreen,
    ImportScreen,
    SleepTimerScreen,
    StationSearchScreen,
    ShortcutHelpScreen,
)
from app.tui.theming import register_themes, resolve_theme_name
from app.tui.widgets import (
    AboutPanel,
    HistoryTable,
    HomePanel,
    KeyHintBar,
    ListeningStatsPanel,
    LogoBlock,
    NowPlayingBar,
    SettingsTable,
    StationTable,
    ThemeGallery,
)

class RadioApp(App[None]):
    """Terminal UI listing stations per band and controlling playback."""

    CSS_PATH = "radio.tcss"
    TITLE = "Radio"

    # The UI is a picker, not an editor, so no widget ever accepts typed text.
    # Disabling the palette removes the only text input Textual adds by default.
    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        Binding("enter", "activate", "Select"),
        Binding("space", "pause", "Pause"),
        Binding("s", "stop", "Stop"),
        Binding("f", "favorite", "Favorite"),
        Binding("plus,equals_sign", "volume_up", "Volume up"),
        Binding("minus,underscore", "volume_down", "Volume down"),
        Binding("m", "mute", "Mute"),
        Binding("t", "cycle_theme", "Theme"),
        Binding("w", "cycle_language", "Language"),
        Binding("e", "export", "Export"),
        Binding("i", "import_settings", "Import"),
        Binding("slash", "search", "Search"),
        Binding("question_mark", "help", "Help"),
        Binding("left", "previous_tab", "Previous tab", show=False),
        Binding("right", "next_tab", "Next tab", show=False),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        service: RadioService,
        themes: ThemeRepository,
        locales: LocaleRepository,
        settings: Settings | None = None,
    ) -> None:
        super().__init__()
        self._service = service
        self._themes = themes
        self._locales = locales
        self._settings = settings or get_settings()
        self._status_timer: Timer | None = None
        self.t: Translator = locales.translator(service.locale_code())
        self.apply_animations(service.animations)

    def compose(self) -> ComposeResult:
        """Build the home page, one tab per band and the auxiliary pages."""
        with TabbedContent(id="tabs"):
            with TabPane(self.t("tab.home"), id=HOME_TAB):
                yield HomePanel(self.t, id="home")
            for band in self._service.catalog.bands():
                with TabPane(
                    str(band),
                    id=self.band_tab(band),
                    classes="centered-table-page",
                ):
                    yield Static("", classes="table-action-spacer")
                    with Container(classes="centered-table-shell"):
                        yield StationTable(
                            self.t,
                            self._service.list_stations(band),
                            id=f"stations-{band.lower()}",
                            classes="main-station-table",
                        )
                    yield Static("", classes="table-action-footer-spacer")
            with TabPane(
                self.t("tab.favorites"),
                id=FAVORITES_TAB,
                classes="centered-table-page",
            ):
                yield Static("", classes="table-action-spacer")
                with Container(classes="centered-table-shell"):
                    yield StationTable(
                        self.t,
                        id="stations-favorites",
                        classes="main-station-table",
                    )
                yield Static("", classes="table-action-footer-spacer")
            with TabPane(
                self.t("tab.history"),
                id=HISTORY_TAB,
                classes="centered-table-page",
            ):
                yield Static("", classes="table-action-spacer")
                with Container(classes="centered-table-shell"):
                    yield HistoryTable(self.t, id="history")
                with Horizontal(id="history-actions"):
                    yield Button(
                        self.t("history.export"),
                        compact=True,
                        id="export-history",
                    )
                    yield Button(
                        self.t("history.clear"),
                        variant="error",
                        compact=True,
                        id="clear-history",
                    )
            with TabPane(self.t("tab.statistics"), id=STATISTICS_TAB):
                yield ListeningStatsPanel(self.t, id="statistics")
            with TabPane(self.t("tab.themes"), id=THEMES_TAB):
                yield ThemeGallery(self.t, id="themes")
            with TabPane(
                self.t("tab.settings"),
                id=SETTINGS_TAB,
                classes="centered-table-page",
            ):
                yield Static("", classes="table-action-spacer")
                with Container(classes="centered-table-shell"):
                    yield SettingsTable(self.t, id="settings")
                with Horizontal(id="settings-actions"):
                    yield Button(
                        self.t("settings.reset"),
                        variant="warning",
                        compact=True,
                        id="reset-settings",
                    )
            with TabPane(self.t("tab.about"), id=ABOUT_TAB):
                yield AboutPanel(self.t, id="about")
        yield NowPlayingBar(self.t, id="now-playing")
        yield KeyHintBar(self.t, id="hints")

    def on_mount(self) -> None:
        """Apply the theme, resume the last station and start the status timer."""
        register_themes(self, self._themes)
        self.theme = resolve_theme_name(self._themes, self._service.theme_name())

        self.refresh_favorites()
        self.refresh_stars()
        self._call_service(self._service.start_session)
        self.refresh_history()
        self.refresh_statistics()

        # Autoplay may have started a stream, but the run always opens on home.
        self.query_one(TabbedContent).active = HOME_TAB

        self.apply_breakpoint()
        self._status_timer = self.set_interval(
            self._settings.status_refresh_seconds, self.sync_status
        )

    def on_unmount(self) -> None:
        """Stop the timer and close the listening session when the UI goes away."""
        if self._status_timer is not None:
            self._status_timer.stop()
            self._status_timer = None
        self._service.end_session()

    @staticmethod
    def band_tab(band: Band) -> str:
        """Return the tab id carrying the stations of one band."""
        return f"tab-{band.lower()}"

    def on_resize(self, event: events.Resize) -> None:
        """Follow the terminal size with the layout classes and the word mark.

        The event carries the new size. Reading self.size here would still give
        the previous one, leaving the classes a resize behind.
        """
        self.apply_breakpoint(event.size.width)

    def apply_breakpoint(self, width: int | None = None) -> None:
        """Tag the screen with its size class and scale the word mark."""
        width = self.size.width if width is None else width
        self.screen.set_class(width < COMPACT_WIDTH, "-compact")
        self.screen.set_class(width >= WIDE_WIDTH, "-wide")

        scale = 2 if width >= WIDE_WIDTH else 1
        for logo in self.query(LogoBlock):
            logo.set_scale(scale)

    def sync_status(self) -> None:
        """Refresh the now playing bar, unless the UI is already tearing down."""
        bars = self.query(NowPlayingBar)
        if bars:
            bars.first().show(self._service.status())

    def on_data_table_row_selected(self, event: StationTable.RowSelected) -> None:
        """Act on the activated row of whichever table posted the event."""
        if isinstance(event.data_table, StationTable):
            self.play_selected_station()
        elif isinstance(event.data_table, SettingsTable):
            self.toggle_setting(event.data_table.selected_key)

    def on_list_view_selected(self, event: ThemeGallery.Selected) -> None:
        """Apply the theme of the activated card."""
        if isinstance(event.list_view, ThemeGallery):
            theme = event.list_view.selected_theme
            if theme is not None:
                self.apply_theme(theme.name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Open confirmation for actions represented by buttons."""
        if event.button.id == "clear-history":
            self.push_screen(
                ConfirmationScreen(self.t, self.t("confirm.clear_history")),
                self.finish_clear_history,
            )
        elif event.button.id == "export-history":
            self.action_export_history()
        elif event.button.id == "reset-settings":
            self.push_screen(
                ConfirmationScreen(self.t, self.t("confirm.reset_settings")),
                self.finish_reset_settings,
            )

    def on_now_playing_bar_playback_toggled(
        self, _event: NowPlayingBar.PlaybackToggled
    ) -> None:
        """Pause or resume when the bottom-left playback state is clicked."""
        self.action_pause()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Reload the tab that just came to the front and give it the focus."""
        reloaders = {
            HISTORY_TAB: self.refresh_history,
            STATISTICS_TAB: self.refresh_statistics,
            FAVORITES_TAB: self.refresh_favorites,
            THEMES_TAB: self.refresh_themes,
            SETTINGS_TAB: self.refresh_settings,
        }
        reloader = reloaders.get(event.pane.id or "")
        if reloader is not None:
            reloader()
        self.focus_pane_table(event.pane)
        if self._service.auto_health_check and not self.is_headless:
            stations = self.stations_for_pane(event.pane.id or "")
            if stations:
                self.begin_station_health_check(stations, force=False, announce=False)

    def refresh_favorites(self) -> None:
        """Reload the favorites tab from the starred stations."""
        table = self.query_one("#stations-favorites", StationTable)
        favorites = self._service.favorites()
        table.set_stations(favorites, frozenset(item.slug for item in favorites))

    def refresh_station_tables(self) -> None:
        """Reload every band table after the station library changes."""
        favorites = frozenset(item.slug for item in self._service.favorites())
        for band in self._service.catalog.bands():
            tables = self.query(f"#stations-{band.lower()}")
            if tables:
                tables.first().set_stations(
                    self._service.list_stations(band), favorites
                )

    def refresh_stars(self) -> None:
        """Redraw the favorite column of every station table."""
        favorites = {station.slug for station in self._service.favorites()}
        for table in self.query(StationTable):
            for slug in table.station_slugs():
                table.mark_favorite(slug, slug in favorites)

    def refresh_history(self) -> None:
        """Reload the listening totals of the history tab."""
        self.query_one(HistoryTable).show(self._service.summaries())

    def refresh_statistics(self) -> None:
        """Rebuild every listening chart from the complete history."""
        panels = self.query(ListeningStatsPanel)
        if panels:
            panels.first().show(self._service.listening_statistics())

    def refresh_themes(self) -> None:
        """Reload the theme gallery, marking the theme in use."""
        self.query_one(ThemeGallery).show(self._themes.all(), str(self.theme))

    def refresh_settings(self) -> None:
        """Reload the settings page from the service and the settings object."""
        settings = self._settings
        state = lambda flag: self.t("value.on" if flag else "value.off")  # noqa: E731
        env = lambda name: self.t("note.env", name=name)  # noqa: E731

        self.query_one(SettingsTable).show(
            (
                (
                    "autoplay",
                    self.t("settings.autoplay"),
                    state(self._service.autoplay),
                    self.t("note.toggle"),
                ),
                (
                    "reconnect",
                    self.t("settings.reconnect"),
                    state(self._service.auto_reconnect),
                    self.t("note.toggle"),
                ),
                (
                    "sleep_timer",
                    self.t("settings.sleep_timer"),
                    (
                        self.t("value.off")
                        if self._service.sleep_remaining_seconds() is None
                        else format_duration(
                            self._service.sleep_remaining_seconds() or 0
                        )
                    ),
                    self.t("note.sleep_timer"),
                ),
                (
                    "health_auto",
                    self.t("settings.health_auto"),
                    state(self._service.auto_health_check),
                    self.t("note.toggle"),
                ),
                (
                    "health_check_all",
                    self.t("settings.health_check_all"),
                    "",
                    self.t("note.health_check_all"),
                ),
                (
                    "custom_stations",
                    self.t("settings.custom_stations"),
                    str(len(self._service.custom_stations())),
                    self.t("note.custom_stations"),
                ),
                (
                    "shortcuts",
                    self.t("settings.shortcuts"),
                    "?",
                    self.t("note.shortcuts"),
                ),
                (
                    "language",
                    self.t("settings.language"),
                    self.t.locale.name,
                    self.t("note.language"),
                ),
                (
                    "theme",
                    self.t("settings.theme"),
                    str(self.theme),
                    self.t("note.theme"),
                ),
                (
                    "animations",
                    self.t("settings.animations"),
                    state(self._service.animations),
                    self.t("note.animations"),
                ),
                (
                    "volume",
                    self.t("settings.volume"),
                    f"{self._service.volume()}%",
                    self.t("note.volume", step=VOLUME_STEP),
                ),
                (
                    "export",
                    self.t("settings.export"),
                    "",
                    self.t("note.export"),
                ),
                (
                    "import",
                    self.t("settings.import"),
                    "",
                    self.t("note.import"),
                ),
                (
                    "refresh",
                    self.t("settings.refresh"),
                    f"{settings.status_refresh_seconds:g}s",
                    env("RADIO_STATUS_REFRESH_SECONDS"),
                ),
                (
                    "history_limit",
                    self.t("settings.history_limit"),
                    str(settings.history_limit),
                    env("RADIO_HISTORY_LIMIT"),
                ),
                (
                    "player",
                    self.t("settings.player"),
                    " ".join(settings.player_command),
                    env("RADIO_PLAYER_COMMAND"),
                ),
                (
                    "stations",
                    self.t("settings.stations_file"),
                    format_path(settings.stations_file),
                    env("RADIO_STATIONS_FILE"),
                ),
                (
                    "themes_file",
                    self.t("settings.themes_file"),
                    format_path(settings.themes_file),
                    env("RADIO_THEMES_FILE"),
                ),
                (
                    "locales_dir",
                    self.t("settings.locales_dir"),
                    format_path(settings.locales_dir),
                    env("RADIO_LOCALES_DIR"),
                ),
                (
                    "data_dir",
                    self.t("settings.data_dir"),
                    format_path(settings.data_dir),
                    env("RADIO_DATA_DIR"),
                ),
            )
        )

    def focus_pane_table(self, pane: TabPane | None = None) -> None:
        """Move the focus onto the table of the given pane, or of the active one."""
        pane = pane or self.query_one(TabbedContent).active_pane
        if pane is None:
            return

        for widget_type in (
            StationTable,
            HistoryTable,
            ListeningStatsPanel,
            ThemeGallery,
            SettingsTable,
            AboutPanel,
            HomePanel,
        ):
            widgets = pane.query(widget_type)
            if widgets:
                widgets.first().focus()
                return

    def apply_animations(self, enabled: bool) -> None:
        """Turn Textual transitions on or off."""
        self.animation_level = "full" if enabled else "none"

    def apply_theme(self, name: str) -> None:
        """Apply a theme, remember it and redraw the pages that display it."""
        self.theme = name
        self._service.remember_theme(name)
        self.refresh_themes()
        self.refresh_settings()
        self.notify(self.t("notify.theme", name=name), timeout=2)

    def apply_locale(self, code: str, *, announce: bool = True) -> None:
        """Switch the interface language and redraw everything that carries text."""
        self.t = self._locales.translator(code)
        self._service.remember_locale(self.t.code)

        tabs = self.query_one(TabbedContent)
        for pane_id, key in TAB_LABELS.items():
            tabs.get_tab(pane_id).label = self.t(key)

        for widget in self.query(
            "HomePanel, AboutPanel, StationTable, HistoryTable, ListeningStatsPanel, "
            "SettingsTable, ThemeGallery, NowPlayingBar, KeyHintBar"
        ):
            retranslate = getattr(widget, "retranslate", None)
            if retranslate is not None:
                retranslate(self.t)

        self.query_one("#clear-history", Button).label = self.t("history.clear")
        self.query_one("#export-history", Button).label = self.t("history.export")
        self.query_one("#reset-settings", Button).label = self.t("settings.reset")

        self.refresh_themes()
        self.refresh_settings()
        self.refresh_stars()
        if announce:
            self.notify(self.t("notify.language", name=self.t.locale.name), timeout=2)

    def finish_clear_history(self, confirmed: bool) -> None:
        """Clear persisted listening events after explicit confirmation."""
        if not confirmed:
            return

        if not self._service.clear_history():
            self.notify(
                self.t("notify.history_clear_failed"), severity="error", timeout=4
            )
            return

        self.refresh_history()
        self.notify(self.t("notify.history_cleared"), timeout=2)

    def finish_reset_settings(self, confirmed: bool) -> None:
        """Restore app defaults after explicit confirmation."""
        if not confirmed:
            return

        restored = self._service.reset_settings(
            autoplay=self._settings.autoplay_last_station,
            animations=self._settings.enable_animations,
            auto_reconnect=self._settings.auto_reconnect,
            auto_health_check=self._settings.auto_health_check,
            locale=self._locales.default_code,
            theme_name=self._themes.default_name,
        )
        self.apply_animations(self._service.animations)
        self.theme = resolve_theme_name(self._themes, restored.theme_name)
        self.apply_locale(restored.locale or self._locales.default_code, announce=False)
        self.sync_status()
        self.refresh_settings()
        self.notify(self.t("notify.settings_reset"), timeout=2)

    def toggle_setting(self, key: str | None) -> None:
        """Flip the setting of the given row, when it is an editable one."""
        if key == "autoplay":
            enabled = self._service.set_autoplay(not self._service.autoplay)
            self.refresh_settings()
            self.notify(
                self.t("notify.autoplay", state=self.t(f"value.{'on' if enabled else 'off'}")),
                timeout=2,
            )
        elif key == "animations":
            enabled = self._service.set_animations(not self._service.animations)
            self.apply_animations(enabled)
            self.refresh_settings()
            self.notify(
                self.t(
                    "notify.animations",
                    state=self.t(f"value.{'on' if enabled else 'off'}"),
                ),
                timeout=2,
            )
        elif key == "reconnect":
            enabled = self._service.set_auto_reconnect(
                not self._service.auto_reconnect
            )
            self.refresh_settings()
            self.notify(
                self.t(
                    "notify.reconnect",
                    state=self.t(f"value.{'on' if enabled else 'off'}"),
                ),
                timeout=2,
            )
        elif key == "sleep_timer":
            self.push_screen(
                SleepTimerScreen(self.t, self._service.sleep_remaining_seconds()),
                self.finish_sleep_timer,
            )
        elif key == "health_auto":
            enabled = self._service.set_auto_health_check(
                not self._service.auto_health_check
            )
            self.refresh_settings()
            self.notify(
                self.t(
                    "notify.health_auto",
                    state=self.t(f"value.{'on' if enabled else 'off'}"),
                ),
                timeout=2,
            )
        elif key == "health_check_all":
            self.begin_station_health_check(
                self._service.list_stations(), force=True, announce=True
            )
        elif key == "custom_stations":
            self.open_custom_station_manager()
        elif key == "shortcuts":
            self.action_help()
        elif key == "theme":
            self.action_cycle_theme()
        elif key == "language":
            self.action_cycle_language()
        elif key == "export":
            self.action_export()
        elif key == "import":
            self.action_import_settings()

    def finish_sleep_timer(self, choice: int | str | None) -> None:
        """Apply the sleep picker result and refresh both status surfaces."""
        if choice is None:
            return
        minutes = None if choice == "off" else int(choice)
        self._call_service(lambda: self._service.set_sleep_timer(minutes))
        self.refresh_settings()
        key = "notify.sleep_off" if minutes is None else "notify.sleep_set"
        values = {} if minutes is None else {"minutes": minutes}
        self.notify(self.t(key, **values), timeout=2)

    def stations_for_pane(self, pane_id: str) -> tuple[Station, ...]:
        """Return stations visible in one station-bearing tab."""
        if pane_id == FAVORITES_TAB:
            return self._service.favorites()
        for band in Band:
            if pane_id == self.band_tab(band):
                return self._service.list_stations(band)
        return ()

    def begin_station_health_check(
        self,
        stations: tuple[Station, ...],
        *,
        force: bool,
        announce: bool,
    ) -> None:
        """Mark a station batch as checking and start a background worker."""
        if not stations:
            if announce:
                self.notify(self.t("notify.health_empty"), timeout=2)
            return
        for item in stations:
            self.set_station_health(item.slug, StationHealth.CHECKING)
        if announce:
            self.notify(self.t("notify.health_started"), timeout=2)
        self.run_station_health_checks(stations, force, announce)

    @work(
        thread=True,
        group="station-health",
        exclusive=True,
        exit_on_error=False,
    )
    def run_station_health_checks(
        self,
        stations: tuple[Station, ...],
        force: bool,
        announce: bool,
    ) -> None:
        """Probe streams off the event loop and return snapshots safely."""
        results = self._service.check_station_health(stations, force=force)
        try:
            self.call_from_thread(
                self.finish_station_health_check, results, announce
            )
        except RuntimeError:
            return

    def finish_station_health_check(
        self,
        results: tuple[StationHealthSnapshot, ...],
        announce: bool,
    ) -> None:
        """Render completed health results and optionally summarize them."""
        counts = {health: 0 for health in StationHealth}
        for result in results:
            self.set_station_health(result.station_slug, result.health)
            counts[result.health] += 1
        if announce:
            self.notify(
                self.t(
                    "notify.health_complete",
                    online=counts[StationHealth.ONLINE],
                    slow=counts[StationHealth.SLOW],
                    offline=counts[StationHealth.OFFLINE],
                ),
                timeout=4,
            )

    def set_station_health(self, slug: str, health: StationHealth) -> None:
        """Apply one health glyph to every table containing the station."""
        for table in self.query(StationTable):
            table.set_health(slug, health)

    def open_custom_station_manager(self) -> None:
        """Open the manager with the latest local station collection."""
        self.push_screen(
            CustomStationManagerScreen(self.t, self._service.custom_stations()),
            self.finish_custom_station_manager,
        )

    def finish_custom_station_manager(
        self, result: tuple[str, str | None] | None
    ) -> None:
        """Continue the selected add, edit, or delete flow."""
        if result is None:
            return
        action, slug = result
        if action == "add":
            self.push_screen(
                CustomStationFormScreen(self.t),
                lambda station: self.finish_custom_station_form(None, station),
            )
        elif action == "edit" and slug is not None:
            self.push_screen(
                CustomStationFormScreen(self.t, self._service.get_station(slug)),
                lambda station: self.finish_custom_station_form(slug, station),
            )
        elif action == "delete" and slug is not None:
            self.push_screen(
                ConfirmationScreen(self.t, self.t("confirm.delete_station")),
                lambda confirmed: self.finish_delete_custom_station(slug, confirmed),
            )

    def finish_custom_station_form(
        self,
        editing_slug: str | None,
        station: Station | None,
    ) -> None:
        """Persist a validated form and refresh every station surface."""
        if station is None:
            self.open_custom_station_manager()
            return
        try:
            if editing_slug is None:
                saved = self._service.add_custom_station(
                    name=station.name,
                    band=station.band,
                    frequency=station.frequency,
                    url=station.url,
                    description=station.description,
                )
                key = "notify.custom_added"
            else:
                saved = self._service.update_custom_station(
                    editing_slug,
                    name=station.name,
                    band=station.band,
                    frequency=station.frequency,
                    url=station.url,
                    description=station.description,
                )
                key = "notify.custom_updated"
        except RadioError as error:
            self.notify(str(error), title=self.TITLE, severity="error")
            self.open_custom_station_manager()
            return
        self.refresh_after_station_change()
        self.notify(self.t(key, name=saved.name), timeout=2)
        self.open_custom_station_manager()

    def finish_delete_custom_station(self, slug: str, confirmed: bool) -> None:
        """Delete a custom station after centered confirmation."""
        if not confirmed:
            self.open_custom_station_manager()
            return
        try:
            removed = self._service.delete_custom_station(slug)
        except RadioError as error:
            self.notify(str(error), title=self.TITLE, severity="error")
            self.open_custom_station_manager()
            return
        self.refresh_after_station_change()
        self.notify(self.t("notify.custom_deleted", name=removed.name), timeout=2)
        self.open_custom_station_manager()

    def refresh_after_station_change(self) -> None:
        """Refresh every page backed by the merged station catalog."""
        self.refresh_station_tables()
        self.refresh_favorites()
        self.refresh_stars()
        self.refresh_settings()

    def action_activate(self) -> None:
        """Act on the highlighted row of the focused page."""
        focused = self.focused
        if isinstance(focused, ThemeGallery):
            theme = focused.selected_theme
            if theme is not None:
                self.apply_theme(theme.name)
        elif isinstance(focused, SettingsTable):
            self.toggle_setting(focused.selected_key)
        else:
            self.play_selected_station()

    def play_selected_station(self) -> None:
        """Play the highlighted station, resuming it when it is only paused."""
        station = self.current_station()
        if station is None:
            return

        status = self._service.status()
        if status.station is not None and status.station.slug == station.slug:
            if status.is_paused:
                self._call_service(self._service.resume)
                return
            if status.is_playing:
                return

        self._call_service(lambda: self._service.play(station.slug))

    def action_pause(self) -> None:
        """Pause a playing stream or resume a paused one."""
        self._call_service(self._service.toggle_pause)

    def action_stop(self) -> None:
        """Stop playback and refresh the totals it just closed."""
        self._call_service(self._service.stop)
        self.refresh_history()

    def action_favorite(self) -> None:
        """Star or unstar the highlighted station."""
        station = self.current_station()
        if station is None:
            return

        self._service.toggle_favorite(station.slug)
        self.refresh_favorites()
        self.refresh_stars()
        key = (
            "notify.favorite_added"
            if self._service.is_favorite(station.slug)
            else "notify.favorite_removed"
        )
        self.notify(self.t(key, name=station.name), timeout=2)

    def action_volume_up(self) -> None:
        """Raise the output volume."""
        self._call_service(lambda: self._service.adjust_volume(VOLUME_STEP))
        self.refresh_settings()

    def action_volume_down(self) -> None:
        """Lower the output volume."""
        self._call_service(lambda: self._service.adjust_volume(-VOLUME_STEP))
        self.refresh_settings()

    def action_mute(self) -> None:
        """Mute or unmute the output."""
        self._call_service(self._service.toggle_mute)

    def action_cycle_theme(self) -> None:
        """Switch to the next theme of the theme file."""
        self.apply_theme(self._themes.next_after(str(self.theme)).name)

    def action_cycle_language(self) -> None:
        """Switch to the next interface language."""
        self.apply_locale(self._locales.next_after(self.t.code).code)

    def action_quit(self) -> None:
        """Show the farewell screen, which exits once it has been seen."""
        if isinstance(self.screen, GoodbyeScreen):
            return

        self.push_screen(
            GoodbyeScreen(
                self.t,
                self._service.session_listened_seconds(),
                self._settings.goodbye_seconds,
            )
        )

    def action_export(self) -> None:
        """Ask where the settings should be written, then write them there."""
        self.push_screen(
            ExportScreen(self.t, self.export_destinations()), self.finish_export
        )

    def action_export_history(self) -> None:
        """Ask for a destination for a localized listening-history CSV."""
        filename = history_csv_filename()
        self.push_screen(
            ExportScreen(
                self.t,
                self.export_destinations(),
                filename=filename,
                title_key="history.export_title",
            ),
            lambda directory: self.finish_history_export(directory, filename),
        )

    def finish_history_export(
        self, directory: Path | None, filename: str
    ) -> None:
        """Write the history using column names from the active language."""
        if directory is None:
            return
        headers = (
            self.t("column.dial"),
            self.t("column.station"),
            self.t("column.plays"),
            self.t("column.listened"),
            self.t("column.paused"),
            self.t("column.last_played"),
        )
        try:
            target = write_history_csv(
                directory,
                self._service.all_summaries(),
                headers,
                filename=filename,
            )
        except RadioError as error:
            self.notify(str(error), title=self.TITLE, severity="error")
            return
        self.notify(self.t("notify.history_exported", path=format_path(target)), timeout=4)

    def action_import_settings(self) -> None:
        """Ask which exported file to load, then adopt what it holds."""
        directories = tuple(path for _, path in self.export_destinations())
        self.push_screen(
            ImportScreen(self.t, find_config_files(directories)), self.finish_import
        )

    def action_search(self) -> None:
        """Open global station search."""
        self.push_screen(
            StationSearchScreen(
                self.t,
                self._service.search_stations,
                frozenset(item.slug for item in self._service.favorites()),
                lambda slug: self._service.station_health(slug).health,
            ),
            self.finish_station_search,
        )

    def action_help(self) -> None:
        """Open the localized keyboard shortcut reference."""
        self.push_screen(ShortcutHelpScreen(self.t))

    def finish_station_search(self, slug: str | None) -> None:
        """Play the station selected by global search."""
        if slug is not None:
            self._call_service(lambda: self._service.play(slug))

    def finish_import(self, path: Path | None) -> None:
        """Adopt the preferences of the chosen file and redraw every page."""
        if path is None:
            return

        try:
            imported = read_export(path)
            adopted = self._service.apply_import(
                imported.preferences, imported.custom_stations
            )
        except RadioError as error:
            self.notify(str(error), title=self.TITLE, severity="error")
            return

        self.apply_animations(self._service.animations)
        self.theme = resolve_theme_name(self._themes, adopted.theme_name)
        self.apply_locale(self._locales.translator(adopted.locale).code)

        self.refresh_station_tables()
        self.refresh_favorites()
        self.refresh_stars()
        self.refresh_themes()
        self.refresh_settings()
        self.notify(self.t("notify.imported", name=path.name), timeout=4)

    def export_destinations(self) -> tuple[tuple[str, Path], ...]:
        """Return the folders offered by the export picker, keeping those that exist."""
        home = Path.home()
        candidates = (
            ("export.desktop", home / "Desktop"),
            ("export.documents", home / "Documents"),
            ("export.downloads", home / "Downloads"),
            ("export.home", home),
            ("export.project", self._settings.stations_file.parent),
            ("export.data", self._settings.data_dir),
        )
        return tuple((key, path) for key, path in candidates if path.is_dir())

    def finish_export(self, directory: Path | None) -> None:
        """Write the export into the chosen folder, if the user picked one."""
        if directory is None:
            return

        try:
            target = write_export(
                directory,
                self._settings,
                self._service.preferences(),
                self._service.custom_stations(),
            )
        except RadioError as error:
            self.notify(str(error), title=self.TITLE, severity="error")
            return

        self.notify(self.t("notify.exported", path=format_path(target)), timeout=4)

    def action_previous_tab(self) -> None:
        """Show the tab on the left of the active one."""
        self.step_tab(-1)

    def action_next_tab(self) -> None:
        """Show the tab on the right of the active one."""
        self.step_tab(1)

    def step_tab(self, offset: int) -> None:
        """Move the active tab by the given offset, wrapping around."""
        tabs = self.query_one(TabbedContent)
        panes = [pane.id for pane in tabs.query(TabPane) if pane.id]
        if not panes:
            return

        index = panes.index(tabs.active) if tabs.active in panes else 0
        tabs.active = panes[(index + offset) % len(panes)]

    def current_station(self) -> Station | None:
        """Return the station highlighted in the active tab."""
        if isinstance(self.focused, StationTable):
            return self.focused.selected_station

        pane = self.query_one(TabbedContent).active_pane
        if pane is None:
            return None

        tables = pane.query(StationTable)
        return tables.first().selected_station if tables else None

    def _call_service(self, operation: Callable[[], object]) -> None:
        """Run a service call, surfacing domain errors as notifications."""
        try:
            operation()
        except RadioError as error:
            self.notify(str(error), title=self.TITLE, severity="error")
        finally:
            self.sync_status()


def run() -> None:
    """Entry point building the services and starting the terminal UI."""
    settings = get_settings()
    RadioApp(
        service=build_radio_service(settings),
        themes=ThemeRepository.from_file(settings.themes_file),
        locales=LocaleRepository.from_directory(settings.locales_dir, settings.locale),
        settings=settings,
    ).run()

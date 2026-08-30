"""Textual application driving the radio from the terminal."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.timer import Timer
from textual.widgets import Button, Static, TabbedContent, TabPane

from app.core.config import Settings, get_settings
from app.core.exceptions import RadioError
from app.core.i18n import LocaleRepository, Translator
from app.enums import Band
from app.models import Station
from app.services import (
    RadioService,
    ThemeRepository,
    build_radio_service,
    find_config_files,
    read_preferences,
    write_export,
)
from app.tui.formatting import format_path
from app.tui.screens import (
    ConfirmationScreen,
    ExportScreen,
    GoodbyeScreen,
    ImportScreen,
)
from app.tui.theming import register_themes, resolve_theme_name
from app.tui.widgets import (
    AboutPanel,
    HistoryTable,
    HomePanel,
    KeyHintBar,
    LogoBlock,
    NowPlayingBar,
    SettingsTable,
    StationTable,
    ThemeGallery,
)

HOME_TAB = "tab-home"
FAVORITES_TAB = "tab-favorites"
HISTORY_TAB = "tab-history"
THEMES_TAB = "tab-themes"
SETTINGS_TAB = "tab-settings"
ABOUT_TAB = "tab-about"
VOLUME_STEP = 5

# Column layouts and the size of the word mark follow these terminal widths.
COMPACT_WIDTH = 90
WIDE_WIDTH = 150

# Band tabs keep their own name, every other tab is translated.
TAB_LABELS = {
    HOME_TAB: "tab.home",
    FAVORITES_TAB: "tab.favorites",
    HISTORY_TAB: "tab.history",
    THEMES_TAB: "tab.themes",
    SETTINGS_TAB: "tab.settings",
    ABOUT_TAB: "tab.about",
}


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
                with TabPane(str(band), id=self.band_tab(band)):
                    yield StationTable(
                        self.t,
                        self._service.list_stations(band),
                        id=f"stations-{band.lower()}",
                    )
            with TabPane(self.t("tab.favorites"), id=FAVORITES_TAB):
                yield StationTable(self.t, id="stations-favorites")
            with TabPane(self.t("tab.history"), id=HISTORY_TAB):
                yield Static("", classes="table-action-spacer")
                with Container(classes="centered-table-shell"):
                    yield HistoryTable(self.t, id="history")
                with Horizontal(id="history-actions"):
                    yield Button(
                        self.t("history.clear"),
                        variant="error",
                        compact=True,
                        id="clear-history",
                    )
            with TabPane(self.t("tab.themes"), id=THEMES_TAB):
                yield ThemeGallery(self.t, id="themes")
            with TabPane(self.t("tab.settings"), id=SETTINGS_TAB):
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
            FAVORITES_TAB: self.refresh_favorites,
            THEMES_TAB: self.refresh_themes,
            SETTINGS_TAB: self.refresh_settings,
        }
        reloader = reloaders.get(event.pane.id or "")
        if reloader is not None:
            reloader()
        self.focus_pane_table(event.pane)

    def refresh_favorites(self) -> None:
        """Reload the favorites tab from the starred stations."""
        table = self.query_one("#stations-favorites", StationTable)
        favorites = self._service.favorites()
        table.set_stations(favorites, frozenset(item.slug for item in favorites))

    def refresh_stars(self) -> None:
        """Redraw the favorite column of every station table."""
        favorites = {station.slug for station in self._service.favorites()}
        for table in self.query(StationTable):
            for slug in table.station_slugs():
                table.mark_favorite(slug, slug in favorites)

    def refresh_history(self) -> None:
        """Reload the listening totals of the history tab."""
        self.query_one(HistoryTable).show(self._service.summaries())

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
            "HomePanel, AboutPanel, StationTable, HistoryTable, SettingsTable, "
            "ThemeGallery, NowPlayingBar, KeyHintBar"
        ):
            retranslate = getattr(widget, "retranslate", None)
            if retranslate is not None:
                retranslate(self.t)

        self.query_one("#clear-history", Button).label = self.t("history.clear")
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
        elif key == "theme":
            self.action_cycle_theme()
        elif key == "language":
            self.action_cycle_language()
        elif key == "export":
            self.action_export()
        elif key == "import":
            self.action_import_settings()

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

    def action_import_settings(self) -> None:
        """Ask which exported file to load, then adopt what it holds."""
        directories = tuple(path for _, path in self.export_destinations())
        self.push_screen(
            ImportScreen(self.t, find_config_files(directories)), self.finish_import
        )

    def finish_import(self, path: Path | None) -> None:
        """Adopt the preferences of the chosen file and redraw every page."""
        if path is None:
            return

        try:
            adopted = self._service.apply_preferences(read_preferences(path))
        except RadioError as error:
            self.notify(str(error), title=self.TITLE, severity="error")
            return

        self.apply_animations(self._service.animations)
        self.theme = resolve_theme_name(self._themes, adopted.theme_name)
        self.apply_locale(self._locales.translator(adopted.locale).code)

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
            target = write_export(directory, self._settings, self._service.preferences())
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

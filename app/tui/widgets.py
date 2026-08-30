"""Reusable widgets of the terminal UI."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import DataTable, ListItem, ListView, Static

from app.core import about
from app.core.i18n import Translator
from app.models import PlaybackState, PlayerStatus, Station, Theme
from app.services import StationSummary
from app.tui.formatting import (
    format_clock,
    format_duration,
    format_timestamp,
    format_volume,
    truncate,
)

EMPTY = "—"
STAR = "★"
DEVICE_NAME_LIMIT = 15
STATE_GLYPHS = {
    PlaybackState.PLAYING: "▶",
    PlaybackState.PAUSED: "⏸",
    PlaybackState.STOPPED: "■",
}
STATE_KEYS = {
    PlaybackState.PLAYING: "player.playing",
    PlaybackState.PAUSED: "player.paused",
    PlaybackState.STOPPED: "player.stopped",
}

LOGO = (
    "██████   █████  ██████  ██  ██████ ",
    "██   ██ ██   ██ ██   ██ ██ ██    ██",
    "██████  ███████ ██   ██ ██ ██    ██",
    "██   ██ ██   ██ ██   ██ ██ ██    ██",
    "██   ██ ██   ██ ██████  ██  ██████ ",
)

def scale_ascii(lines: tuple[str, ...], factor: int) -> tuple[str, ...]:
    """Return the art enlarged by repeating each cell and each row."""
    if factor <= 1:
        return lines

    scaled: list[str] = []
    for line in lines:
        stretched = "".join(character * factor for character in line)
        scaled.extend([stretched] * factor)
    return tuple(scaled)


TAB_NAVIGATION = [
    Binding("left", "app.previous_tab", "Prev tab", show=False),
    Binding("right", "app.next_tab", "Next tab", show=False),
    Binding("k", "cursor_up", "Up", show=False),
    Binding("j", "cursor_down", "Down", show=False),
]

# Scrolling pages have no cursor, so the vim keys move the viewport instead.
PAGE_NAVIGATION = [
    Binding("left", "app.previous_tab", "Prev tab", show=False),
    Binding("right", "app.next_tab", "Next tab", show=False),
    Binding("k", "scroll_up", "Up", show=False),
    Binding("j", "scroll_down", "Down", show=False),
]


class NavigableTable(DataTable[str]):
    """Table that leaves the left and right keys to the tab bar."""

    BINDINGS = TAB_NAVIGATION

    def __init__(self, translator: Translator, **kwargs: object) -> None:
        super().__init__(cursor_type="row", zebra_stripes=True, **kwargs)
        self.t = translator
        self._laid_out_width = 0

    def retranslate(self, translator: Translator) -> None:
        """Rebuild the header row in the new language, keeping the data."""
        self.t = translator

    def on_resize(self) -> None:
        """Lay the columns out again when the terminal changes width."""
        if self.size.width and self.size.width != self._laid_out_width:
            self._laid_out_width = self.size.width
            self.retranslate(self.t)

    def scaled(self, fraction: float, smallest: int, largest: int) -> int:
        """Return a column width proportional to the table, within bounds."""
        width = self.size.width or largest
        return max(smallest, min(largest, int(width * fraction)))

    @property
    def scrolls_sideways_only(self) -> bool:
        """Return whether the rows fit but the columns run past the right edge."""
        return self.max_scroll_y == 0 and self.max_scroll_x > 0

    def _on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        """Send a wheel step to the right when only the columns overflow."""
        if self.scrolls_sideways_only:
            self.scroll_right(animate=False)
            event.stop()

    def _on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        """Send a wheel step to the left when only the columns overflow."""
        if self.scrolls_sideways_only:
            self.scroll_left(animate=False)
            event.stop()


class StationTable(NavigableTable):
    """Table listing stations, with a column marking the favorites."""

    def __init__(
        self,
        translator: Translator,
        stations: tuple[Station, ...] = (),
        **kwargs: object,
    ) -> None:
        super().__init__(translator, **kwargs)
        self._stations: dict[str, Station] = {}
        self._favorites: frozenset[str] = frozenset()
        self._pending = stations

    def on_mount(self) -> None:
        """Declare the columns and load the initial rows."""
        self._add_columns()
        self.set_stations(self._pending)

    def _add_columns(self) -> None:
        """Add the header row in the current language."""
        self.add_column(STAR, width=3, key="favorite")
        self.add_column(self.t("column.dial"), width=10, key="dial")
        self.add_column(
            self.t("column.station"), width=self.scaled(0.34, 18, 52), key="station"
        )
        self.add_column(self.t("column.info"), key="info")

    def retranslate(self, translator: Translator) -> None:
        """Rebuild the header row in the new language, keeping the rows."""
        super().retranslate(translator)
        stations = tuple(self._stations.values())
        self.clear(columns=True)
        self._add_columns()
        self.set_stations(stations, self._favorites)

    @property
    def selected_station(self) -> Station | None:
        """Return the station under the cursor, if any."""
        if not self.is_mounted or self.row_count == 0:
            return None
        row_key, _ = self.coordinate_to_cell_key(self.cursor_coordinate)
        return self._stations.get(str(row_key.value))

    def set_stations(
        self, stations: tuple[Station, ...], favorites: frozenset[str] = frozenset()
    ) -> None:
        """Replace every row with the given stations."""
        self.clear()
        self._stations = {station.slug: station for station in stations}
        self._favorites = favorites
        for station in stations:
            self.add_row(
                STAR if station.slug in favorites else "",
                station.dial,
                station.name,
                station.description or "",
                key=station.slug,
            )

    def station_slugs(self) -> tuple[str, ...]:
        """Return the slug of every row, in display order."""
        return tuple(self._stations)

    def mark_favorite(self, slug: str, favorite: bool) -> None:
        """Update the star of one row without rebuilding the table."""
        if slug not in self._stations:
            return

        self._favorites = (
            self._favorites | {slug} if favorite else self._favorites - {slug}
        )
        self.update_cell(slug, "favorite", STAR if favorite else "")

    def focus_station(self, slug: str) -> None:
        """Move the cursor onto the given station when it belongs to this table."""
        if slug in self._stations:
            self.move_cursor(row=self.get_row_index(slug))


class HistoryTable(NavigableTable):
    """Table listing how long each station was listened to."""

    def __init__(self, translator: Translator, **kwargs: object) -> None:
        super().__init__(translator, **kwargs)
        self._summaries: tuple[StationSummary, ...] = ()

    def on_mount(self) -> None:
        """Declare the columns once the widget joins the screen."""
        self._add_columns()

    def _add_columns(self) -> None:
        """Add the header row in the current language."""
        self.add_column(self.t("column.dial"), width=10)
        self.add_column(self.t("column.station"), width=self.scaled(0.30, 16, 46))
        self.add_column(self.t("column.plays"), width=8)
        self.add_column(self.t("column.listened"), width=12)
        self.add_column(self.t("column.paused"), width=12)
        self.add_column(self.t("column.last_played"))

    def retranslate(self, translator: Translator) -> None:
        """Rebuild the header row in the new language, keeping the rows."""
        super().retranslate(translator)
        self.clear(columns=True)
        self._add_columns()
        self.show(self._summaries)

    def show(self, summaries: tuple[StationSummary, ...]) -> None:
        """Replace the rows with the given listening totals."""
        self.clear()
        self._summaries = summaries
        for summary in summaries:
            self.add_row(
                summary.station_dial or EMPTY,
                summary.station_name,
                str(summary.play_count),
                format_clock(summary.listened_seconds),
                format_clock(summary.paused_seconds),
                format_timestamp(summary.last_played_at),
                key=summary.station_slug,
            )


class SettingsTable(NavigableTable):
    """Table of preferences, where the editable rows are toggled with enter."""

    def __init__(self, translator: Translator, **kwargs: object) -> None:
        super().__init__(translator, **kwargs)
        self._rows: tuple[tuple[str, str, str, str], ...] = ()

    def on_mount(self) -> None:
        """Declare the columns once the widget joins the screen."""
        self._add_columns()

    def _add_columns(self) -> None:
        """Add the header row in the current language."""
        self.add_column(self.t("column.setting"), width=self.scaled(0.16, 12, 24), key="name")
        self.add_column(self.t("column.value"), width=self.scaled(0.36, 24, 62), key="value")
        self.add_column(self.t("column.note"), key="note")

    def retranslate(self, translator: Translator) -> None:
        """Rebuild the header row in the new language, keeping the rows."""
        super().retranslate(translator)
        self.clear(columns=True)
        self._add_columns()
        self.show(self._rows)

    def show(self, rows: tuple[tuple[str, str, str, str], ...]) -> None:
        """Replace the rows with the given key, name, value and note tuples."""
        selected = self.selected_key
        self.clear()
        self._rows = rows
        for key, name, value, note in rows:
            self.add_row(name, value, note, key=key)
        keys = [key for key, *_ in rows]
        if selected in keys:
            self.move_cursor(row=keys.index(selected))

    @property
    def selected_key(self) -> str | None:
        """Return the key of the row under the cursor, if any."""
        if not self.is_mounted or self.row_count == 0:
            return None
        row_key, _ = self.coordinate_to_cell_key(self.cursor_coordinate)
        return str(row_key.value)


class ThemeCard(ListItem):
    """One row of the theme gallery, painted with the theme it previews."""

    SWATCHES = ("primary", "secondary", "accent", "success", "warning", "error")

    def __init__(self, theme: Theme, active: bool, translator: Translator) -> None:
        super().__init__()
        self.theme_model = theme
        self._active = active
        self.t = translator

    def compose(self) -> ComposeResult:
        """Show the theme name and a swatch per color, painted as the theme is.

        The colors are set on the widgets while they are built. Doing it from
        on_mount would run before the children of the item exist.
        """
        theme = self.theme_model
        if theme.background:
            self.styles.background = theme.background

        marker = "●" if self._active else " "
        mode = self.t("theme.dark" if theme.dark else "theme.light")
        name = Static(f"{marker} {theme.name}  ({mode})", classes="theme-name")
        if theme.foreground:
            name.styles.color = theme.foreground
        yield name

        with Horizontal(classes="theme-swatches"):
            for token in self.SWATCHES:
                swatch = Static(token[:3].upper(), classes=f"swatch swatch-{token}")
                swatch.styles.background = getattr(theme, token, None) or theme.primary
                swatch.styles.color = theme.background or "black"
                yield swatch


class ThemeGallery(ListView):
    """Scrollable preview of every theme defined in the theme file."""

    BINDINGS = TAB_NAVIGATION

    def __init__(self, translator: Translator, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.t = translator

    def retranslate(self, translator: Translator) -> None:
        """Store the new language, the caller redraws the cards."""
        self.t = translator

    def show(self, themes: tuple[Theme, ...], active: str) -> None:
        """Rebuild the gallery, marking and highlighting the theme in use."""
        self.clear()
        for theme in themes:
            self.append(ThemeCard(theme, theme.name == active, self.t))

        names = [theme.name for theme in themes]
        if active in names:
            self.index = names.index(active)

    @property
    def selected_theme(self) -> Theme | None:
        """Return the theme under the cursor, if any."""
        item = self.highlighted_child
        return item.theme_model if isinstance(item, ThemeCard) else None


class LogoBlock(Vertical):
    """The word mark, drawn at a scale the caller chooses."""

    def __init__(self, scale: int = 1, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._scale = scale

    def compose(self) -> ComposeResult:
        """Draw one static per line of the scaled art."""
        for line in scale_ascii(LOGO, self._scale):
            yield Static(line, classes="logo-line")

    def set_scale(self, scale: int) -> None:
        """Redraw the mark at a new scale, when it actually changed."""
        if scale != self._scale:
            self._scale = scale
            self.refresh(recompose=True)


class HomePanel(VerticalScroll):
    """Landing page carrying the centred logo and the tagline."""

    BINDINGS = PAGE_NAVIGATION

    def __init__(self, translator: Translator, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.t = translator

    def compose(self) -> ComposeResult:
        """Lay out the logo, the tagline and the hint."""
        yield LogoBlock(id="home-logo")
        yield Static("", id="home-tagline")
        yield Static("", id="home-hint")

    def on_mount(self) -> None:
        """Draw the text once the widget joins the screen."""
        self._render_text()

    def retranslate(self, translator: Translator) -> None:
        """Redraw every line in the new language."""
        self.t = translator
        if self.is_mounted:
            self._render_text()

    def _render_text(self) -> None:
        """Write the tagline and the hint."""
        self.query_one("#home-tagline", Static).update(self.t("home.tagline"))
        self.query_one("#home-hint", Static).update(self.t("home.hint"))


class AboutPanel(VerticalScroll):
    """Page naming the project, its version and what it builds on.

    It scrolls, because the credits run past a short terminal once the word mark
    is drawn at the larger size.
    """

    BINDINGS = PAGE_NAVIGATION

    def __init__(self, translator: Translator, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.t = translator

    def compose(self) -> ComposeResult:
        """Lay out the logo, the identity block and the credits."""
        yield LogoBlock(id="about-logo")
        yield Static(f"{about.PACKAGE.upper()}  {about.get_version()}", id="about-title")
        yield Static("", id="about-summary")
        yield Static(about.copyright_line(), id="about-copyright")
        yield Static("", id="about-home")
        yield Static("", classes="about-heading", id="about-heading")
        for name, key in about.CREDITS:
            yield Static("", classes="about-credit", id=f"credit-{key.split('.')[1]}")

    def on_mount(self) -> None:
        """Draw the translated lines once the widget joins the screen."""
        self._render_text()

    def retranslate(self, translator: Translator) -> None:
        """Redraw the translated lines in the new language."""
        self.t = translator
        if self.is_mounted:
            self._render_text()

    def _render_text(self) -> None:
        """Write every translated line of the page."""
        self.query_one("#about-summary", Static).update(self.t("about.summary"))
        self.query_one("#about-home", Static).update(
            f"{self.t('about.homepage')}  {about.HOMEPAGE}"
        )
        self.query_one("#about-heading", Static).update(self.t("about.built_with"))
        for name, key in about.CREDITS:
            widget = self.query_one(f"#credit-{key.split('.')[1]}", Static)
            widget.update(f"{name}  ·  {self.t(key)}")


class NowPlayingBar(Vertical):
    """Bottom bar showing the station, the program, the timer and the volume."""

    class PlaybackToggled(Message):
        """The playback state at the bottom left was clicked."""

    def __init__(self, translator: Translator, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.t = translator
        self._status = PlayerStatus()

    def compose(self) -> ComposeResult:
        """Lay out the two lines of the bar."""
        with Horizontal(id="np-top"):
            yield Static("", id="np-state")
            yield Static(EMPTY, id="np-dial")
            yield Static("", id="np-station")
            yield Static(format_duration(0), id="np-timer")
        with Horizontal(id="np-bottom"):
            yield Static(EMPTY, id="np-program")
            yield Static("", id="np-device")
            yield Static("", id="np-volume")

    def on_mount(self) -> None:
        """Draw the empty state once the widget joins the screen."""
        self.show(self._status)

    def retranslate(self, translator: Translator) -> None:
        """Redraw the labels in the new language."""
        self.t = translator
        if self.is_mounted:
            self.show(self._status)

    def on_click(self, event: events.Click) -> None:
        """Ask the app to pause or resume when the state label is clicked."""
        if event.widget is not None and event.widget.id == "np-state":
            event.stop()
            if self._status.is_playing:
                self.post_message(self.PlaybackToggled())

    def show(self, status: PlayerStatus) -> None:
        """Update every slot from the current playback status."""
        self._status = status
        station = status.station
        timer = format_duration(status.elapsed_seconds) if station else format_duration(0)
        if status.is_paused:
            timer = f"{timer} ⏸ {format_duration(status.paused_seconds)}"

        label = self.t("player.muted" if status.muted else "player.volume")
        state = f"{STATE_GLYPHS[status.state]} {self.t(STATE_KEYS[status.state])}"

        self.query_one("#np-state", Static).update(state)
        self.query_one("#np-dial", Static).update(station.dial if station else EMPTY)
        self.query_one("#np-station", Static).update(
            station.name if station else self.t("player.no_station")
        )
        self.query_one("#np-timer", Static).update(timer)
        self.query_one("#np-program", Static).update(
            f"♪ {status.program}" if status.program else EMPTY
        )
        self.query_one("#np-device", Static).update(
            truncate(status.device, DEVICE_NAME_LIMIT) if status.device else EMPTY
        )
        self.query_one("#np-volume", Static).update(format_volume(status.volume, label))

        self.set_class(status.state is PlaybackState.PLAYING, "playing")
        self.set_class(status.is_paused, "paused")


class KeyHintBar(Static):
    """Footer replacement whose key hints follow the interface language."""

    HINTS = (
        ("←→", "key.tabs"),
        ("enter", "key.select"),
        ("space", "key.pause"),
        ("s", "key.stop"),
        ("f", "key.favorite"),
        ("+/-", "key.volume_up"),
        ("m", "key.mute"),
        ("t", "key.theme"),
        ("w", "key.language"),
        ("q", "key.quit"),
    )

    def __init__(self, translator: Translator, **kwargs: object) -> None:
        super().__init__("", **kwargs)
        self.t = translator

    def on_mount(self) -> None:
        """Draw the hints once the widget joins the screen."""
        self._render_text()

    def retranslate(self, translator: Translator) -> None:
        """Redraw the hints in the new language."""
        self.t = translator
        if self.is_mounted:
            self._render_text()

    def _render_text(self) -> None:
        """Write every key and its translated label on one line."""
        self.update("  ".join(f"{key} {self.t(name)}" for key, name in self.HINTS))

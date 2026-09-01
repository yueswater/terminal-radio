"""Reusable widgets of the terminal UI."""

from __future__ import annotations

from functools import lru_cache

from rich.cells import cell_len, set_cell_size

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.timer import Timer
from textual.widgets import DataTable, ListItem, ListView, Static

from terminal_radio.core import about
from terminal_radio.constants.logo import LOGO
from terminal_radio.constants.tui import (
    DEFAULT_SORT_COLUMN,
    DEVICE_NAME_LIMIT,
    EMPTY,
    HEALTH_GLYPHS,
    MARQUEE_HOLD_TICKS,
    MARQUEE_SEPARATOR,
    MARQUEE_STEP_SECONDS,
    PAGE_NAVIGATION,
    SEARCH_GLYPH,
    SORT_GLYPHS,
    SORTABLE_COLUMNS,
    STAR,
    STATE_GLYPHS,
    STATE_KEYS,
    TAB_NAVIGATION,
)
from terminal_radio.core.i18n import Translator
from terminal_radio.enums import PlaybackState, StationHealth
from terminal_radio.models import PlayerStatus, Station, Theme
from terminal_radio.models.now_playing import NowPlayingEntry
from terminal_radio.services import ListeningStatistics, StationSummary
from terminal_radio.tui.labels import format_tags
from terminal_radio.tui.formatting import (
    format_clock,
    format_duration,
    format_timestamp,
    format_volume,
    truncate,
)
from terminal_radio.tui.statistics import render_listening_statistics, style_statistics_headings

@lru_cache(maxsize=8)
def scale_ascii(lines: tuple[str, ...], factor: int) -> tuple[str, ...]:
    """Return the art enlarged by repeating each cell and each row.

    Cached because every resize and every recompose asks for the same handful of
    scales of the same art.
    """
    if factor <= 1:
        return lines

    scaled: list[str] = []
    for line in lines:
        stretched = "".join(character * factor for character in line)
        scaled.extend([stretched] * factor)
    return tuple(scaled)


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
        self._health: dict[str, StationHealth] = {}
        self._pending = stations
        self._sort_column = DEFAULT_SORT_COLUMN
        self._sort_descending = False

    def on_mount(self) -> None:
        """Declare the columns and load the initial rows."""
        self._add_columns()
        self.set_stations(self._pending)

    def _add_columns(self) -> None:
        """Add the header row in the current language, marking the sorted one."""
        self.add_column(STAR, width=3, key="favorite")
        self.add_column(self.t("column.health"), width=6, key="health")
        self.add_column(self._heading("dial"), width=10, key="dial")
        self.add_column(
            self._heading("station"), width=self.scaled(0.34, 18, 52), key="station"
        )
        self.add_column(self.t("column.info"), key="info")

    def _heading(self, column: str) -> str:
        """Return the label of a sortable column, with its order mark when active."""
        label = self.t(f"column.{column}")
        if column != self._sort_column:
            return label
        return f"{label} {SORT_GLYPHS[self._sort_descending]}"

    def _sort_key(self, station: Station) -> tuple[object, ...]:
        """Return the ordering key of a station for the column in use."""
        if self._sort_column == "station":
            return (station.name, station.band.value)

        # A dial is read as a number, so 96.3 comes before 104.9 rather than after.
        try:
            frequency = float(station.frequency) if station.frequency else float("inf")
        except ValueError:
            frequency = float("inf")
        return (station.band.value, frequency, station.name)

    def sorted_stations(self, stations: tuple[Station, ...]) -> tuple[Station, ...]:
        """Return the stations in the order the header asks for."""
        return tuple(
            sorted(stations, key=self._sort_key, reverse=self._sort_descending)
        )

    def sort_by(self, column: str) -> None:
        """Sort on a column, flipping the order when it is already the sorted one."""
        if column not in SORTABLE_COLUMNS:
            return

        if column == self._sort_column:
            self._sort_descending = not self._sort_descending
        else:
            self._sort_column = column
            self._sort_descending = False

        selected = self.selected_station
        stations = tuple(self._stations.values())
        self.clear(columns=True)
        self._add_columns()
        self.set_stations(stations, self._favorites)

        if selected is not None:
            self.focus_station(selected.slug)

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Sort on the clicked column, ignoring the ones that carry no order."""
        column = str(event.column_key.value)
        if column in SORTABLE_COLUMNS:
            self.sort_by(column)
            event.stop()

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
        """Replace every row with the given stations, in the order in force."""
        self.clear()
        ordered = self.sorted_stations(stations)
        self._stations = {station.slug: station for station in ordered}
        self._favorites = favorites
        for station in ordered:
            self.add_row(
                STAR if station.slug in favorites else "",
                HEALTH_GLYPHS[
                    self._health.get(station.slug, StationHealth.UNKNOWN)
                ],
                station.dial,
                station.name,
                # A station that carries no blurb still says what it plays,
                # which is what fills the column for the relay transmitters.
                station.description or format_tags(self.t, "genre", station.genres),
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

    def set_health(self, slug: str, health: StationHealth) -> None:
        """Update one station's cached health glyph in place."""
        self._health[slug] = health
        if slug in self._stations:
            self.update_cell(slug, "health", HEALTH_GLYPHS[health])

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


class NowPlayingTable(NavigableTable):
    """Table listing what the stations said they were playing, newest first."""

    def __init__(self, translator: Translator, **kwargs: object) -> None:
        super().__init__(translator, **kwargs)
        self._entries: tuple[NowPlayingEntry, ...] = ()

    def on_mount(self) -> None:
        """Declare the columns once the widget joins the screen."""
        self._add_columns()

    def _add_columns(self) -> None:
        """Add the header row in the current language."""
        self.add_column(self.t("column.time"), width=14)
        self.add_column(self.t("column.station"), width=self.scaled(0.24, 14, 34))
        self.add_column(self.t("column.title"))

    def retranslate(self, translator: Translator) -> None:
        """Rebuild the header row in the new language, keeping the rows."""
        super().retranslate(translator)
        self.clear(columns=True)
        self._add_columns()
        self.show(self._entries)

    def show(self, entries: tuple[NowPlayingEntry, ...]) -> None:
        """Replace the rows with the given announcements."""
        self.clear()
        self._entries = entries
        for index, entry in enumerate(entries):
            self.add_row(
                format_timestamp(entry.at),
                entry.station_name,
                entry.title,
                # The same song comes round again, so the row key is the
                # position rather than anything the entry carries.
                key=str(index),
            )


class ListeningStatsPanel(VerticalScroll):
    """Scrollable collection of localized terminal-native listening charts."""

    BINDINGS = PAGE_NAVIGATION

    def __init__(self, translator: Translator, **kwargs: object) -> None:
        super().__init__(can_focus=True, **kwargs)
        self.t = translator
        self._report: ListeningStatistics | None = None

    def compose(self) -> ComposeResult:
        yield Static("", id="statistics-report", markup=False)

    def show(self, report: ListeningStatistics) -> None:
        """Replace the report and redraw it for the available width."""
        self._report = report
        self._render_report()

    def retranslate(self, translator: Translator) -> None:
        """Redraw every heading in the newly selected interface language."""
        self.t = translator
        self._render_report()

    def on_resize(self) -> None:
        """Keep chart lines within the terminal when its width changes."""
        self._render_report()

    def action_scroll_down(self) -> None:
        """Move immediately so keyboard scrolling remains responsive."""
        self.scroll_down(animate=False, immediate=True)

    def action_scroll_up(self) -> None:
        """Move immediately so keyboard scrolling remains responsive."""
        self.scroll_up(animate=False, immediate=True)

    def action_page_down(self) -> None:
        """Move one visible page down without animating the whole report."""
        self.scroll_to(
            y=self.scroll_y + self.scrollable_content_region.height,
            animate=False,
            immediate=True,
        )

    def action_page_up(self) -> None:
        """Move one visible page up without animating the whole report."""
        self.scroll_to(
            y=self.scroll_y - self.scrollable_content_region.height,
            animate=False,
            immediate=True,
        )

    def _render_report(self) -> None:
        if not self.is_mounted or self._report is None:
            return
        report_widget = self.query_one("#statistics-report", Static)
        report_width = (
            report_widget.content_region.width or self.content_region.width
        )
        report = render_listening_statistics(
            self._report,
            self.t,
            width=max(report_width, 32),
            height=max(self.content_region.height, 20),
        )
        report_widget.update(style_statistics_headings(report, self.t))


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
        yield Static(f"{about.DISPLAY_NAME}  {about.get_version()}", id="about-title")
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


class MarqueeLabel(Static):
    """A line of text that slides along when it is too long for its slot.

    Nothing moves unless it has to: a title that fits is simply written out.
    One that does not holds still for a beat, so its opening can be read, and
    then slides a character at a time and wraps round to the start.

    Widths are measured in terminal cells rather than characters, because a
    title is as likely to be Chinese as English and those are twice as wide.
    """

    def __init__(self, prefix: str = "", **kwargs: object) -> None:
        super().__init__("", **kwargs)
        self._prefix = prefix
        self._text = ""
        self._offset = 0
        self._held = 0
        self._scrolling = True
        self._timer: Timer | None = None

    def set_scrolling(self, enabled: bool) -> None:
        """Turn the slide on or off, redrawing what is currently shown."""
        if enabled == self._scrolling:
            return
        self._scrolling = enabled
        self._offset = 0
        self._held = 0
        self._draw()

    def set_text(self, text: str) -> None:
        """Show a line of text, restarting the slide only when it changed.

        The bar is redrawn about once a second, so a title that has not changed
        has to keep the position it had or it would never get anywhere.
        """
        if text == self._text:
            self._draw()
            return

        self._text = text
        self._offset = 0
        self._held = 0
        self._draw()

    def on_mount(self) -> None:
        """Start the clock that moves the text along."""
        self._timer = self.set_interval(MARQUEE_STEP_SECONDS, self._step)

    def on_resize(self) -> None:
        """A wider slot may no longer need to slide at all."""
        self._offset = 0
        self._held = 0
        self._draw()

    @property
    def _room(self) -> int:
        """Return the cells left for the text once the prefix has its own."""
        return max(self.content_region.width - cell_len(self._prefix), 0)

    @property
    def _slides(self) -> bool:
        """Return whether the text is too long to simply be written out."""
        room = self._room
        return (
            self._scrolling
            and bool(self._text)
            and room > 0
            and cell_len(self._text) > room
        )

    def _step(self) -> None:
        """Move the text along one character, holding at the start first."""
        if not self._slides:
            return
        if self._held < MARQUEE_HOLD_TICKS:
            self._held += 1
            return

        looped = self._text + MARQUEE_SEPARATOR
        self._offset = (self._offset + 1) % len(looped)
        self._draw()

    def _draw(self) -> None:
        """Write the window of the text that is currently in view."""
        if not self.is_mounted:
            return
        if not self._text:
            self.update("")
            return

        room = self._room
        if room <= 0:
            self.update("")
            return
        if not self._slides:
            # set_cell_size pads as well as cuts, and a short title must not
            # pick up a trail of spaces it never had.
            standing = (
                self._text
                if cell_len(self._text) <= room
                else set_cell_size(self._text, room)
            )
            self.update(f"{self._prefix}{standing}")
            return

        looped = self._text + MARQUEE_SEPARATOR
        rolled = looped[self._offset :] + looped[: self._offset]
        # set_cell_size pads or cuts to an exact number of cells, and knows not
        # to leave half of a double width character at the edge.
        self.update(f"{self._prefix}{set_cell_size(rolled, room)}")


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
            yield Static("", id="np-fallback")
            yield Static(EMPTY, id="np-dial")
            yield Static("", id="np-station")
            # Beside the station, because the title is what the station is
            # doing right now rather than a detail of the playback below it.
            yield MarqueeLabel("♪ ", id="np-program")
            yield Static(format_duration(0), id="np-timer")
        with Horizontal(id="np-bottom"):
            yield Static("", id="np-sleep")
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

    def set_scrolling_titles(self, enabled: bool) -> None:
        """Pass the listener's choice on to the title slot."""
        labels = self.query(MarqueeLabel)
        if labels:
            labels.first().set_scrolling(enabled)

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
        # Silent while the first address is playing: a badge that is always
        # there says nothing, and the listener only needs to know when the
        # station is being carried by something other than its own stream.
        self.query_one("#np-fallback", Static).update(
            self.t("player.fallback", index=status.stream_index)
            if status.using_fallback
            else ""
        )
        self.query_one("#np-dial", Static).update(station.dial if station else EMPTY)
        self.query_one("#np-station", Static).update(
            station.name if station else self.t("player.no_station")
        )
        self.query_one("#np-timer", Static).update(timer)
        # Nothing at all when the station announces nothing: a dash beside the
        # name would read as part of it.
        self.query_one("#np-program", MarqueeLabel).set_text(status.program or "")
        self.query_one("#np-sleep", Static).update(
            ""
            if status.sleep_remaining_seconds is None
            else self.t(
                "player.sleep",
                duration=format_duration(status.sleep_remaining_seconds),
            )
        )
        self.query_one("#np-device", Static).update(
            truncate(status.device, DEVICE_NAME_LIMIT) if status.device else EMPTY
        )
        self.query_one("#np-volume", Static).update(format_volume(status.volume, label))

        self.set_class(status.state is PlaybackState.PLAYING, "playing")
        self.set_class(status.is_paused, "paused")
        self.set_class(status.state is PlaybackState.RECONNECTING, "reconnecting")


class SearchButton(Static):
    """Search affordance floating over the right end of the tab bar."""

    class Pressed(Message):
        """The search icon was clicked."""

    def __init__(self, translator: Translator, **kwargs: object) -> None:
        super().__init__(SEARCH_GLYPH, **kwargs)
        self.t = translator

    def on_mount(self) -> None:
        """Name the icon once the widget joins the screen."""
        self._render_tooltip()

    def retranslate(self, translator: Translator) -> None:
        """Name the icon in the new language."""
        self.t = translator
        if self.is_mounted:
            self._render_tooltip()

    def on_click(self, event: events.Click) -> None:
        """Ask the app to open the search modal."""
        event.stop()
        self.post_message(self.Pressed())

    def _render_tooltip(self) -> None:
        """Write the hover label, which names the shortcut as well."""
        self.tooltip = f"{self.t('search.title')}  (/)"


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
        ("/", "key.search"),
        ("?", "key.help"),
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

"""Screens shown outside the main tabbed view."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from collections.abc import Callable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Input, ListItem, ListView, Select, Static
from pydantic import ValidationError

from app.core.i18n import Translator
from app.constants.tui import SHORTCUT_HELP
from app.enums import Band, StationHealth
from app.models import Station
from app.services import export_filename
from app.tui.formatting import format_clock, format_path
from app.tui.widgets import LogoBlock, StationTable


class GoodbyeScreen(Screen[None]):
    """Farewell shown for a moment after the user asks to quit."""

    def __init__(
        self, translator: Translator, listened_seconds: float, delay: float
    ) -> None:
        super().__init__()
        self.t = translator
        self._listened = listened_seconds
        self._delay = delay

    def compose(self) -> ComposeResult:
        """Lay out the logo, the farewell and the time listened."""
        with Vertical(id="goodbye"):
            yield LogoBlock(scale=2, id="goodbye-logo")
            yield Static(self.t("goodbye.title"), id="goodbye-title")
            yield Static(
                self.t("goodbye.listened", duration=format_clock(self._listened)),
                id="goodbye-listened",
            )

    def on_mount(self) -> None:
        """Leave the application once the farewell has been on screen."""
        self.set_timer(self._delay, self.app.exit)


class ConfirmationScreen(ModalScreen[bool]):
    """Centered confirmation dialog used for destructive actions."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, translator: Translator, question: str) -> None:
        super().__init__()
        self.t = translator
        self._question = question

    def compose(self) -> ComposeResult:
        """Lay out the question with safe cancel and destructive confirm buttons."""
        with Vertical(id="confirm-dialog"):
            yield Static(self._question, id="confirm-question")
            with Horizontal(id="confirm-actions"):
                yield Button(self.t("confirm.cancel"), id="confirm-cancel")
                yield Button(
                    self.t("confirm.accept"), variant="error", id="confirm-accept"
                )

    def on_mount(self) -> None:
        """Focus cancel so an accidental enter cannot confirm the action."""
        self.query_one("#confirm-cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Return the user's answer to the caller."""
        event.stop()
        self.dismiss(event.button.id == "confirm-accept")

    def action_cancel(self) -> None:
        """Close the dialog without changing anything."""
        self.dismiss(False)


class ShortcutHelpScreen(ModalScreen[None]):
    """Centered, localized reference for every global keyboard shortcut."""

    BINDINGS = [Binding("escape", "close", "Close", show=False)]

    def __init__(self, translator: Translator) -> None:
        super().__init__()
        self.t = translator

    def compose(self) -> ComposeResult:
        lines = "\n".join(
            f"{key:<12} {self.t(message)}" for key, message in SHORTCUT_HELP
        )
        with Vertical(id="shortcut-dialog"):
            yield Static(self.t("help.title"), id="shortcut-title")
            yield Static(lines, id="shortcut-content", markup=False)
            yield Static(self.t("help.close"), id="shortcut-close-hint")

    def action_close(self) -> None:
        self.dismiss(None)


class SleepTimerScreen(ModalScreen[int | Literal["off"] | None]):
    """Centered picker for preset or custom sleep timer durations."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, translator: Translator, remaining_seconds: float | None) -> None:
        super().__init__()
        self.t = translator
        self._remaining = remaining_seconds

    def compose(self) -> ComposeResult:
        """Lay out presets and the validated custom-minute field."""
        with Vertical(id="sleep-dialog"):
            yield Static(self.t("sleep.title"), id="sleep-title")
            current = (
                self.t("sleep.off")
                if self._remaining is None
                else self.t(
                    "sleep.remaining", duration=format_clock(self._remaining)
                )
            )
            yield Static(current, id="sleep-current")
            with Horizontal(id="sleep-presets"):
                yield Button(self.t("sleep.off"), id="sleep-off", compact=True)
                for minutes in (15, 30, 60):
                    yield Button(
                        self.t("sleep.minutes", minutes=minutes),
                        id=f"sleep-{minutes}",
                        compact=True,
                    )
            yield Input(
                placeholder=self.t("sleep.custom_placeholder"),
                type="integer",
                id="sleep-custom",
            )
            yield Static("", id="sleep-error")
            with Horizontal(id="sleep-actions"):
                yield Button(self.t("confirm.cancel"), id="sleep-cancel", compact=True)
                yield Button(
                    self.t("sleep.set"),
                    variant="primary",
                    id="sleep-custom-submit",
                    compact=True,
                )

    def on_mount(self) -> None:
        """Focus the first preset for quick keyboard use."""
        self.query_one("#sleep-off", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Return a preset, cancellation, or validated custom minutes."""
        event.stop()
        button_id = event.button.id or ""
        if button_id == "sleep-cancel":
            self.dismiss(None)
        elif button_id == "sleep-off":
            self.dismiss("off")
        elif button_id in {"sleep-15", "sleep-30", "sleep-60"}:
            self.dismiss(int(button_id.removeprefix("sleep-")))
        elif button_id == "sleep-custom-submit":
            self._submit_custom()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Treat Enter in the custom field as pressing Set."""
        if event.input.id == "sleep-custom":
            event.stop()
            self._submit_custom()

    def _submit_custom(self) -> None:
        """Validate and return one through 1440 minutes."""
        field = self.query_one("#sleep-custom", Input)
        try:
            minutes = int(field.value)
        except ValueError:
            minutes = 0
        if not 1 <= minutes <= 1440:
            self.query_one("#sleep-error", Static).update(self.t("sleep.invalid"))
            field.focus()
            return
        self.dismiss(minutes)

    def action_cancel(self) -> None:
        """Close without changing the active timer."""
        self.dismiss(None)


class StationSearchScreen(ModalScreen[str | None]):
    """Live global search over the merged station library."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(
        self,
        translator: Translator,
        search: Callable[[str], tuple[Station, ...]],
        favorites: frozenset[str],
        health: Callable[[str], StationHealth],
    ) -> None:
        super().__init__()
        self.t = translator
        self._search = search
        self._favorites = favorites
        self._health = health

    def compose(self) -> ComposeResult:
        """Lay out the search field and live station table."""
        stations = self._search("")
        with Vertical(id="station-search-dialog"):
            yield Static(self.t("search.title"), id="station-search-title")
            yield Input(
                placeholder=self.t("search.placeholder"),
                id="station-search-input",
            )
            yield StationTable(
                self.t,
                stations,
                id="station-search-results",
            )
            yield Static(self.t("search.hint"), id="station-search-hint")

    def on_mount(self) -> None:
        """Focus the query and paint cached health results."""
        self.query_one("#station-search-input", Input).focus()
        self._refresh_results("")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter immediately as the query changes."""
        if event.input.id == "station-search-input":
            self._refresh_results(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Play the first highlighted result when Enter is pressed."""
        if event.input.id != "station-search-input":
            return
        event.stop()
        selected = self.query_one("#station-search-results", StationTable).selected_station
        if selected is not None:
            self.dismiss(selected.slug)

    def on_data_table_row_selected(self, event: StationTable.RowSelected) -> None:
        """Return a result activated directly from the table."""
        if isinstance(event.data_table, StationTable):
            event.stop()
            selected = event.data_table.selected_station
            if selected is not None:
                self.dismiss(selected.slug)

    def _refresh_results(self, query: str) -> None:
        table = self.query_one("#station-search-results", StationTable)
        stations = self._search(query)
        table.set_stations(stations, self._favorites)
        for item in stations:
            table.set_health(item.slug, self._health(item.slug))

    def action_cancel(self) -> None:
        """Close without changing playback."""
        self.dismiss(None)


class CustomStationManagerScreen(ModalScreen[tuple[str, str | None] | None]):
    """List custom stations and return the requested management action."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, translator: Translator, stations: tuple[Station, ...]) -> None:
        super().__init__()
        self.t = translator
        self._stations = stations

    def compose(self) -> ComposeResult:
        with Vertical(id="custom-station-manager"):
            yield Static(self.t("custom.manager_title"), id="custom-manager-title")
            yield StationTable(
                self.t,
                self._stations,
                id="custom-station-list",
            )
            with Horizontal(id="custom-manager-actions"):
                yield Button(
                    self.t("custom.add"), id="custom-station-add", compact=True
                )
                yield Button(
                    self.t("custom.edit"), id="custom-station-edit", compact=True
                )
                yield Button(
                    self.t("custom.delete"),
                    variant="error",
                    id="custom-station-delete",
                    compact=True,
                )
                yield Button(
                    self.t("custom.close"), id="custom-station-close", compact=True
                )

    def on_mount(self) -> None:
        table = self.query_one("#custom-station-list", StationTable)
        table.focus()
        disabled = not self._stations
        self.query_one("#custom-station-edit", Button).disabled = disabled
        self.query_one("#custom-station-delete", Button).disabled = disabled

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        button_id = event.button.id
        if button_id == "custom-station-add":
            self.dismiss(("add", None))
        elif button_id == "custom-station-close":
            self.dismiss(None)
        elif button_id in {"custom-station-edit", "custom-station-delete"}:
            selected = self.query_one(
                "#custom-station-list", StationTable
            ).selected_station
            if selected is not None:
                action = "edit" if button_id.endswith("edit") else "delete"
                self.dismiss((action, selected.slug))

    def on_data_table_row_selected(self, event: StationTable.RowSelected) -> None:
        if isinstance(event.data_table, StationTable):
            event.stop()
            selected = event.data_table.selected_station
            if selected is not None:
                self.dismiss(("edit", selected.slug))

    def action_cancel(self) -> None:
        self.dismiss(None)


class CustomStationFormScreen(ModalScreen[Station | None]):
    """Add or edit one custom station while retaining invalid input."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(
        self,
        translator: Translator,
        station: Station | None = None,
    ) -> None:
        super().__init__()
        self.t = translator
        self._station = station

    def compose(self) -> ComposeResult:
        source = self._station
        with Vertical(id="custom-station-form"):
            yield Static(
                self.t("custom.edit_title" if source else "custom.add_title"),
                id="custom-form-title",
            )
            yield Static(self.t("custom.name"), classes="custom-form-label")
            yield Input(value=source.name if source else "", id="custom-name")
            yield Static(self.t("custom.band"), classes="custom-form-label")
            yield Select[Band](
                ((Band.FM.value, Band.FM), (Band.AM.value, Band.AM)),
                allow_blank=False,
                value=source.band if source else Band.FM,
                id="custom-band",
            )
            yield Static(self.t("custom.frequency"), classes="custom-form-label")
            yield Input(
                value=source.frequency or "" if source else "",
                id="custom-frequency",
            )
            yield Static(self.t("custom.url"), classes="custom-form-label")
            yield Input(value=source.url if source else "", id="custom-url")
            yield Static(self.t("custom.description"), classes="custom-form-label")
            yield Input(
                value=source.description or "" if source else "",
                id="custom-description",
            )
            yield Static("", id="custom-form-error")
            with Horizontal(id="custom-form-actions"):
                yield Button(
                    self.t("confirm.cancel"), id="custom-cancel", compact=True
                )
                yield Button(
                    self.t("custom.save"),
                    variant="primary",
                    id="custom-save",
                    compact=True,
                )

    def on_mount(self) -> None:
        self.query_one("#custom-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "custom-cancel":
            self.dismiss(None)
        elif event.button.id == "custom-save":
            self._submit()

    def _submit(self) -> None:
        band = self.query_one("#custom-band", Select).value
        if not isinstance(band, Band):
            self.query_one("#custom-form-error", Static).update(
                self.t("custom.invalid")
            )
            return
        frequency = self.query_one("#custom-frequency", Input).value.strip()
        description = self.query_one("#custom-description", Input).value.strip()
        try:
            station = Station(
                slug=self._station.slug if self._station else "custom-preview",
                name=self.query_one("#custom-name", Input).value.strip(),
                band=band,
                frequency=frequency or None,
                url=self.query_one("#custom-url", Input).value.strip(),
                description=description or None,
            )
        except ValidationError:
            self.query_one("#custom-form-error", Static).update(
                self.t("custom.invalid")
            )
            return
        self.dismiss(station)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ExportScreen(ModalScreen[Path | None]):
    """Destination picker shown when the settings are exported."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("left", "ignore", "Ignore", show=False),
        Binding("right", "ignore", "Ignore", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("j", "cursor_down", "Down", show=False),
    ]

    def __init__(
        self,
        translator: Translator,
        destinations: tuple[tuple[str, Path], ...],
        *,
        filename: str | None = None,
        title_key: str = "export.title",
    ) -> None:
        super().__init__()
        self.t = translator
        self._destinations = destinations
        self._filename = filename or export_filename()
        self._title_key = title_key

    def compose(self) -> ComposeResult:
        """Lay out the title, the destinations and the hint."""
        with Vertical(id="export"):
            yield Static(self.t(self._title_key), id="export-title")
            yield Static(self._filename, id="export-filename")
            yield ListView(
                *[
                    ListItem(Static(f"{self.t(key)}  ·  {format_path(path)}"))
                    for key, path in self._destinations
                ],
                id="export-list",
            )
            yield Static(self.t("export.hint"), id="export-hint")

    def on_mount(self) -> None:
        """Put the cursor on the first destination."""
        self.query_one(ListView).focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Return the chosen destination to the caller."""
        index = event.list_view.index
        if index is not None:
            self.dismiss(self._destinations[index][1])

    def action_cancel(self) -> None:
        """Close the picker without exporting."""
        self.dismiss(None)

    def action_ignore(self) -> None:
        """Swallow the tab keys so the picker stays put."""

    def action_cursor_up(self) -> None:
        """Move the cursor up, for the vim style key."""
        self.query_one(ListView).action_cursor_up()

    def action_cursor_down(self) -> None:
        """Move the cursor down, for the vim style key."""
        self.query_one(ListView).action_cursor_down()


class ImportScreen(ModalScreen[Path | None]):
    """File picker listing the exports found in the usual folders."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("left", "ignore", "Ignore", show=False),
        Binding("right", "ignore", "Ignore", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("j", "cursor_down", "Down", show=False),
    ]

    def __init__(self, translator: Translator, files: tuple[Path, ...]) -> None:
        super().__init__()
        self.t = translator
        self._files = files

    def compose(self) -> ComposeResult:
        """Lay out the title, the files found and the hint."""
        with Vertical(id="import"):
            yield Static(self.t("import.title"), id="import-title")
            if self._files:
                yield ListView(
                    *[
                        ListItem(Static(f"{path.name}  ·  {format_path(path.parent)}"))
                        for path in self._files
                    ],
                    id="import-list",
                )
            else:
                yield Static(self.t("import.empty"), id="import-empty")
            yield Static(self.t("import.hint"), id="import-hint")

    def on_mount(self) -> None:
        """Put the cursor on the newest file, when there is one."""
        listing = self.query(ListView)
        if listing:
            listing.first().focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Return the chosen file to the caller."""
        index = event.list_view.index
        if index is not None:
            self.dismiss(self._files[index])

    def action_cancel(self) -> None:
        """Close the picker without importing."""
        self.dismiss(None)

    def action_ignore(self) -> None:
        """Swallow the tab keys so the picker stays put."""

    def action_cursor_up(self) -> None:
        """Move the cursor up, for the vim style key."""
        listing = self.query(ListView)
        if listing:
            listing.first().action_cursor_up()

    def action_cursor_down(self) -> None:
        """Move the cursor down, for the vim style key."""
        listing = self.query(ListView)
        if listing:
            listing.first().action_cursor_down()

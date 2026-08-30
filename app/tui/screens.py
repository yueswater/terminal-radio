"""Screens shown outside the main tabbed view."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, ListItem, ListView, Static

from app.core.i18n import Translator
from app.services import export_filename
from app.tui.formatting import format_clock, format_path
from app.tui.widgets import LogoBlock


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
        self, translator: Translator, destinations: tuple[tuple[str, Path], ...]
    ) -> None:
        super().__init__()
        self.t = translator
        self._destinations = destinations

    def compose(self) -> ComposeResult:
        """Lay out the title, the destinations and the hint."""
        with Vertical(id="export"):
            yield Static(self.t("export.title"), id="export-title")
            yield Static(export_filename(), id="export-filename")
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

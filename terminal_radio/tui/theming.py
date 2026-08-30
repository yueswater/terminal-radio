"""Bridge between the YAML themes and the Textual theme system."""

from __future__ import annotations

from textual.app import App
from textual.theme import Theme as TextualTheme

from terminal_radio.services import ThemeRepository


def register_themes(app: App[None], repository: ThemeRepository) -> None:
    """Register every YAML theme on the application."""
    for theme in repository.all():
        app.register_theme(TextualTheme(**theme.to_textual_kwargs()))


def resolve_theme_name(repository: ThemeRepository, preferred: str | None) -> str:
    """Return the preferred theme name when it exists, otherwise the default."""
    if preferred and preferred in repository.names():
        return preferred
    return repository.default_name

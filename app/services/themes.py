"""Loading and cycling of the color themes."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from app.core.exceptions import ThemeError
from app.models import Theme


class ThemeRepository:
    """An ordered set of themes with a default and a cycling cursor."""

    def __init__(self, themes: list[Theme], default: str | None = None) -> None:
        if not themes:
            raise ThemeError("Theme file defines no theme")

        self._themes = tuple(themes)
        self._by_name = {theme.name: theme for theme in self._themes}

        if len(self._by_name) != len(self._themes):
            raise ThemeError("Theme names must be unique")
        if default is not None and default not in self._by_name:
            raise ThemeError(f"Unknown default theme: {default}")

        self._default = default or self._themes[0].name

    @classmethod
    def from_file(cls, path: Path) -> "ThemeRepository":
        """Read a YAML theme file and build a repository out of it."""
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except OSError as error:
            raise ThemeError(f"Cannot read theme file: {path}") from error
        except yaml.YAMLError as error:
            raise ThemeError(f"Malformed theme file: {path}") from error

        try:
            themes = [Theme(**entry) for entry in raw.get("themes", [])]
        except (TypeError, ValidationError) as error:
            raise ThemeError(f"Invalid theme entry in {path}") from error

        return cls(themes, raw.get("default"))

    @property
    def default_name(self) -> str:
        """Return the name of the theme selected on startup."""
        return self._default

    def all(self) -> tuple[Theme, ...]:
        """Return every theme in declaration order."""
        return self._themes

    def names(self) -> tuple[str, ...]:
        """Return every theme name in declaration order."""
        return tuple(theme.name for theme in self._themes)

    def get(self, name: str) -> Theme:
        """Return one theme by name or raise ThemeError."""
        try:
            return self._by_name[name]
        except KeyError:
            raise ThemeError(f"Unknown theme: {name}") from None

    def next_after(self, name: str) -> Theme:
        """Return the theme following the given one, wrapping around."""
        names = self.names()
        index = names.index(name) if name in self._by_name else -1
        return self._themes[(index + 1) % len(self._themes)]

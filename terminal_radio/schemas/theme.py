"""Response payloads of the themes endpoint."""

from __future__ import annotations

from pydantic import BaseModel

from terminal_radio.models import Theme


class ThemeRead(BaseModel):
    """Public representation of a color theme."""

    name: str
    dark: bool

    @classmethod
    def from_domain(cls, theme: Theme) -> "ThemeRead":
        """Build the payload from a domain theme."""
        return cls(name=theme.name, dark=theme.dark)


class ThemeListRead(BaseModel):
    """Envelope returned when listing themes."""

    default: str
    total: int
    items: list[ThemeRead]

    @classmethod
    def from_domain(cls, themes: tuple[Theme, ...], default: str) -> "ThemeListRead":
        """Build the payload from a tuple of domain themes."""
        items = [ThemeRead.from_domain(theme) for theme in themes]
        return cls(default=default, total=len(items), items=items)

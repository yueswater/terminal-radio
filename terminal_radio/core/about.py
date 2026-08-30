"""Identity of the application, shown on the about page."""

from __future__ import annotations

from datetime import datetime
from importlib.metadata import PackageNotFoundError, version

from terminal_radio.constants.about import (
    AUTHOR,
    CREDITS,
    DISPLAY_NAME,
    DISTRIBUTION,
    FIRST_YEAR,
    HOMEPAGE,
)

__all__ = [
    "AUTHOR",
    "CREDITS",
    "DISPLAY_NAME",
    "DISTRIBUTION",
    "FIRST_YEAR",
    "HOMEPAGE",
    "copyright_line",
    "get_version",
]


def get_version() -> str:
    """Return the installed package version, or a placeholder when missing."""
    try:
        return version(DISTRIBUTION)
    except PackageNotFoundError:
        return "unknown"


def copyright_line() -> str:
    """Return the copyright notice, widening the year range as time passes."""
    year = datetime.now().year
    span = str(FIRST_YEAR) if year <= FIRST_YEAR else f"{FIRST_YEAR}-{year}"
    return f"© {span} {AUTHOR}"

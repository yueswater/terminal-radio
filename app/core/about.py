"""Identity of the application, shown on the about page."""

from __future__ import annotations

from datetime import datetime
from importlib.metadata import PackageNotFoundError, version

PACKAGE = "radio"
AUTHOR = "Anthony Sung"
FIRST_YEAR = 2026
HOMEPAGE = "https://github.com/anthonysung/radio"

# Every role is a message key, so the about page follows the interface language.
CREDITS = (
    ("Textual", "credit.textual"),
    ("FastAPI", "credit.fastapi"),
    ("Pydantic", "credit.pydantic"),
    ("mpv", "credit.mpv"),
    ("radio-browser.info", "credit.radio_browser"),
)


def get_version() -> str:
    """Return the installed package version, or a placeholder when missing."""
    try:
        return version(PACKAGE)
    except PackageNotFoundError:
        return "unknown"


def copyright_line() -> str:
    """Return the copyright notice, widening the year range as time passes."""
    year = datetime.now().year
    span = str(FIRST_YEAR) if year <= FIRST_YEAR else f"{FIRST_YEAR}-{year}"
    return f"© {span} {AUTHOR}"

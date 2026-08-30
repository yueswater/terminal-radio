"""Small helpers turning domain values into display strings."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def format_duration(seconds: float) -> str:
    """Return a compact hh:mm:ss or mm:ss representation of a duration."""
    total = max(int(seconds), 0)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_clock(seconds: float) -> str:
    """Return a duration as hh:mm:ss, keeping the hours even when they are zero."""
    total = max(int(seconds), 0)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_timestamp(moment: datetime | None) -> str:
    """Return a local, minute precision timestamp, or a dash when missing."""
    if moment is None:
        return "—"
    return moment.astimezone().strftime("%m-%d %H:%M")


def format_volume(volume: int, label: str, width: int = 10) -> str:
    """Return a text gauge showing the output volume, with no emoji in it."""
    filled = round(min(volume, 100) / 100 * width)
    gauge = "\u2588" * filled + "\u2500" * (width - filled)
    return f"{label} {gauge} {volume:>3d}%"


def format_path(path: Path) -> str:
    """Return the path with the home directory folded into a tilde."""
    try:
        return f"~/{path.relative_to(Path.home())}"
    except ValueError:
        return str(path)


def truncate(text: str, limit: int) -> str:
    """Return the text shortened to the limit, ending in an ellipsis when cut."""
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)] + "..."

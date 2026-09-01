"""What each export puts in its columns.

The writing itself belongs to :mod:`terminal_radio.services.csv_writer`. What
is here is only the shape of each export: which columns, in which order, and
how a duration or a moment is spelled inside one.

Column names arrive already translated. This layer never reads a locale file,
so an export made from the command line and one made from the interface are the
same file.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from terminal_radio.constants.transfer import (
    HISTORY_CSV_PREFIX,
    NOW_PLAYING_CSV_PREFIX,
)
from terminal_radio.models.now_playing import NowPlayingEntry
from terminal_radio.services.csv_writer import stamped_filename, write_csv
from terminal_radio.services.history import StationSummary

HistoryHeaders = tuple[str, str, str, str, str, str]
NowPlayingHeaders = tuple[str, str, str]


def history_csv_filename(moment: datetime | None = None) -> str:
    """Return a millisecond-stamped listening-history CSV filename."""
    return stamped_filename(HISTORY_CSV_PREFIX, moment)


def now_playing_csv_filename(moment: datetime | None = None) -> str:
    """Return a millisecond-stamped announced-titles CSV filename."""
    return stamped_filename(NOW_PLAYING_CSV_PREFIX, moment)


def write_history_csv(
    directory: Path,
    summaries: Sequence[StationSummary],
    headers: HistoryHeaders,
    *,
    filename: str | None = None,
) -> Path:
    """Write the listening totals of every station, most listened first."""
    return write_csv(
        directory,
        headers,
        (
            (
                summary.station_dial or "",
                summary.station_name,
                summary.play_count,
                _clock(summary.listened_seconds),
                _clock(summary.paused_seconds),
                _moment(summary.last_played_at),
            )
            for summary in summaries
        ),
        filename or history_csv_filename(),
    )


def write_now_playing_csv(
    directory: Path,
    entries: Sequence[NowPlayingEntry],
    headers: NowPlayingHeaders,
    *,
    filename: str | None = None,
) -> Path:
    """Write every title the stations announced, newest first."""
    return write_csv(
        directory,
        headers,
        (
            (_moment(entry.at), entry.station_name, entry.title)
            for entry in entries
        ),
        filename or now_playing_csv_filename(),
    )


def _clock(seconds: float) -> str:
    """Return a duration as hh:mm:ss, which a spreadsheet reads as a time."""
    total = max(int(seconds), 0)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _moment(value: datetime | None) -> str:
    """Return a local, second precision timestamp, or nothing when missing."""
    if value is None:
        return ""
    return value.astimezone().isoformat(timespec="seconds")

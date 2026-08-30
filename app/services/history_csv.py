"""Localized CSV export for aggregated listening history."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.constants.transfer import (
    EXPORT_TIMESTAMP_FORMAT,
    HISTORY_CSV_PREFIX,
    HISTORY_CSV_SUFFIX,
)
from app.core.exceptions import RadioError
from app.services.history import StationSummary


def history_csv_filename(moment: datetime | None = None) -> str:
    """Return a millisecond-stamped listening-history CSV filename."""
    stamp = (moment or datetime.now()).strftime(EXPORT_TIMESTAMP_FORMAT)[:-3]
    return f"{HISTORY_CSV_PREFIX}{stamp}{HISTORY_CSV_SUFFIX}"


def write_history_csv(
    directory: Path,
    summaries: Sequence[StationSummary],
    headers: tuple[str, str, str, str, str, str],
    *,
    filename: str | None = None,
) -> Path:
    """Atomically write summaries with localized headers and a UTF-8 BOM."""
    chosen_name = filename or history_csv_filename()
    if Path(chosen_name).name != chosen_name:
        raise RadioError("Invalid history export filename")
    folder = directory.expanduser()
    target = folder / chosen_name
    temporary: Path | None = None
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8-sig",
            newline="",
            dir=folder,
            prefix=".history-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            writer = csv.writer(stream)
            writer.writerow(headers)
            for summary in summaries:
                writer.writerow(
                    (
                        summary.station_dial or "",
                        summary.station_name,
                        summary.play_count,
                        _clock(summary.listened_seconds),
                        _clock(summary.paused_seconds),
                        (
                            summary.last_played_at.isoformat(timespec="seconds")
                            if summary.last_played_at
                            else ""
                        ),
                    )
                )
        temporary.replace(target)
    except (OSError, csv.Error) as error:
        raise RadioError(f"Cannot write history export: {target}") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target


def _clock(seconds: float) -> str:
    total = max(int(seconds), 0)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

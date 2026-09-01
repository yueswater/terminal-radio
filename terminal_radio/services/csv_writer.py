"""Writing one spreadsheet file, correctly, whatever is going into it.

The mechanism only. It knows nothing about stations, history or titles: give
it column names and rows and it writes them.

Three things make it worth having in one place. A byte order mark, so a
spreadsheet opens Chinese column names without being asked what encoding they
are in. A write through a temporary file replaced in one step, so an export
interrupted halfway leaves no half-written file that looks finished. And a
filename that cannot escape the folder it was aimed at.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from terminal_radio.constants.transfer import CSV_SUFFIX, EXPORT_TIMESTAMP_FORMAT
from terminal_radio.core.exceptions import RadioError


def stamped_filename(prefix: str, moment: datetime | None = None) -> str:
    """Return a millisecond-stamped CSV filename.

    Two exports a second apart must not land on the same name, and a listener
    sorting a folder by name has to get them in the order they were made.
    """
    stamp = (moment or datetime.now()).strftime(EXPORT_TIMESTAMP_FORMAT)[:-3]
    return f"{prefix}{stamp}{CSV_SUFFIX}"


def write_csv(
    directory: Path,
    headers: Sequence[str],
    rows: Iterable[Sequence[object]],
    filename: str,
) -> Path:
    """Write one CSV into the directory and return the file it created."""
    if Path(filename).name != filename:
        raise RadioError("Invalid export filename")

    folder = directory.expanduser()
    target = folder / filename
    temporary: Path | None = None
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8-sig",
            newline="",
            dir=folder,
            prefix=".export-",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerows(rows)
        temporary.replace(target)
    except (OSError, csv.Error) as error:
        raise RadioError(f"Cannot write export: {target}") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target

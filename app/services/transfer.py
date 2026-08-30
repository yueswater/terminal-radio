"""Export and import of the settings and preferences as a file."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.core.about import get_version
from app.core.config import Settings
from app.core.exceptions import RadioError
from pydantic import ValidationError

from app.services.state import PersistedState

FILE_SUFFIX = ".radio.config"
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S_%f"


def export_filename(moment: datetime | None = None) -> str:
    """Return the file name of an export, stamped down to the millisecond."""
    moment = moment or datetime.now()
    stamp = moment.strftime(TIMESTAMP_FORMAT)[:-3]
    return f"settings_{stamp}{FILE_SUFFIX}"


def build_document(settings: Settings, state: PersistedState) -> dict[str, object]:
    """Return the exported document, with the settings and the preferences."""
    return {
        "version": get_version(),
        "exported_at": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "settings": json.loads(settings.model_dump_json()),
        "preferences": json.loads(state.model_dump_json()),
    }


def write_export(
    directory: Path, settings: Settings, state: PersistedState
) -> Path:
    """Write the export into the directory and return the file it created."""
    target = directory.expanduser() / export_filename()
    document = build_document(settings, state)

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except OSError as error:
        raise RadioError(f"Cannot write export: {target}") from error

    return target


def find_config_files(directories: tuple[Path, ...]) -> tuple[Path, ...]:
    """Return every exported file found in the directories, newest first."""
    found: list[Path] = []
    for directory in directories:
        try:
            found.extend(directory.glob(f"*{FILE_SUFFIX}"))
        except OSError:
            continue

    unique = {path.resolve(): path for path in found}
    return tuple(
        sorted(unique.values(), key=lambda path: path.stat().st_mtime, reverse=True)
    )


def read_preferences(path: Path) -> PersistedState:
    """Read the preferences out of an exported file.

    Only the preferences are read back. The settings block is a record of how the
    program was configured when the file was written, and the paths and commands
    in it belong to the environment, not to the user.
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise RadioError(f"Cannot read export: {path}") from error
    except json.JSONDecodeError as error:
        raise RadioError(f"Malformed export: {path}") from error

    if not isinstance(document, dict) or "preferences" not in document:
        raise RadioError(f"Not a radio export: {path}")

    try:
        return PersistedState(**document["preferences"])
    except (TypeError, ValidationError) as error:
        raise RadioError(f"Invalid preferences in {path}") from error

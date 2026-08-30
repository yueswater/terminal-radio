"""Export and import of the settings and preferences as a file."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from collections.abc import Sequence
from pathlib import Path

from terminal_radio.constants.transfer import CONFIG_EXPORT_SUFFIX, EXPORT_TIMESTAMP_FORMAT
from terminal_radio.core.about import get_version
from terminal_radio.core.config import Settings
from terminal_radio.core.exceptions import RadioError
from terminal_radio.models import Station
from pydantic import ValidationError

from terminal_radio.services.state import PersistedState

@dataclass(frozen=True)
class ImportedConfiguration:
    """Validated portable preferences and optional custom stations."""

    preferences: PersistedState
    custom_stations: tuple[Station, ...] | None


def export_filename(moment: datetime | None = None) -> str:
    """Return the file name of an export, stamped down to the millisecond."""
    moment = moment or datetime.now()
    stamp = moment.strftime(EXPORT_TIMESTAMP_FORMAT)[:-3]
    return f"settings_{stamp}{CONFIG_EXPORT_SUFFIX}"


def build_document(
    settings: Settings,
    state: PersistedState,
    custom_stations: Sequence[Station] = (),
) -> dict[str, object]:
    """Return the exported document, with the settings and the preferences."""
    return {
        "version": get_version(),
        "exported_at": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "settings": json.loads(settings.model_dump_json()),
        "preferences": json.loads(state.model_dump_json()),
        "custom_stations": [
            item.model_dump(mode="json") for item in custom_stations
        ],
    }


def write_export(
    directory: Path,
    settings: Settings,
    state: PersistedState,
    custom_stations: Sequence[Station] = (),
) -> Path:
    """Write the export into the directory and return the file it created."""
    target = directory.expanduser() / export_filename()
    document = build_document(settings, state, custom_stations)

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
            found.extend(directory.glob(f"*{CONFIG_EXPORT_SUFFIX}"))
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
    return read_export(path).preferences


def read_export(path: Path) -> ImportedConfiguration:
    """Read and validate preferences plus optional custom stations."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise RadioError(f"Cannot read export: {path}") from error
    except json.JSONDecodeError as error:
        raise RadioError(f"Malformed export: {path}") from error

    if not isinstance(document, dict) or "preferences" not in document:
        raise RadioError(f"Not a radio export: {path}")

    try:
        preferences = PersistedState(**document["preferences"])
    except (TypeError, ValidationError) as error:
        raise RadioError(f"Invalid preferences in {path}") from error

    if "custom_stations" not in document:
        return ImportedConfiguration(preferences, None)
    entries = document["custom_stations"]
    if not isinstance(entries, list):
        raise RadioError(f"Invalid custom stations in {path}")
    try:
        custom_stations = tuple(Station.model_validate(entry) for entry in entries)
    except (TypeError, ValidationError) as error:
        raise RadioError(f"Invalid custom stations in {path}") from error
    slugs = [item.slug for item in custom_stations]
    if len(slugs) != len(set(slugs)):
        raise RadioError(f"Duplicate custom stations in {path}")
    return ImportedConfiguration(preferences, custom_stations)

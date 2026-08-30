"""Carrying listener state over from where earlier versions kept it.

Before the program could be installed, it wrote its history and preferences
beside its own source. Those files belong to the listener, not to the checkout,
so the first run after the move brings them along.

The copy is one way and never overwrites: once the new directory holds a file,
the old one is left alone as a backup.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from terminal_radio.constants.config import PACKAGE_DIR

LEGACY_DATA_DIR = PACKAGE_DIR.parent / ".radio"
CARRIED_FILES = ("history.jsonl", "state.json", "custom-stations.toml")


def migrate_legacy_data(target: Path, legacy: Path = LEGACY_DATA_DIR) -> tuple[str, ...]:
    """Copy any file the old directory still holds alone, and name what moved."""
    if not legacy.is_dir() or legacy.resolve() == target.resolve():
        return ()

    carried: list[str] = []
    for name in CARRIED_FILES:
        source, destination = legacy / name, target / name
        if not source.is_file() or destination.exists():
            continue
        try:
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        except OSError:
            continue
        carried.append(name)

    return tuple(carried)

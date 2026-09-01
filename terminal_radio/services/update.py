"""Noticing that a newer release exists, and knowing how to fetch it.

Two questions are answered here, and they are separate. Whether there is a newer
version is asked of the index. How to install it depends on how this copy was
installed, which is read off the installation itself rather than guessed.

Nothing here ever raises. A listener opening a radio does not want to hear that
the version check failed, so every failure is the same as finding nothing.
"""

from __future__ import annotations

import json
import shutil
import urllib.request
from dataclasses import dataclass
from importlib.metadata import Distribution, PackageNotFoundError
from pathlib import Path

from terminal_radio.constants.update import (
    PYPI_RELEASE_URL,
    UPDATE_CHECK_TIMEOUT_SECONDS,
)


def parse_version(text: str) -> tuple[int, ...] | None:
    """Return the numbers of a plain release version, or None for anything else.

    Only ``1.2.3`` shaped versions are understood. A release candidate or a
    development build is deliberately not comparable, so a listener on a stable
    version is never told to move to one.
    """
    parts = text.strip().split(".")
    if not parts or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def is_newer(candidate: str, current: str) -> bool:
    """Return whether one version is a later release than another."""
    left, right = parse_version(candidate), parse_version(current)
    if left is None or right is None:
        return False

    length = max(len(left), len(right))
    padded_left = left + (0,) * (length - len(left))
    padded_right = right + (0,) * (length - len(right))
    return padded_left > padded_right


def latest_release(
    distribution: str, timeout: float = UPDATE_CHECK_TIMEOUT_SECONDS
) -> str | None:
    """Return the newest version the index offers, or None when it cannot say."""
    url = PYPI_RELEASE_URL.format(distribution=distribution)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            document = json.load(response)
        version = document["info"]["version"]
    except Exception:
        # Offline, blocked, rate limited, or the index answered with something
        # unexpected. None of it is worth troubling the listener with.
        return None
    return str(version) if version else None


@dataclass(frozen=True)
class Installation:
    """How this copy of the program was installed."""

    # The command that would replace it, or None when it should not be replaced
    # from inside the program.
    upgrade_command: tuple[str, ...] | None
    # Why there is no command, for the one case worth explaining: a checkout.
    editable: bool = False

    @property
    def upgradable(self) -> bool:
        """Return whether the program can replace itself."""
        return self.upgrade_command is not None


def describe_installation(distribution: str) -> Installation:
    """Work out how to upgrade this copy, by looking at where it lives.

    A tool installer keeps its packages under a directory that names it, which
    is a surer signal than asking which commands happen to be on the path: a
    machine may well have both uv and pipx while only one of them owns this.
    """
    try:
        distribution_metadata = Distribution.from_name(distribution)
    except PackageNotFoundError:
        return Installation(None)

    if _is_editable(distribution_metadata):
        # A checkout, where upgrading means git, not an index.
        return Installation(None, editable=True)

    location = _location(distribution_metadata)
    if location is None:
        return Installation(None)

    parts = location.parts
    if "uv" in parts and "tools" in parts and shutil.which("uv"):
        return Installation(("uv", "tool", "upgrade", distribution))
    if "pipx" in parts and shutil.which("pipx"):
        return Installation(("pipx", "upgrade", distribution))

    return Installation(None)


def _is_editable(distribution_metadata: Distribution) -> bool:
    """Return whether the distribution points at a working copy."""
    try:
        raw = distribution_metadata.read_text("direct_url.json")
    except OSError:
        return False
    if not raw:
        return False
    try:
        document = json.loads(raw)
    except json.JSONDecodeError:
        return False
    return bool(document.get("dir_info", {}).get("editable"))


def _location(distribution_metadata: Distribution) -> Path | None:
    """Return the directory the distribution is installed into."""
    try:
        located = distribution_metadata.locate_file("")
    except Exception:
        return None
    return Path(str(located)) if located is not None else None

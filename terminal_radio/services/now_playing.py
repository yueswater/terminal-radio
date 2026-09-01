"""Append only log of the titles the stations announced."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from terminal_radio.constants.playback import (
    NOW_PLAYING_REPEAT_SECONDS,
    NOW_PLAYING_TRIM_EVERY,
)
from terminal_radio.models import Station
from terminal_radio.models.now_playing import NowPlayingEntry


def normalize_title(title: str) -> str:
    """Return the title with its runs of whitespace collapsed to one space."""
    return " ".join(title.split())


class NowPlayingLog:
    """Stores announced titles as JSON lines and reads them back newest first.

    Two things keep the file honest. The same title is not written twice in a
    row for a station, which is what a reconnect would otherwise cause, and
    entries older than the retention window are dropped as the log grows. A
    music station announces a title every few minutes, so this file fills far
    faster than the listening history and cannot be left to grow forever.
    """

    def __init__(self, path: Path, retention_days: int = 30) -> None:
        self._path = path
        self._retention_days = retention_days
        self._last: dict[str, tuple[str, datetime]] = {}
        self._since_trim = 0

    def record(self, station: Station, title: str) -> NowPlayingEntry | None:
        """Log a title unless it repeats what the station just said.

        Returns the entry written, or None when the title was suppressed.
        """
        cleaned = normalize_title(title)
        if not cleaned:
            return None

        now = datetime.now(UTC)
        previous = self._last.get(station.slug)
        if previous is not None:
            last_title, last_at = previous
            repeated_soon = (now - last_at) < timedelta(
                seconds=NOW_PLAYING_REPEAT_SECONDS
            )
            if last_title == cleaned and repeated_soon:
                return None
            if last_title == cleaned:
                # The same title after a long gap is a genuine second play, but
                # the timestamp still has to move so the window keeps working.
                self._last[station.slug] = (cleaned, now)

        entry = NowPlayingEntry(
            at=now,
            station_slug=station.slug,
            station_name=station.name,
            title=cleaned,
        )
        if not self._append(entry):
            return None

        self._last[station.slug] = (cleaned, now)
        return entry

    def forget(self, slug: str | None = None) -> None:
        """Drop what a station last said, so its next title is written again."""
        if slug is None:
            self._last.clear()
        else:
            self._last.pop(slug, None)

    def read(self, limit: int | None = None) -> tuple[NowPlayingEntry, ...]:
        """Return the most recently announced titles, newest first."""
        if limit is not None and limit <= 0:
            return ()
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return ()

        entries: list[NowPlayingEntry] = []
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                entries.append(NowPlayingEntry(**json.loads(line)))
            except (json.JSONDecodeError, TypeError, ValidationError):
                continue
            if limit is not None and len(entries) >= limit:
                break
        return tuple(entries)

    def clear(self) -> bool:
        """Remove every stored title and report whether it succeeded."""
        self.forget()
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            return False
        return True

    def trim(self) -> int:
        """Drop entries past the retention window, returning how many went."""
        entries = self.read()
        if not entries:
            return 0

        cutoff = datetime.now(UTC) - timedelta(days=self._retention_days)
        kept = [entry for entry in entries if entry.at >= cutoff]
        if len(kept) == len(entries):
            return 0

        # Oldest first again, which is the order the file is written in.
        payload = "".join(
            entry.model_dump_json() + "\n" for entry in reversed(kept)
        )
        try:
            self._path.write_text(payload, encoding="utf-8")
        except OSError:
            return 0
        return len(entries) - len(kept)

    def _append(self, entry: NowPlayingEntry) -> bool:
        """Add one entry, silently ignoring an unwritable location."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as stream:
                stream.write(entry.model_dump_json() + "\n")
        except OSError:
            return False

        self._since_trim += 1
        if self._since_trim >= NOW_PLAYING_TRIM_EVERY:
            self._since_trim = 0
            self.trim()
        return True

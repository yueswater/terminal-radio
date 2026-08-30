"""Persistence of the small state remembered between runs."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError


class PersistedState(BaseModel):
    """What the application remembers across restarts."""

    last_station_slug: str | None = None
    theme_name: str | None = None
    favorites: list[str] = Field(default_factory=list)
    volume: int = Field(default=100, ge=0, le=130)
    muted: bool = False
    autoplay_last_station: bool | None = None
    enable_animations: bool | None = None
    auto_reconnect: bool | None = None
    auto_health_check: bool | None = None
    locale: str | None = None


class StateStore:
    """Reads and writes the persisted state as a small JSON file."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> PersistedState:
        """Return the stored state, falling back to an empty one."""
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return PersistedState(**raw)
        except (OSError, json.JSONDecodeError, TypeError, ValidationError):
            return PersistedState()

    def save(self, state: PersistedState) -> None:
        """Write the state, silently ignoring an unwritable location."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        except OSError:
            return

    def update(self, **changes: object) -> PersistedState:
        """Merge changes into the stored state and write it back."""
        state = self.load().model_copy(update=changes)
        self.save(state)
        return state

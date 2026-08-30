"""Deterministic reconnect backoff state."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from app.constants.playback import (
    RECONNECT_DELAYS_SECONDS,
    RECONNECT_STABLE_SECONDS,
)

class ReconnectSchedule:
    """Track retry deadlines and the post-restart stability window."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        delays: Sequence[float] = RECONNECT_DELAYS_SECONDS,
        stable_seconds: float = RECONNECT_STABLE_SECONDS,
    ) -> None:
        if not delays or any(delay < 0 for delay in delays):
            raise ValueError("delays must contain non-negative values")
        if stable_seconds < 0:
            raise ValueError("stable_seconds must be non-negative")
        self._clock = clock
        self._delays = tuple(float(delay) for delay in delays)
        self._stable_seconds = float(stable_seconds)
        self._active = False
        self._attempt = 0
        self._due_at: float | None = None
        self._stable_since: float | None = None

    @property
    def active(self) -> bool:
        return self._active

    @property
    def attempt(self) -> int:
        return self._attempt

    @property
    def ready(self) -> bool:
        return (
            self._active
            and self._stable_since is None
            and self._due_at is not None
            and self._clock() >= self._due_at
        )

    @property
    def stabilizing(self) -> bool:
        return self._active and self._stable_since is not None

    @property
    def stable(self) -> bool:
        return (
            self.stabilizing
            and self._clock() - self._stable_since >= self._stable_seconds
        )

    def start(self) -> None:
        """Schedule the first attempt from now."""
        self._active = True
        self._attempt = 0
        self._stable_since = None
        self._due_at = self._clock() + self._delays[0]

    def record_attempt(self) -> int:
        """Enter the stability window and return the one-based attempt number."""
        if not self.ready:
            raise RuntimeError("reconnect attempt is not ready")
        self._attempt += 1
        self._due_at = None
        self._stable_since = self._clock()
        return self._attempt

    def record_failure(self) -> bool:
        """Schedule the next attempt, returning false when retries are exhausted."""
        if not self.stabilizing:
            raise RuntimeError("no reconnect attempt is in progress")
        self._stable_since = None
        if self._attempt >= len(self._delays):
            self._active = False
            self._due_at = None
            return False
        self._due_at = self._clock() + self._delays[self._attempt]
        return True

    def reset(self) -> None:
        """Clear all retry state."""
        self._active = False
        self._attempt = 0
        self._due_at = None
        self._stable_since = None

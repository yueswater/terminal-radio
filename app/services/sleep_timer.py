"""A monotonic, session-only sleep timer."""

from __future__ import annotations

import time
from collections.abc import Callable

from app.constants.playback import SLEEP_MINUTES_MAX, SLEEP_MINUTES_MIN

class SleepTimer:
    """Track one playback-stop deadline without starting a background thread."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._deadline: float | None = None

    def set_minutes(self, minutes: int | None) -> None:
        """Set the deadline, or cancel it when ``minutes`` is ``None``."""
        if minutes is None:
            self.cancel()
            return
        if not SLEEP_MINUTES_MIN <= minutes <= SLEEP_MINUTES_MAX:
            raise ValueError(
                f"minutes must be between {SLEEP_MINUTES_MIN} and {SLEEP_MINUTES_MAX}"
            )
        self._deadline = self._clock() + minutes * 60

    def cancel(self) -> None:
        """Remove the active deadline."""
        self._deadline = None

    def remaining_seconds(self) -> float | None:
        """Return clamped remaining time, or ``None`` when disabled."""
        if self._deadline is None:
            return None
        return max(self._deadline - self._clock(), 0.0)

    def expired(self) -> bool:
        """Return whether an active timer reached its deadline."""
        remaining = self.remaining_seconds()
        return remaining is not None and remaining <= 0

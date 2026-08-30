"""Listening-history enumerations."""

from enum import StrEnum


class HistoryEventType(StrEnum):
    """Kind of event appended to the history log."""

    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    PLAY_STARTED = "play_started"
    PLAY_ENDED = "play_ended"
    PAUSED = "paused"
    RESUMED = "resumed"

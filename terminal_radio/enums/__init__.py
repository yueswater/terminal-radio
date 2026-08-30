"""Shared domain enumerations."""

from terminal_radio.enums.analytics import Daypart
from terminal_radio.enums.history import HistoryEventType
from terminal_radio.enums.playback import PlaybackState
from terminal_radio.enums.station import Band, StationHealth

__all__ = [
    "Band",
    "Daypart",
    "HistoryEventType",
    "PlaybackState",
    "StationHealth",
]

"""Shared domain enumerations."""

from terminal_radio.enums.analytics import Daypart
from terminal_radio.enums.history import HistoryEventType
from terminal_radio.enums.playback import PlaybackState
from terminal_radio.enums.station import Band, Genre, Region, StationHealth

__all__ = [
    "Band",
    "Daypart",
    "Genre",
    "HistoryEventType",
    "PlaybackState",
    "Region",
    "StationHealth",
]

"""Playback lifecycle enumerations."""

from enum import StrEnum


class PlaybackState(StrEnum):
    """Lifecycle of the audio backend."""

    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    RECONNECTING = "reconnecting"

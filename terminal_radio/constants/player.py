"""mpv process, IPC, volume, and metadata constants."""

PLAYER_TERMINATE_TIMEOUT_SECONDS = 3.0
PLAYER_SOCKET_WAIT_SECONDS = 5.0
PLAYER_SOCKET_TIMEOUT_SECONDS = 0.5
MIN_VOLUME = 0
MAX_VOLUME = 130
DEVICE_REFRESH_SECONDS = 15.0
AUTO_DEVICE = "auto"
OBSERVED_PROPERTIES = {
    1: "media-title",
    2: "metadata/by-key/icy-title",
    3: "pause",
    4: "volume",
    5: "mute",
    6: "audio-device",
    7: "current-ao",
    8: "filename",
}
STREAM_ID_LENGTH = 10

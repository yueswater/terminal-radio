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
# Endings that mark a title as the name of the thing being fetched rather than
# the name of what is playing. A station with no metadata reports its playlist
# or its container, and mpv passes that through as the media title.
STREAM_FILE_SUFFIXES = (
    ".m3u8",
    ".m3u",
    ".pls",
    ".mpd",
    ".asx",
    ".aac",
    ".mp3",
    ".m4a",
    ".ogg",
    ".opus",
    ".flac",
    ".wav",
    ".ts",
)
# Titles held for a reader that has not asked yet. A station announcing one
# every few minutes will never come close to this.
ANNOUNCED_TITLE_LIMIT = 64
# How often the level is stepped while the sound is being faded out.
# Fine enough that a fade is heard as a fade rather than as a staircase.
FADE_STEP_SECONDS = 0.05

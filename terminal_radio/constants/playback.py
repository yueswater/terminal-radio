"""Playback recovery and timer boundaries."""

RECONNECT_DELAYS_SECONDS = (1.0, 2.0, 4.0, 8.0, 15.0)
RECONNECT_STABLE_SECONDS = 5.0
SLEEP_MINUTES_MIN = 1
SLEEP_MINUTES_MAX = 1440

# A reconnect makes a station announce the title it was already playing. The
# same title inside this window is that echo rather than a second play.
NOW_PLAYING_REPEAT_SECONDS = 60.0
# How many titles are written before the retention window is applied again.
# Roughly ten hours of music, so trimming costs nothing in practice.
NOW_PLAYING_TRIM_EVERY = 200
NOW_PLAYING_RETENTION_DAYS = 30

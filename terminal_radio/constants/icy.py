"""Limits of the direct request for a station's current title."""

ICY_PROBE_TIMEOUT_SECONDS = 6.0
ICY_READ_CHUNK = 8192
ICY_MAX_REDIRECTS = 4
# A server naming a larger interval than this is not worth downloading past.
ICY_MAX_METAINT = 128 * 1024
ICY_TITLE_KEY = "streamtitle"

# A playlist lists addresses instead of carrying audio, so it carries no
# in-band metadata either.
PLAYLIST_SUFFIXES = (".m3u8", ".m3u", ".pls", ".mpd", ".asx")

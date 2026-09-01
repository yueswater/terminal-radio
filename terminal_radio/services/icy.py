"""Asking a station for its current title directly.

mpv learns the title too, but only once playback has consumed the first
metadata block, which is about two seconds after the sound starts. A shoutcast
server bursts that block as fast as the connection allows, so asking for it
ourselves answers in about a second: the title appears with the sound rather
than a beat behind it.

The request reads one metadata block and hangs up. It is a few tens of
kilobytes and a connection open for around a second, not a second stream.
"""

from __future__ import annotations

import http.client
from urllib.parse import urlsplit

from terminal_radio.constants.icy import (
    ICY_MAX_METAINT,
    ICY_MAX_REDIRECTS,
    ICY_PROBE_TIMEOUT_SECONDS,
    ICY_READ_CHUNK,
    ICY_TITLE_KEY,
    PLAYLIST_SUFFIXES,
)


def carries_icy_metadata(url: str) -> bool:
    """Return whether the address could carry in-band titles at all.

    A playlist is a list of addresses, not a stream, so there is nothing in it
    to ask and no point opening a connection to find that out.
    """
    path = urlsplit(url).path.casefold()
    return not path.endswith(PLAYLIST_SUFFIXES)


def fetch_stream_title(
    url: str, timeout: float = ICY_PROBE_TIMEOUT_SECONDS
) -> str | None:
    """Return the title a station is announcing, or None when it announces none.

    Never raises. A station that does not speak this protocol, is unreachable,
    or is simply between titles all answer the same way: nothing to report.
    """
    if not carries_icy_metadata(url):
        return None

    connection = None
    try:
        connection, response = _open(url, timeout)
        if connection is None or response is None:
            return None

        raw = response.getheader("icy-metaint")
        if raw is None:
            return None
        interval = int(raw)
        if not 0 < interval <= ICY_MAX_METAINT:
            return None

        _skip(response, interval)
        return _read_title(response)
    except (OSError, http.client.HTTPException, ValueError, UnicodeError):
        return None
    finally:
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass


def _open(
    url: str, timeout: float
) -> tuple[http.client.HTTPConnection | None, http.client.HTTPResponse | None]:
    """Open the stream asking for metadata, following any redirects."""
    connection: http.client.HTTPConnection | None = None
    for _ in range(ICY_MAX_REDIRECTS + 1):
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return connection, None

        opener = (
            http.client.HTTPSConnection
            if parts.scheme == "https"
            else http.client.HTTPConnection
        )
        if connection is not None:
            connection.close()
        connection = opener(parts.hostname, parts.port, timeout=timeout)
        target = parts.path or "/"
        if parts.query:
            target = f"{target}?{parts.query}"
        connection.request(
            "GET",
            target,
            headers={"Icy-MetaData": "1", "User-Agent": "radio/0.1"},
        )
        response = connection.getresponse()

        if response.status not in {301, 302, 303, 307, 308}:
            return connection, response if response.status == 200 else None

        location = response.getheader("Location")
        response.read()
        if not location:
            return connection, None
        url = location

    return connection, None


def _skip(response: http.client.HTTPResponse, count: int) -> None:
    """Read past the audio that comes before the first metadata block."""
    remaining = count
    while remaining > 0:
        chunk = response.read(min(ICY_READ_CHUNK, remaining))
        if not chunk:
            return
        remaining -= len(chunk)


def _read_title(response: http.client.HTTPResponse) -> str | None:
    """Read one metadata block and pull the title out of it."""
    length = response.read(1)
    if not length:
        return None

    size = length[0] * 16
    if size == 0:
        return None

    block = response.read(size).decode("utf-8", "replace").strip("\x00")
    for field in block.split(";"):
        name, separator, value = field.partition("=")
        if separator and name.strip().casefold() == ICY_TITLE_KEY:
            title = value.strip().strip("'\"").strip()
            return title or None
    return None

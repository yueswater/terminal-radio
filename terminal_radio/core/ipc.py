"""Talking to the mpv process, over whichever channel the platform offers.

mpv exposes the same JSON protocol everywhere, but not over the same kind of
channel. On Unix it listens on a socket; on Windows it listens on a named pipe,
which is read and written as an ordinary file. Both are reduced to send, receive
and close here, so the player above knows only about lines of JSON.
"""

from __future__ import annotations

import socket
import sys
import time
from pathlib import Path
from typing import Protocol, runtime_checkable

WINDOWS = sys.platform == "win32"
PIPE_PREFIX = r"\\.\pipe"
RETRY_SECONDS = 0.05


@runtime_checkable
class IpcChannel(Protocol):
    """A duplex byte channel to one mpv process."""

    def send(self, payload: bytes) -> None:
        """Write bytes, raising OSError when the channel is gone."""

    def receive(self, size: int) -> bytes:
        """Read up to size bytes. Empty means the far end closed.

        A read that finds nothing within the timeout raises TimeoutError, which
        lets the caller check whether it has been asked to stop.
        """

    def close(self) -> None:
        """Release the channel. Closing twice is not an error."""


def endpoint(name: str, directory: Path) -> Path:
    """Return the address mpv should listen on for this platform.

    A named pipe lives in its own namespace rather than on disk. A Unix socket
    goes in the temporary directory, because its path is limited to about a
    hundred characters.
    """
    return Path(f"{PIPE_PREFIX}\\{name}") if WINDOWS else directory / f"{name}.sock"


def clear(address: Path) -> None:
    """Remove a stale address, where the platform leaves one behind.

    A named pipe disappears with the process that served it, so only the socket
    file needs clearing.
    """
    if WINDOWS:
        return

    address.parent.mkdir(parents=True, exist_ok=True)
    address.unlink(missing_ok=True)


class SocketChannel:
    """Channel backed by a Unix domain socket."""

    def __init__(self, connection: socket.socket) -> None:
        self._connection = connection

    def send(self, payload: bytes) -> None:
        """Write bytes to the socket."""
        self._connection.sendall(payload)

    def receive(self, size: int) -> bytes:
        """Read from the socket, raising TimeoutError when it stays quiet."""
        return self._connection.recv(size)

    def close(self) -> None:
        """Close the socket."""
        try:
            self._connection.close()
        except OSError:
            pass


class PipeChannel:
    """Channel backed by a Windows named pipe.

    The handle is opened unbuffered and in binary, and every write is flushed,
    because mpv acts on a command as soon as it reads the newline.
    """

    def __init__(self, handle) -> None:
        self._handle = handle

    def send(self, payload: bytes) -> None:
        """Write bytes to the pipe and push them out."""
        self._handle.write(payload)
        self._handle.flush()

    def receive(self, size: int) -> bytes:
        """Read from the pipe.

        A pipe read blocks until something arrives, so unlike a socket it never
        reports a timeout. The reader thread is a daemon, and closing the handle
        releases it.
        """
        return self._handle.read(size) or b""

    def close(self) -> None:
        """Close the pipe handle."""
        try:
            self._handle.close()
        except OSError:
            pass


def connect(address: Path, timeout: float, deadline: float) -> IpcChannel | None:
    """Open a channel to mpv, waiting for it to start listening.

    Returns None when mpv never showed up, which the caller treats as a stream
    that failed to start rather than as an error to raise.
    """
    while time.monotonic() < deadline:
        channel = _attempt(address, timeout)
        if channel is not None:
            return channel
        time.sleep(RETRY_SECONDS)
    return None


def _attempt(address: Path, timeout: float) -> IpcChannel | None:
    """Try once to open the channel, returning None when it is not there yet."""
    if WINDOWS:
        try:
            return PipeChannel(open(address, "r+b", buffering=0))
        except OSError:
            return None

    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(timeout)
    try:
        connection.connect(str(address))
    except OSError:
        connection.close()
        return None
    return SocketChannel(connection)

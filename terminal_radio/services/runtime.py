"""Deciding who owns the player, and reaching whoever does.

Exactly one process may own a :class:`RadioService` and the mpv behind it.
Two owners means two audio streams, two reconnect loops, and two writers of the
same state file. The claim is a lock file rather than a socket, because a lock
held by a file descriptor is released by the kernel when its holder dies, so a
crash never leaves the radio unstartable.
"""

from __future__ import annotations

import errno
import fcntl
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from terminal_radio.constants.runtime import (
    DAEMON_START_TIMEOUT_SECONDS,
    SOCKET_POLL_SECONDS,
)


class OwnerLock:
    """An exclusive, crash safe claim on the player.

    Held for as long as the process that took it lives. The file records the
    holder's process id, which is only ever used to tell a person which process
    to look at: the claim itself is the flock, never the number in the file.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: object | None = None

    def acquire(self) -> bool:
        """Take the lock, returning whether this process now owns the player."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = self.path.open("a+", encoding="utf-8")
        except OSError:
            return False

        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False

        try:
            handle.seek(0)
            handle.truncate()
            handle.write(f"{os.getpid()}\n")
            handle.flush()
        except OSError:
            pass

        self._handle = handle
        return True

    def release(self) -> None:
        """Give the lock up, if this process is holding it."""
        handle, self._handle = self._handle, None
        if handle is None:
            return
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)  # type: ignore[attr-defined]
        except OSError:
            pass
        try:
            handle.close()  # type: ignore[attr-defined]
        except OSError:
            pass

    @property
    def held(self) -> bool:
        """Return whether this process is the owner."""
        return self._handle is not None

    def holder_pid(self) -> int | None:
        """Return the process id recorded by whoever holds the lock."""
        try:
            return int(self.path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None


def is_owned(lock_path: Path) -> bool:
    """Return whether some other live process owns the player."""
    probe = OwnerLock(lock_path)
    if not probe.acquire():
        return True
    probe.release()
    return False


def socket_is_live(path: Path) -> bool:
    """Return whether something is actually listening on the socket.

    A socket file outlives the process that made it. Connecting is the only
    way to tell a listener from the litter left by a crash.
    """
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(SOCKET_POLL_SECONDS)
    try:
        connection.connect(str(path))
    except OSError:
        return False
    else:
        return True
    finally:
        connection.close()


def clear_stale_socket(path: Path) -> None:
    """Remove a socket file that nothing is listening on."""
    if not path.exists() or socket_is_live(path):
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return


def wait_for_socket(
    path: Path, timeout: float = DAEMON_START_TIMEOUT_SECONDS
) -> bool:
    """Wait for something to start listening, returning whether it did."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if socket_is_live(path):
            return True
        time.sleep(SOCKET_POLL_SECONDS)
    return False


def spawn_daemon() -> None:
    """Start a headless owner in the background and return at once.

    It is detached from this process group and from every standard stream, so
    closing the terminal that started it does not take the radio with it.
    """
    try:
        subprocess.Popen(
            [sys.executable, "-m", "terminal_radio.cli", "daemon"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as error:
        raise RuntimeError("Cannot start the radio daemon") from error


def ensure_daemon(socket_path: Path, lock_path: Path) -> bool:
    """Make sure an owner is listening, starting one when there is none.

    Returns whether a socket is now reachable. Racing callers are harmless:
    the loser of the lock simply finds the winner's socket and uses it.
    """
    if socket_is_live(socket_path):
        return True

    clear_stale_socket(socket_path)
    if not is_owned(lock_path):
        spawn_daemon()
    return wait_for_socket(socket_path)


def unlink_socket(path: Path) -> None:
    """Remove a socket path so a listener can bind it."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
    except OSError as error:
        if error.errno != errno.ENOENT:
            raise

"""The process that owns the player and answers commands over a socket.

It is the same FastAPI application the HTTP API serves, bound to a unix socket
instead of a port. Nothing new is invented: a command is an HTTP request, the
routes and their payloads already exist and are already tested, and any client
that can open a socket can drive the radio.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from terminal_radio.constants.runtime import (
    CONTROL_SOCKET_MODE,
    DAEMON_IDLE_CHECK_SECONDS,
    DAEMON_IDLE_EXIT_SECONDS,
)
from terminal_radio.core.config import Settings, get_settings
from terminal_radio.services.runtime import OwnerLock, unlink_socket


class IdleTimer:
    """Tracks how long the owner has had nothing to do.

    A headless owner that is playing nothing and being asked nothing is only
    holding a lock other commands may want, so it stands down. Every request
    counts as activity, which is what keeps it alive while a client is around.
    """

    def __init__(
        self,
        idle_seconds: float = DAEMON_IDLE_EXIT_SECONDS,
        clock: object = time.monotonic,
    ) -> None:
        self._idle_seconds = idle_seconds
        self._clock = clock
        self._last_active = self._now()

    def _now(self) -> float:
        return float(self._clock())  # type: ignore[operator]

    def touch(self) -> None:
        """Record that something asked for the radio just now."""
        self._last_active = self._now()

    def expired(self, playing: bool) -> bool:
        """Return whether the owner has been idle long enough to stand down."""
        if playing:
            self.touch()
            return False
        return self._now() - self._last_active >= self._idle_seconds


def serve_in_background(settings: Settings, service: object) -> threading.Thread:
    """Answer control commands for a service this process already owns.

    Used by the terminal UI, so that `radio play` from another window drives
    the radio the listener is looking at rather than starting a second one.
    The caller must already hold the owner lock.
    """
    import uvicorn

    unlink_socket(settings.control_socket)
    server = uvicorn.Server(
        uvicorn.Config(
            _build_app(settings, service),
            uds=str(settings.control_socket),
            log_level="warning",
            access_log=False,
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return thread


def serve(settings: Settings | None = None) -> int:
    """Own the player and answer commands until asked to stop.

    Returns a process exit code. Refusing to start when somebody else already
    owns the player is a success, not a failure: whatever wanted a radio
    running has one.
    """
    import uvicorn

    settings = settings or get_settings()
    lock = OwnerLock(settings.control_lock)
    if not lock.acquire():
        return 0

    try:
        unlink_socket(settings.control_socket)
        server = uvicorn.Server(
            uvicorn.Config(
                _build_app(settings),
                uds=str(settings.control_socket),
                log_level="warning",
                access_log=False,
            )
        )
        _watch_for_idleness(server, settings)
        server.run()
    finally:
        unlink_socket(settings.control_socket)
        lock.release()
    return 0


def _build_app(settings: Settings, service: object | None = None) -> object:
    """Return the API application, told to count requests as activity."""
    from starlette.middleware.base import BaseHTTPMiddleware

    from terminal_radio.main import create_app

    app = create_app(settings, service)  # type: ignore[arg-type]
    app.state.idle = IdleTimer()

    async def note_activity(request: object, call_next: object) -> object:
        app.state.idle.touch()
        # The socket is created by the server, so its permissions are set on
        # the first request rather than before one can arrive.
        _restrict_socket(settings.control_socket)
        return await call_next(request)  # type: ignore[operator]

    app.add_middleware(BaseHTTPMiddleware, dispatch=note_activity)
    return app


def _restrict_socket(path: Path) -> None:
    """Keep the control socket readable only by the user who started it."""
    try:
        if path.exists() and (path.stat().st_mode & 0o777) != CONTROL_SOCKET_MODE:
            path.chmod(CONTROL_SOCKET_MODE)
    except OSError:
        return


def _watch_for_idleness(server: object, settings: Settings) -> None:
    """Ask the server to stop once nothing has needed it for a while."""

    def watch() -> None:
        while not getattr(server, "should_exit", False):
            time.sleep(DAEMON_IDLE_CHECK_SECONDS)
            app = getattr(server, "config", None)
            state = getattr(getattr(app, "loaded_app", None), "state", None)
            idle = getattr(state, "idle", None)
            service = getattr(state, "radio_service", None)
            if idle is None or service is None:
                continue
            try:
                playing = service.status().is_playing
            except Exception:
                playing = False
            if idle.expired(playing):
                server.should_exit = True  # type: ignore[attr-defined]
                return

    threading.Thread(target=watch, daemon=True).start()


def owner_pid(settings: Settings | None = None) -> int | None:
    """Return the process id of the owner, or None when there is none."""
    from terminal_radio.services.runtime import is_owned

    settings = settings or get_settings()
    if not is_owned(settings.control_lock):
        return None
    return OwnerLock(settings.control_lock).holder_pid()


def stop_owner(settings: Settings | None = None) -> bool:
    """Ask the owner to shut down, returning whether one was asked."""
    import signal

    settings = settings or get_settings()
    pid = owner_pid(settings)
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    return True

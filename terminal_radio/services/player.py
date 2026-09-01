"""Audio backends able to play a stream URL."""

from __future__ import annotations

import json
import socket
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Protocol, runtime_checkable

from terminal_radio.constants.player import (
    ANNOUNCED_TITLE_LIMIT,
    AUTO_DEVICE,
    DEVICE_REFRESH_SECONDS,
    FADE_STEP_SECONDS,
    MAX_VOLUME,
    MIN_VOLUME,
    OBSERVED_PROPERTIES,
    PLAYER_SOCKET_TIMEOUT_SECONDS,
    PLAYER_SOCKET_WAIT_SECONDS,
    PLAYER_TERMINATE_TIMEOUT_SECONDS,
    STREAM_FILE_SUFFIXES,
    STREAM_ID_LENGTH,
)
from terminal_radio.core.exceptions import PlayerError
from terminal_radio.services.audio import detect_output_device
from terminal_radio.services.icy import fetch_stream_title


@runtime_checkable
class Player(Protocol):
    """Minimal contract the radio service needs from an audio backend.

    Every method returns immediately. Nothing here may block the caller, because
    the terminal UI calls into it from its event loop.
    """

    @property
    def is_running(self) -> bool:
        """Return whether a stream is loaded, playing or paused."""

    @property
    def is_paused(self) -> bool:
        """Return whether the loaded stream is paused."""

    def start(self, url: str) -> None:
        """Start playing the given stream URL, replacing any running stream."""

    def fade_out(self, seconds: float) -> None:
        """Ramp the output down to silence over the given time.

        Returns at once; the ramp runs on its own. The level the listener chose
        is left untouched, so whatever stops the sound afterwards does not
        inherit a volume of nothing.
        """

    def stop(self) -> None:
        """Stop playback, doing nothing when already stopped."""

    def set_paused(self, paused: bool) -> None:
        """Pause or resume the loaded stream."""

    @property
    def volume(self) -> int:
        """Return the current output volume in percent."""

    def set_volume(self, volume: int) -> None:
        """Set the output volume in percent."""

    @property
    def is_muted(self) -> bool:
        """Return whether the output is muted."""

    def set_muted(self, muted: bool) -> None:
        """Mute or unmute the output."""

    def program(self) -> str | None:
        """Return the title the stream currently advertises, if any."""

    def _ask_for_title(self, url: str, generation: int) -> None:
        """Ask the station for its title directly, off the calling thread.

        mpv learns the same title, but only once playback has consumed the
        first metadata block. Asking outright answers about two seconds sooner,
        so the title appears with the sound instead of a beat behind it.
        """

        def ask() -> None:
            title = fetch_stream_title(url)
            if title is None or self._shutdown.is_set():
                return
            # A different station was chosen while this was in flight.
            if generation != self._generation:
                return
            self._icy_title = title
            self._announce()

        threading.Thread(target=ask, daemon=True).start()

    def drain_program_changes(self) -> tuple[str, ...]:
        """Return the titles announced since the last call, and forget them.

        The backend collects these as they arrive rather than making the caller
        notice a change by polling, so a title that only lasted a moment is
        still reported once.
        """

    def device(self) -> str | None:
        """Return the audio output the sound is going to, if it is known."""


def looks_like_stream_id(title: str) -> bool:
    """Return whether the title is really a stream identifier."""
    return (
        len(title) >= STREAM_ID_LENGTH
        and title.isascii()
        and title.isalnum()
        and any(character.isdigit() for character in title)
    )


# Leading punctuation a station puts in front of an otherwise real title,
# such as " - 晚安FUN音樂". The trailing end is left alone: what looks like
# noise there is usually part of the station's own format.
TITLE_LEADERS = " -–—·•|:"


def tidy_title(title: str) -> str:
    """Return the title without the separators some stations prefix it with."""
    return title.strip().lstrip(TITLE_LEADERS).strip()


def looks_like_address(title: str) -> bool:
    """Return whether the title is the address of the stream itself.

    A station whose address ends in a slash has no last segment to report, so
    mpv falls back to the whole URL. Nothing a station would ever call a track
    contains a scheme.
    """
    return "://" in title


def looks_like_stream_file(title: str) -> bool:
    """Return whether the title is the name of the file being fetched.

    Checked on the title itself rather than against the filename property,
    because the two are reported separately: a station announcing
    ``playlist.m3u8`` does so before mpv gets round to saying that is also its
    filename, and by then the title has already been passed on.
    """
    return title.casefold().endswith(STREAM_FILE_SUFFIXES)


def clamp_volume(volume: int) -> int:
    """Return the volume constrained to the range mpv accepts."""
    return max(MIN_VOLUME, min(MAX_VOLUME, int(volume)))


class MpvPlayer:
    """Player backed by an mpv process driven through its JSON IPC.

    A background thread owns the socket. It subscribes to the properties the UI
    displays and keeps a local copy of them, so every call from the UI is a plain
    attribute read and never waits on mpv.
    """

    def __init__(
        self, command: tuple[str, ...], ipc_socket: Path, volume: int = 100
    ) -> None:
        self._command = command
        self._ipc_socket = ipc_socket
        self._process: subprocess.Popen[bytes] | None = None

        self._volume = clamp_volume(volume)
        self._muted = False
        self._paused = False
        self._media_title: str | None = None
        self._icy_title: str | None = None
        self._filename: str | None = None
        self._audio_device = AUTO_DEVICE
        self._fading = False
        self._output_driver: str | None = None
        self._device: str | None = None
        # The last segment of the address being played. mpv reports it as the
        # media title for any station that sends no metadata of its own.
        self._url_basename: str | None = None

        # Filled by the IPC thread, emptied by whoever asks. A deque is
        # bounded so a reader that never comes cannot grow it without limit.
        self._announced: deque[str] = deque(maxlen=ANNOUNCED_TITLE_LIMIT)
        self._last_announced: str | None = None
        # Bumped by every start, so an answer that arrives after the listener
        # has moved on is recognised as stale and dropped.
        self._generation = 0

        self._connection: socket.socket | None = None
        self._reader: threading.Thread | None = None
        self._shutdown = threading.Event()
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        """Return whether the mpv process is alive, reaping it once it exits."""
        if self._process is None:
            return False
        if self._process.poll() is None:
            return True

        self.stop()
        return False

    @property
    def is_paused(self) -> bool:
        """Return the last pause state reported by mpv."""
        return self._process is not None and self._paused

    @property
    def volume(self) -> int:
        """Return the volume applied to the current and the next stream."""
        return self._volume

    @property
    def is_muted(self) -> bool:
        """Return whether the output is muted."""
        return self._muted

    def start(self, url: str) -> None:
        """Spawn mpv on the given URL and attach the IPC reader to it."""
        self.stop()
        self._prepare_socket()
        self._url_basename = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1] or None
        self._generation += 1

        command = [
            *self._command,
            f"--input-ipc-server={self._ipc_socket}",
            f"--volume={self._volume}",
            f"--mute={'yes' if self._muted else 'no'}",
            url,
        ]
        try:
            # The backend shares the terminal with the UI, so it is detached from
            # every standard stream to keep it from stealing keys or printing.
            self._process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            raise PlayerError(f"Cannot start player: {self._command[0]}") from error

        self._paused = False
        self._fading = False
        self._media_title = None
        self._icy_title = None
        self._filename = None
        self._last_announced = None

        self._shutdown.clear()
        self._reader = threading.Thread(target=self._read_events, daemon=True)
        self._reader.start()
        self._ask_for_title(url, self._generation)

    def fade_out(self, seconds: float) -> None:
        """Ramp mpv down to silence without disturbing the stored level.

        The ramp is sent straight down the socket rather than through
        set_volume, because the number the listener chose has to survive: it is
        what the next run starts at, and what an unfaded stream comes back to.
        """
        if seconds <= 0 or not self.is_running:
            return

        start = self._volume
        steps = max(int(seconds / FADE_STEP_SECONDS), 1)
        self._fading = True

        def ramp() -> None:
            for step in range(1, steps + 1):
                if self._shutdown.is_set():
                    return
                self._send(
                    ["set_property", "volume", round(start * (steps - step) / steps)]
                )
                time.sleep(FADE_STEP_SECONDS)

        threading.Thread(target=ramp, daemon=True).start()

    def stop(self) -> None:
        """Terminate mpv and tear the IPC reader down."""
        process, self._process = self._process, None
        self._shutdown.set()
        self._close_connection()

        self._paused = False
        self._fading = False
        self._media_title = None
        self._icy_title = None
        self._filename = None
        self._url_basename = None
        self._reader = None

        if process is None or process.poll() is not None:
            return

        process.terminate()
        try:
            process.wait(timeout=PLAYER_TERMINATE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    def set_paused(self, paused: bool) -> None:
        """Pause or resume mpv, updating the local copy right away."""
        self._paused = paused
        self._send(["set_property", "pause", paused])

    def set_volume(self, volume: int) -> None:
        """Store the volume and push it to a running mpv process."""
        self._volume = clamp_volume(volume)
        self._send(["set_property", "volume", self._volume])

    def set_muted(self, muted: bool) -> None:
        """Store the mute flag and push it to a running mpv process."""
        self._muted = muted
        self._send(["set_property", "mute", muted])

    def program(self) -> str | None:
        """Return the title of the stream, ignoring the ones that carry no title.

        A stream with no metadata reports its own file name, and a few stations
        send their stream identifier, so both are treated as no title at all.
        """
        for title in (self._icy_title, self._media_title):
            if not title:
                continue

            cleaned = tidy_title(title)
            if not cleaned or cleaned == self._filename:
                continue
            if (
                looks_like_stream_id(cleaned)
                or looks_like_stream_file(cleaned)
                or looks_like_address(cleaned)
            ):
                continue
            if cleaned == self._url_basename:
                continue
            return cleaned
        return None

    def _ask_for_title(self, url: str, generation: int) -> None:
        """Ask the station for its title directly, off the calling thread.

        mpv learns the same title, but only once playback has consumed the
        first metadata block. Asking outright answers about two seconds sooner,
        so the title appears with the sound instead of a beat behind it.
        """

        def ask() -> None:
            title = fetch_stream_title(url)
            if title is None or self._shutdown.is_set():
                return
            # A different station was chosen while this was in flight.
            if generation != self._generation:
                return
            self._icy_title = title
            self._announce()

        threading.Thread(target=ask, daemon=True).start()

    def drain_program_changes(self) -> tuple[str, ...]:
        """Return the titles announced since the last call, and forget them."""
        drained: list[str] = []
        while True:
            try:
                drained.append(self._announced.popleft())
            except IndexError:
                break
        return tuple(drained)

    def _announce(self) -> None:
        """Queue the current title when it differs from the one before it.

        Called from the IPC thread each time a property that feeds the title
        changes, because mpv reports the pieces separately.
        """
        title = self.program()
        if title is not None and title != self._last_announced:
            self._last_announced = title
            self._announced.append(title)

    def device(self) -> str | None:
        """Return the audio output in use, preferring the system device name."""
        if self._audio_device != AUTO_DEVICE:
            return self._audio_device.rsplit("/", 1)[-1]
        return self._device or self._output_driver

    def _prepare_socket(self) -> None:
        """Make sure the IPC socket path is free and its directory exists."""
        try:
            self._ipc_socket.parent.mkdir(parents=True, exist_ok=True)
            self._ipc_socket.unlink(missing_ok=True)
        except OSError as error:
            raise PlayerError(f"Cannot use IPC socket: {self._ipc_socket}") from error

    def _send(self, command: list[object]) -> None:
        """Write one IPC command without waiting for its answer."""
        with self._lock:
            connection = self._connection
            if connection is None:
                return
            try:
                connection.sendall((json.dumps({"command": command}) + "\n").encode())
            except OSError:
                return

    def _close_connection(self) -> None:
        """Close the IPC channel, if one is open."""
        with self._lock:
            connection, self._connection = self._connection, None
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass

    def _read_events(self) -> None:
        """Own the IPC socket and keep the observed properties up to date."""
        connection = self._wait_for_socket()
        if connection is None:
            return

        with self._lock:
            self._connection = connection

        for identifier, name in OBSERVED_PROPERTIES.items():
            self._send(["observe_property", identifier, name])

        buffer = b""
        next_device_probe = 0.0
        while not self._shutdown.is_set():
            if time.monotonic() >= next_device_probe:
                next_device_probe = time.monotonic() + DEVICE_REFRESH_SECONDS
                self._device = detect_output_device()

            try:
                chunk = connection.recv(4096)
            except TimeoutError:
                continue
            except OSError:
                break

            if not chunk:
                break

            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                self._handle_message(line)

        self._close_connection()

    def _wait_for_socket(self) -> socket.socket | None:
        """Connect to the IPC socket, waiting for mpv to create it."""
        deadline = time.monotonic() + PLAYER_SOCKET_WAIT_SECONDS
        while not self._shutdown.is_set() and time.monotonic() < deadline:
            connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            connection.settimeout(PLAYER_SOCKET_TIMEOUT_SECONDS)
            try:
                connection.connect(str(self._ipc_socket))
                return connection
            except OSError:
                connection.close()
                time.sleep(0.05)
        return None

    def _handle_message(self, line: bytes) -> None:
        """Apply one IPC message to the local copy of the observed properties."""
        if not line.strip():
            return

        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            return

        if message.get("event") != "property-change":
            return

        match message.get("name"):
            case "media-title":
                self._media_title = message.get("data")
                self._announce()
            case "metadata/by-key/icy-title":
                self._icy_title = message.get("data")
                self._announce()
            case "pause":
                self._paused = bool(message.get("data"))
            case "volume":
                # While fading, the level coming back is the ramp rather than
                # anything the listener asked for.
                if not self._fading:
                    self._volume = clamp_volume(message.get("data") or 0)
            case "mute":
                self._muted = bool(message.get("data"))
            case "filename":
                name = message.get("data")
                self._filename = str(name) if name else None
            case "audio-device":
                self._audio_device = str(message.get("data") or AUTO_DEVICE)
            case "current-ao":
                driver = message.get("data")
                self._output_driver = str(driver) if driver else None

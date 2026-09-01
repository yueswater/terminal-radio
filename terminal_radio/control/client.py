"""A small HTTP client speaking to the owner over its unix socket.

Deliberately built from the standard library alone. Every control command pays
this import, and a person typing ``radio status`` should get an answer before
they notice asking, so nothing here reaches for pydantic, fastapi or httpx.
"""

from __future__ import annotations

import http.client
import json
import socket
from pathlib import Path
from typing import Any

from terminal_radio.constants.runtime import DAEMON_START_TIMEOUT_SECONDS


class ControlError(Exception):
    """Raised when the owner cannot be reached, or refuses a command."""


class _UnixConnection(http.client.HTTPConnection):
    """An HTTP connection carried over a unix socket rather than a port."""

    def __init__(self, socket_path: str, timeout: float) -> None:
        super().__init__("localhost", timeout=timeout)
        self._socket_path = socket_path

    def connect(self) -> None:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(self.timeout)
        try:
            connection.connect(self._socket_path)
        except OSError as error:
            connection.close()
            raise ControlError("No radio is running") from error
        self.sock = connection


class ControlClient:
    """Sends one command at a time to whoever owns the player."""

    def __init__(
        self, socket_path: Path, timeout: float = DAEMON_START_TIMEOUT_SECONDS
    ) -> None:
        self._socket_path = str(socket_path)
        self._timeout = timeout

    def get(self, path: str, **params: object) -> Any:
        """Ask a question."""
        return self._send("GET", path + _query(params), None)

    def post(self, path: str, body: dict[str, object] | None = None) -> Any:
        """Give an instruction."""
        return self._send("POST", path, body)

    def _send(
        self, method: str, path: str, body: dict[str, object] | None
    ) -> Any:
        connection = _UnixConnection(self._socket_path, self._timeout)
        payload = None if body is None else json.dumps(body).encode()
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"

        try:
            connection.request(method, path, body=payload, headers=headers)
            response = connection.getresponse()
            raw = response.read()
            status = response.status
        except ControlError:
            raise
        except OSError as error:
            raise ControlError("Lost contact with the radio") from error
        finally:
            connection.close()

        try:
            document = json.loads(raw) if raw else None
        except json.JSONDecodeError as error:
            raise ControlError("The radio answered with something unreadable") from error

        if status >= 400:
            raise ControlError(_detail(document, status))
        return document


def _detail(document: object, status: int) -> str:
    """Return the message a failed answer carries, or a plain fallback."""
    if isinstance(document, dict):
        detail = document.get("detail")
        if isinstance(detail, str):
            return detail
        if detail is not None:
            return json.dumps(detail, ensure_ascii=False)
    return f"The radio refused that command ({status})"


def _query(params: dict[str, object]) -> str:
    """Return a query string, leaving out anything unset."""
    from urllib.parse import urlencode

    wanted = {key: value for key, value in params.items() if value is not None}
    return f"?{urlencode(wanted, doseq=True)}" if wanted else ""

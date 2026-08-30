"""Application settings resolved from environment variables."""

from __future__ import annotations

import os
import shlex
import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

PACKAGE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = PACKAGE_DIR.parent

DEFAULT_STATIONS_FILE = PROJECT_DIR / "stations.toml"
DEFAULT_THEMES_FILE = PROJECT_DIR / "themes.yml"
DEFAULT_LOCALES_DIR = PROJECT_DIR / "locales"
DEFAULT_LOCALE = "zh-Hant"
DEFAULT_DATA_DIR = PROJECT_DIR / ".radio"
# --no-terminal keeps mpv away from the shared terminal, so it never reads the
# keys meant for the UI nor writes over it.
DEFAULT_PLAYER_COMMAND = ("mpv", "--no-video", "--no-terminal")
ENV_PREFIX = "RADIO_"


class Settings(BaseModel):
    """Runtime configuration shared by the API and the terminal UI."""

    model_config = {"frozen": True}

    app_name: str = "Radio"
    stations_file: Path = DEFAULT_STATIONS_FILE
    themes_file: Path = DEFAULT_THEMES_FILE
    locales_dir: Path = DEFAULT_LOCALES_DIR
    locale: str = DEFAULT_LOCALE
    data_dir: Path = DEFAULT_DATA_DIR
    player_command: tuple[str, ...] = DEFAULT_PLAYER_COMMAND
    status_refresh_seconds: float = Field(default=1.0, gt=0)
    history_limit: int = Field(default=200, gt=0)
    goodbye_seconds: float = Field(default=1.4, ge=0)
    autoplay_last_station: bool = True
    # Off by default so interface changes stay immediate.
    enable_animations: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, gt=0, le=65535)

    @property
    def history_file(self) -> Path:
        """Return the JSON lines file holding every history event."""
        return self.data_dir / "history.jsonl"

    @property
    def state_file(self) -> Path:
        """Return the JSON file remembering the last station and theme."""
        return self.data_dir / "state.json"

    @property
    def ipc_socket(self) -> Path:
        """Return the unix socket used to talk to the mpv process.

        It lives in the system temporary directory because a unix socket path is
        limited to about a hundred characters on most platforms.
        """
        return Path(tempfile.gettempdir()) / f"radio-mpv-{os.getpid()}.sock"


def _env_flag(name: str) -> bool | None:
    """Read a boolean environment variable, returning None when unset."""
    raw = os.getenv(name)
    if raw is None:
        return None
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache
def get_settings() -> Settings:
    """Build settings once from RADIO_* environment variables."""
    overrides: dict[str, object] = {}

    if stations_file := os.getenv(f"{ENV_PREFIX}STATIONS_FILE"):
        overrides["stations_file"] = Path(stations_file).expanduser()
    if themes_file := os.getenv(f"{ENV_PREFIX}THEMES_FILE"):
        overrides["themes_file"] = Path(themes_file).expanduser()
    if locales_dir := os.getenv(f"{ENV_PREFIX}LOCALES_DIR"):
        overrides["locales_dir"] = Path(locales_dir).expanduser()
    if locale := os.getenv(f"{ENV_PREFIX}LOCALE"):
        overrides["locale"] = locale
    if data_dir := os.getenv(f"{ENV_PREFIX}DATA_DIR"):
        overrides["data_dir"] = Path(data_dir).expanduser()
    if player_command := os.getenv(f"{ENV_PREFIX}PLAYER_COMMAND"):
        overrides["player_command"] = tuple(shlex.split(player_command))
    if refresh := os.getenv(f"{ENV_PREFIX}STATUS_REFRESH_SECONDS"):
        overrides["status_refresh_seconds"] = float(refresh)
    if history_limit := os.getenv(f"{ENV_PREFIX}HISTORY_LIMIT"):
        overrides["history_limit"] = int(history_limit)
    if goodbye := os.getenv(f"{ENV_PREFIX}GOODBYE_SECONDS"):
        overrides["goodbye_seconds"] = float(goodbye)
    if (autoplay := _env_flag(f"{ENV_PREFIX}AUTOPLAY_LAST_STATION")) is not None:
        overrides["autoplay_last_station"] = autoplay
    if (animations := _env_flag(f"{ENV_PREFIX}ENABLE_ANIMATIONS")) is not None:
        overrides["enable_animations"] = animations
    if api_host := os.getenv(f"{ENV_PREFIX}API_HOST"):
        overrides["api_host"] = api_host
    if api_port := os.getenv(f"{ENV_PREFIX}API_PORT"):
        overrides["api_port"] = int(api_port)

    return Settings(**overrides)

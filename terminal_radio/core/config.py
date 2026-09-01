"""Application settings resolved from environment variables."""

from __future__ import annotations

import os
import shlex
import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from terminal_radio.constants.playback import NOW_PLAYING_RETENTION_DAYS
from terminal_radio.constants.config import (
    DEFAULT_DATA_DIR,
    DEFAULT_LOCALE,
    CONTROL_LOCK_NAME,
    CONTROL_SOCKET_NAME,
    DEFAULT_PLAYER_COMMAND,
    ENV_PREFIX,
    default_runtime_dir,
    default_locales_dir,
    default_stations_file,
    default_themes_file,
)


class Settings(BaseModel):
    """Runtime configuration shared by the API and the terminal UI."""

    model_config = {"frozen": True}

    app_name: str = "Wavepick"
    stations_file: Path = Field(default_factory=default_stations_file)
    themes_file: Path = Field(default_factory=default_themes_file)
    locales_dir: Path = Field(default_factory=default_locales_dir)
    locale: str = DEFAULT_LOCALE
    data_dir: Path = DEFAULT_DATA_DIR
    runtime_dir: Path = Field(default_factory=default_runtime_dir)
    player_command: tuple[str, ...] = DEFAULT_PLAYER_COMMAND
    status_refresh_seconds: float = Field(default=1.0, gt=0)
    history_limit: int = Field(default=200, gt=0)
    now_playing_retention_days: int = Field(
        default=NOW_PLAYING_RETENTION_DAYS, gt=0
    )
    goodbye_seconds: float = Field(default=1.4, ge=0)
    autoplay_last_station: bool = True
    auto_reconnect: bool = True
    auto_health_check: bool = True
    # Asks the index, once a day, whether a newer release exists.
    check_for_updates: bool = True
    # Off by default so interface changes stay immediate.
    enable_animations: bool = False
    # A title too long for its slot slides along instead of being cut.
    scroll_titles: bool = True
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
    def now_playing_file(self) -> Path:
        """Return the JSON lines file holding every announced title."""
        return self.data_dir / "now-playing.jsonl"

    @property
    def custom_stations_file(self) -> Path:
        """Return the TOML file holding user-defined stations."""
        return self.data_dir / "custom-stations.toml"

    @property
    def control_socket(self) -> Path:
        """Return the unix socket every client sends its commands to."""
        return self.runtime_dir / CONTROL_SOCKET_NAME

    @property
    def control_lock(self) -> Path:
        """Return the lock file whose holder owns the player."""
        return self.runtime_dir / CONTROL_LOCK_NAME

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
    if runtime_dir := os.getenv(f"{ENV_PREFIX}RUNTIME_DIR"):
        overrides["runtime_dir"] = Path(runtime_dir).expanduser()
    if player_command := os.getenv(f"{ENV_PREFIX}PLAYER_COMMAND"):
        overrides["player_command"] = tuple(shlex.split(player_command))
    if refresh := os.getenv(f"{ENV_PREFIX}STATUS_REFRESH_SECONDS"):
        overrides["status_refresh_seconds"] = float(refresh)
    if history_limit := os.getenv(f"{ENV_PREFIX}HISTORY_LIMIT"):
        overrides["history_limit"] = int(history_limit)
    if retention := os.getenv(f"{ENV_PREFIX}NOW_PLAYING_RETENTION_DAYS"):
        overrides["now_playing_retention_days"] = int(retention)
    if goodbye := os.getenv(f"{ENV_PREFIX}GOODBYE_SECONDS"):
        overrides["goodbye_seconds"] = float(goodbye)
    if (autoplay := _env_flag(f"{ENV_PREFIX}AUTOPLAY_LAST_STATION")) is not None:
        overrides["autoplay_last_station"] = autoplay
    if (reconnect := _env_flag(f"{ENV_PREFIX}AUTO_RECONNECT")) is not None:
        overrides["auto_reconnect"] = reconnect
    if (health := _env_flag(f"{ENV_PREFIX}AUTO_HEALTH_CHECK")) is not None:
        overrides["auto_health_check"] = health
    if (updates := _env_flag(f"{ENV_PREFIX}CHECK_FOR_UPDATES")) is not None:
        overrides["check_for_updates"] = updates
    if (animations := _env_flag(f"{ENV_PREFIX}ENABLE_ANIMATIONS")) is not None:
        overrides["enable_animations"] = animations
    if (scroll := _env_flag(f"{ENV_PREFIX}SCROLL_TITLES")) is not None:
        overrides["scroll_titles"] = scroll
    if api_host := os.getenv(f"{ENV_PREFIX}API_HOST"):
        overrides["api_host"] = api_host
    if api_port := os.getenv(f"{ENV_PREFIX}API_PORT"):
        overrides["api_port"] = int(api_port)

    return Settings(**overrides)

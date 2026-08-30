"""Default paths, commands, and environment prefix."""

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = PACKAGE_DIR.parent

DEFAULT_STATIONS_FILE = PROJECT_DIR / "stations.toml"
DEFAULT_THEMES_FILE = PROJECT_DIR / "themes.yml"
DEFAULT_LOCALES_DIR = PROJECT_DIR / "locales"
DEFAULT_LOCALE = "zh-Hant"
DEFAULT_DATA_DIR = PROJECT_DIR / ".radio"
DEFAULT_PLAYER_COMMAND = ("mpv", "--no-video", "--no-terminal")
ENV_PREFIX = "RADIO_"

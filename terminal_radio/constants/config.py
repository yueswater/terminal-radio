"""Default paths, commands, and environment prefix.

Three kinds of location are kept apart here.

Bundled files ship inside the package, so they are found wherever the program is
installed rather than only in a checkout.

The config directory is where a listener may drop their own catalogue or themes.
It is read first, and the bundled copy is the fallback, so an override never has
to be a complete replacement of the file it shadows.

The state directory is the only one written to. It is outside the installation,
so upgrading or reinstalling never loses a listening history.
"""

from pathlib import Path

from platformdirs import user_config_dir, user_state_dir

# The application name, which owns the state and config directories. It is
# deliberately not the distribution name: renaming the project on an index
# must not orphan a listener's history.
APP_NAME = "terminal-radio"

PACKAGE_DIR = Path(__file__).resolve().parent.parent
BUNDLED_DIR = PACKAGE_DIR / "data"

CONFIG_DIR = Path(user_config_dir(APP_NAME))
STATE_DIR = Path(user_state_dir(APP_NAME))

STATIONS_NAME = "stations.toml"
THEMES_NAME = "themes.yml"
LOCALES_NAME = "locales"

BUNDLED_STATIONS_FILE = BUNDLED_DIR / STATIONS_NAME
BUNDLED_THEMES_FILE = BUNDLED_DIR / THEMES_NAME
BUNDLED_LOCALES_DIR = BUNDLED_DIR / LOCALES_NAME

DEFAULT_LOCALE = "zh-Hant"
DEFAULT_DATA_DIR = STATE_DIR
DEFAULT_PLAYER_COMMAND = ("mpv", "--no-video", "--no-terminal")
ENV_PREFIX = "RADIO_"


def preferred(name: str, bundled: Path) -> Path:
    """Return the listener's own copy of a file when they have one."""
    override = CONFIG_DIR / name
    return override if override.exists() else bundled


def default_stations_file() -> Path:
    """Return the catalogue to read, preferring the listener's own."""
    return preferred(STATIONS_NAME, BUNDLED_STATIONS_FILE)


def default_themes_file() -> Path:
    """Return the theme file to read, preferring the listener's own."""
    return preferred(THEMES_NAME, BUNDLED_THEMES_FILE)


def default_locales_dir() -> Path:
    """Return the locale directory to read, preferring the listener's own."""
    return preferred(LOCALES_NAME, BUNDLED_LOCALES_DIR)

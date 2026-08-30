"""Domain errors raised across the application."""


class RadioError(Exception):
    """Base class for every error raised by this application."""


class StationNotFoundError(RadioError):
    """Raised when a station slug is missing from the catalog."""

    def __init__(self, slug: str) -> None:
        super().__init__(f"Unknown station: {slug}")
        self.slug = slug


class CatalogError(RadioError):
    """Raised when the station catalog cannot be read or parsed."""


class PlayerError(RadioError):
    """Raised when the audio backend cannot be started."""


class ThemeError(RadioError):
    """Raised when the theme file cannot be read or parsed."""


class StateError(RadioError):
    """Raised when the persisted state cannot be read or written."""


class LocaleError(RadioError):
    """Raised when an interface language cannot be read or parsed."""

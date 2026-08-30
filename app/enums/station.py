"""Station-domain enumerations."""

from enum import StrEnum


class Band(StrEnum):
    """Broadcast band a station is transmitted on."""

    FM = "FM"
    AM = "AM"

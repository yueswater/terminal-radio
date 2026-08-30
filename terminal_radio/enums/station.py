"""Station-domain enumerations."""

from enum import StrEnum


class Band(StrEnum):
    """Broadcast band a station is transmitted on."""

    FM = "FM"
    AM = "AM"


class StationHealth(StrEnum):
    """Most recently observed availability of a station stream."""

    UNKNOWN = "unknown"
    CHECKING = "checking"
    ONLINE = "online"
    SLOW = "slow"
    OFFLINE = "offline"

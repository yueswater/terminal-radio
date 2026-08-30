"""Categories used to group listening statistics."""

from enum import StrEnum


class Daypart(StrEnum):
    """Broad local-time periods used by the ASCII charts."""

    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"

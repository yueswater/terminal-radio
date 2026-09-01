"""Station-domain enumerations."""

from enum import StrEnum


class Band(StrEnum):
    """Broadcast band a station is transmitted on."""

    FM = "FM"
    AM = "AM"


class Region(StrEnum):
    """Area a station mainly serves, not where its company is registered.

    The values are the administrative divisions of Taiwan, plus one for the
    networks that cover the whole country. A closed set is what lets a filter
    mean something: free text would split the same place across spellings.
    """

    NATIONAL = "national"
    TAIPEI = "taipei"
    NEW_TAIPEI = "new-taipei"
    KEELUNG = "keelung"
    TAOYUAN = "taoyuan"
    HSINCHU = "hsinchu"
    MIAOLI = "miaoli"
    TAICHUNG = "taichung"
    CHANGHUA = "changhua"
    NANTOU = "nantou"
    YUNLIN = "yunlin"
    CHIAYI = "chiayi"
    TAINAN = "tainan"
    KAOHSIUNG = "kaohsiung"
    PINGTUNG = "pingtung"
    YILAN = "yilan"
    HUALIEN = "hualien"
    TAITUNG = "taitung"
    PENGHU = "penghu"
    KINMEN = "kinmen"
    LIENCHIANG = "lienchiang"


class Genre(StrEnum):
    """What a station mostly broadcasts.

    A station carries as many of these as it needs: a police network is news,
    traffic and talk at once.
    """

    NEWS = "news"
    TALK = "talk"
    TRAFFIC = "traffic"
    MUSIC = "music"
    POP = "pop"
    CLASSICAL = "classical"
    CULTURE = "culture"
    EDUCATION = "education"
    RELIGION = "religion"
    COMMUNITY = "community"
    GOVERNMENT = "government"
    MILITARY = "military"


class StationHealth(StrEnum):
    """Most recently observed availability of a station stream."""

    UNKNOWN = "unknown"
    CHECKING = "checking"
    ONLINE = "online"
    SLOW = "slow"
    OFFLINE = "offline"

"""Static limits and glyphs used by listening statistics."""

from terminal_radio.enums import Daypart

TOP_STATIONS_LIMIT = 10
TREND_DAYS = 14
BAR_GLYPH = "█"
THIN_AXIS_GLYPH = "─"
VERTICAL_CHART_MIN_HEIGHT = 3
VERTICAL_CHART_MAX_HEIGHT = 7
VERTICAL_BAR_MAX_WIDTH = 5
STATS_PANEL_BREAKPOINT = 96
STATS_PANEL_GAP = 3
LEGEND_MIN_COLUMN_WIDTH = 26
RANKING_SLOT_MAX_WIDTH = 14
STATISTICS_HEADING_KEYS = (
    "stats.title",
    "stats.top_stations",
    "stats.trend",
    "stats.weekdays",
    "stats.dayparts",
    "stats.bands",
)
DAYPART_ORDER = (
    Daypart.MORNING,
    Daypart.AFTERNOON,
    Daypart.EVENING,
    Daypart.NIGHT,
)
BAND_ORDER = ("FM", "AM")
OTHER_BAND = "Other"

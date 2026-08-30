"""Static limits and glyphs used by listening statistics."""

from app.enums import Daypart

TOP_STATIONS_LIMIT = 10
TREND_DAYS = 14
BAR_GLYPH = "█"
SPARKLINE_GLYPHS = "▁▂▃▄▅▆▇█"
CHART_BAR_WIDTH = 24
DAYPART_ORDER = (
    Daypart.MORNING,
    Daypart.AFTERNOON,
    Daypart.EVENING,
    Daypart.NIGHT,
)
BAND_ORDER = ("FM", "AM")
OTHER_BAND = "Other"

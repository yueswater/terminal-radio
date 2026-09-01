"""Terminal UI identifiers, sizing, glyphs, and static artwork."""

from textual.binding import Binding

from terminal_radio.enums import PlaybackState, StationHealth

HOME_TAB = "tab-home"
FAVORITES_TAB = "tab-favorites"
HISTORY_TAB = "tab-history"
NOW_PLAYING_TAB = "tab-now-playing"
STATISTICS_TAB = "tab-statistics"
THEMES_TAB = "tab-themes"
SETTINGS_TAB = "tab-settings"
ABOUT_TAB = "tab-about"

VOLUME_STEP = 5
COMPACT_WIDTH = 90
WIDE_WIDTH = 150
DEVICE_NAME_LIMIT = 15
# Rows the programme table holds. The log behind it runs to thousands of
# lines, and nobody scrolls that far looking for a song.
NOW_PLAYING_TABLE_LIMIT = 200

EMPTY = "—"
STAR = "★"
SEARCH_GLYPH = "⌕"

# A title too long for its slot slides along the way a car stereo does. It
# holds still for a beat first, so the start of the title can be read before it
# starts moving, and the separator marks where the loop comes round again.
MARQUEE_STEP_SECONDS = 0.3
MARQUEE_HOLD_TICKS = 6
MARQUEE_SEPARATOR = "   ·   "

# Station columns the header click can sort, and the marks that show the order.
SORTABLE_COLUMNS = ("dial", "station")
DEFAULT_SORT_COLUMN = "dial"
SORT_GLYPHS = {False: "▲", True: "▼"}

SHORTCUT_HELP = (
    ("← / →", "key.tabs"),
    ("j / k", "key.move"),
    ("enter", "key.select"),
    ("space", "key.pause"),
    ("s", "key.stop"),
    ("f", "key.favorite"),
    ("+ / -", "key.volume_up"),
    ("m", "key.mute"),
    ("t", "key.theme"),
    ("w", "key.language"),
    ("e", "key.export"),
    ("i", "key.import"),
    ("/", "key.search"),
    ("?", "key.help"),
    ("q", "key.quit"),
)

TAB_LABELS = {
    HOME_TAB: "tab.home",
    FAVORITES_TAB: "tab.favorites",
    HISTORY_TAB: "tab.history",
    NOW_PLAYING_TAB: "tab.now_playing",
    STATISTICS_TAB: "tab.statistics",
    THEMES_TAB: "tab.themes",
    SETTINGS_TAB: "tab.settings",
    ABOUT_TAB: "tab.about",
}

STATE_GLYPHS = {
    PlaybackState.PLAYING: "▶",
    PlaybackState.PAUSED: "⏸",
    PlaybackState.STOPPED: "■",
    PlaybackState.RECONNECTING: "↻",
}
STATE_KEYS = {
    PlaybackState.PLAYING: "player.playing",
    PlaybackState.PAUSED: "player.paused",
    PlaybackState.STOPPED: "player.stopped",
    PlaybackState.RECONNECTING: "player.reconnecting",
}
HEALTH_GLYPHS = {
    StationHealth.UNKNOWN: "·",
    StationHealth.CHECKING: "…",
    StationHealth.ONLINE: "●",
    StationHealth.SLOW: "◐",
    StationHealth.OFFLINE: "×",
}



TAB_NAVIGATION = [
    Binding("left", "app.previous_tab", "Prev tab", show=False),
    Binding("right", "app.next_tab", "Next tab", show=False),
    Binding("k", "cursor_up", "Up", show=False),
    Binding("j", "cursor_down", "Down", show=False),
]
PAGE_NAVIGATION = [
    Binding("left", "app.previous_tab", "Prev tab", show=False),
    Binding("right", "app.next_tab", "Next tab", show=False),
    Binding("k", "scroll_up", "Up", show=False),
    Binding("j", "scroll_down", "Down", show=False),
    Binding("pageup", "page_up", "Page up", show=False),
    Binding("pagedown", "page_down", "Page down", show=False),
    Binding("home", "scroll_home", "Top", show=False),
    Binding("end", "scroll_end", "Bottom", show=False),
]

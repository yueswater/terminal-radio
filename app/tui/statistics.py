"""Render listening statistics as responsive terminal equalizer charts."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from rich.cells import cell_len, set_cell_size
from rich.text import Text

from app.constants.analytics import (
    BAR_GLYPH,
    DAYPART_ORDER,
    LEGEND_MIN_COLUMN_WIDTH,
    RANKING_SLOT_MAX_WIDTH,
    STATS_PANEL_BREAKPOINT,
    STATS_PANEL_GAP,
    STATISTICS_HEADING_KEYS,
    THIN_AXIS_GLYPH,
    VERTICAL_BAR_MAX_WIDTH,
    VERTICAL_CHART_MAX_HEIGHT,
    VERTICAL_CHART_MIN_HEIGHT,
)
from app.core.i18n import Translator
from app.services import ListeningStatistics
from app.tui.formatting import format_clock

ChartItem = tuple[str, float]


def style_statistics_headings(report: str, translator: Translator) -> Text:
    """Return the literal report with only its localized headings in bold."""
    styled = Text(report)
    for key in STATISTICS_HEADING_KEYS:
        heading = translator(key)
        start = report.find(heading)
        if start >= 0:
            styled.stylize("bold", start, start + len(heading))
    return styled


def render_listening_statistics(
    report: ListeningStatistics,
    translator: Translator,
    *,
    width: int = 80,
    height: int = 36,
) -> str:
    """Return a localized report made entirely from vertical charts."""
    t = translator
    available_width = max(int(width), 24)
    available_height = max(int(height), 20)
    if report.play_count == 0:
        return "\n".join(
            _section_panel(
                t("stats.title"),
                [t("stats.no_data")],
                available_width,
            )
        )

    chart_height = max(
        VERTICAL_CHART_MIN_HEIGHT,
        min(VERTICAL_CHART_MAX_HEIGHT, (available_height - 8) // 5),
    )
    summary_body = _spread_entries(
        (
            f"{t('stats.total')} {format_clock(report.total_listened_seconds)}",
            f"{t('stats.plays')} {report.play_count}",
            f"{t('stats.active_days')} {report.active_days}",
            f"{t('stats.longest')} {format_clock(report.longest_session_seconds)}",
            f"{t('stats.average')} {format_clock(report.average_session_seconds)}",
        ),
        available_width - 2,
    )
    lines = _section_panel(t("stats.title"), summary_body, available_width)

    ranking_width = available_width - 2
    ranking = [
        (item.station_name, item.listened_seconds)
        for item in report.top_stations
    ]
    ranking_body = _vertical_chart(
        ranking,
        ranking_width,
        chart_height,
        value_formatter=format_clock,
        max_slot_width=RANKING_SLOT_MAX_WIDTH,
    )
    lines.extend(
        ("", *_section_panel(t("stats.top_stations"), ranking_body, available_width))
    )

    trend_width = available_width - 2
    trend = [
        (point.day.strftime("%d"), point.seconds)
        for point in report.daily_trend
    ]
    trend_body = _vertical_chart(trend, trend_width, chart_height)
    trend_body.extend(
        _spread_entries(
            (
                report.daily_trend[0].day.strftime("%m/%d"),
                report.daily_trend[-1].day.strftime("%m/%d"),
                format_clock(sum(point.seconds for point in report.daily_trend)),
            ),
            trend_width,
        )
    )
    lines.extend(("", *_section_panel(t("stats.trend"), trend_body, available_width)))

    weekday_items = list(
        zip(
            (t(f"stats.weekday.{key}") for key in (
                "mon",
                "tue",
                "wed",
                "thu",
                "fri",
                "sat",
                "sun",
            )),
            report.weekday_seconds,
            strict=True,
        )
    )
    daypart_items = [
        (t(f"stats.daypart.{part.value}"), report.daypart_seconds[part])
        for part in DAYPART_ORDER
    ]
    band_items = list(report.band_seconds.items())
    panel_widths = (
        _slot_widths(
            available_width - STATS_PANEL_GAP * 2,
            3,
        )
        if available_width >= STATS_PANEL_BREAKPOINT
        else [available_width] * 3
    )
    bottom_panels = (
        _chart_panel(
            t("stats.weekdays"),
            weekday_items,
            panel_widths[0],
            chart_height,
            format_clock,
        ),
        _chart_panel(
            t("stats.dayparts"),
            daypart_items,
            panel_widths[1],
            chart_height,
            format_clock,
        ),
        _chart_panel(
            t("stats.bands"),
            band_items,
            panel_widths[2],
            chart_height,
            _percentage_formatter(report.band_seconds),
        ),
    )
    lines.append("")
    if available_width >= STATS_PANEL_BREAKPOINT:
        lines.extend(_combine_panels(bottom_panels, available_width))
    else:
        for index, panel in enumerate(bottom_panels):
            if index:
                lines.append("")
            lines.extend(panel)

    return "\n".join(_fit(line, available_width) for line in lines)


def _vertical_chart(
    items: Sequence[ChartItem],
    width: int,
    height: int,
    *,
    value_formatter: Callable[[float], str] | None = None,
    max_slot_width: int | None = None,
) -> list[str]:
    """Draw values upward in evenly distributed terminal columns."""
    if not items:
        return []
    maximum = max((value for _, value in items), default=0.0)
    chart_width = (
        min(width, max_slot_width * len(items))
        if max_slot_width is not None
        else width
    )
    left_padding = max((width - chart_width) // 2, 0)
    slot_widths = _slot_widths(chart_width, len(items))
    filled_heights = [
        0
        if value <= 0 or maximum <= 0
        else max(1, round(height * value / maximum))
        for _, value in items
    ]
    rows: list[str] = []
    if value_formatter is not None:
        rows.append(
            " " * left_padding
            + "".join(
                _center(value_formatter(value), slot)
                for (_, value), slot in zip(items, slot_widths, strict=True)
            ).rstrip()
        )
    for level in range(height, 0, -1):
        segments = []
        for slot, filled in zip(slot_widths, filled_heights, strict=True):
            bar_width = min(VERTICAL_BAR_MAX_WIDTH, max(slot - 1, 1))
            block = BAR_GLYPH * bar_width if filled >= level else ""
            segments.append(_center(block, slot))
        rows.append((" " * left_padding + "".join(segments)).rstrip())
    rows.append(" " * left_padding + THIN_AXIS_GLYPH * chart_width)
    rows.append(
        (" " * left_padding + "".join(
            _center(label, slot)
            for (label, _), slot in zip(items, slot_widths, strict=True)
        )).rstrip()
    )
    return rows


def _chart_panel(
    title: str,
    items: Sequence[ChartItem],
    width: int,
    height: int,
    formatter: Callable[[float], str],
) -> list[str]:
    """Build one titled chart with a compact non-zero value legend."""
    content_width = max(width - 2, 1)
    active_entries = tuple(
        f"{label} {formatter(value)}" for label, value in items if value > 0
    )
    body = [
        *_vertical_chart(items, content_width, max(height - 1, 3)),
        *_entry_grid(active_entries, content_width, min_column_width=14),
    ]
    return _section_panel(title, body, width)


def _section_panel(title: str, body: Sequence[str], width: int) -> list[str]:
    """Group one statistic with a quiet heading and consistent indentation."""
    section_width = max(width, 4)
    inner_width = section_width - 2
    lines = [_fit(title, section_width)]
    for line in body:
        content = set_cell_size(_fit(line, inner_width), inner_width)
        lines.append(f"  {content}")
    return lines


def _combine_panels(
    panels: Sequence[list[str]],
    width: int,
) -> list[str]:
    """Lay three related charts side by side across a wide terminal."""
    content_width = width - STATS_PANEL_GAP * (len(panels) - 1)
    widths = _slot_widths(content_width, len(panels))
    row_count = max(len(panel) for panel in panels)
    combined: list[str] = []
    for row in range(row_count):
        cells = [
            set_cell_size(panel[row] if row < len(panel) else "", panel_width)
            for panel, panel_width in zip(panels, widths, strict=True)
        ]
        combined.append((" " * STATS_PANEL_GAP).join(cells).rstrip())
    return combined


def _entry_grid(
    entries: Sequence[str],
    width: int,
    *,
    min_column_width: int = LEGEND_MIN_COLUMN_WIDTH,
) -> list[str]:
    """Pack chart legends into as many readable columns as fit."""
    if not entries:
        return []
    column_count = min(
        len(entries),
        max(1, min(4, (width + 2) // (min_column_width + 2))),
    )
    gap = 2
    column_widths = _slot_widths(
        width - gap * (column_count - 1), column_count
    )
    rows: list[str] = []
    for start in range(0, len(entries), column_count):
        row_entries = entries[start : start + column_count]
        cells = [
            set_cell_size(entry, column_widths[index])
            for index, entry in enumerate(row_entries)
        ]
        rows.append((" " * gap).join(cells).rstrip())
    return rows


def _spread_entries(entries: Sequence[str], width: int) -> list[str]:
    """Wrap summary values, spreading each complete row across the page."""
    rows: list[list[str]] = []
    current: list[str] = []
    current_width = 0
    for entry in entries:
        entry_width = cell_len(entry)
        proposed = current_width + (3 if current else 0) + entry_width
        if current and proposed > width:
            rows.append(current)
            current = [entry]
            current_width = entry_width
        else:
            current.append(entry)
            current_width = proposed
    if current:
        rows.append(current)

    spread: list[str] = []
    for row in rows:
        if len(row) == 1:
            spread.append(row[0])
            continue
        remaining = max(width - sum(cell_len(entry) for entry in row), 0)
        gaps = len(row) - 1
        gap_width, extra = divmod(remaining, gaps)
        parts: list[str] = []
        for index, entry in enumerate(row):
            parts.append(entry)
            if index < gaps:
                parts.append(" " * (gap_width + (1 if index < extra else 0)))
        spread.append("".join(parts).rstrip())
    return spread


def _percentage_formatter(
    values: dict[str, float],
) -> Callable[[float], str]:
    total = sum(values.values())

    def format_percentage(value: float) -> str:
        return f"{(value / total * 100) if total else 0:.1f}%"

    return format_percentage


def _slot_widths(width: int, count: int) -> list[int]:
    base, remainder = divmod(max(width, count), count)
    return [base + (1 if index < remainder else 0) for index in range(count)]


def _center(text: str, width: int) -> str:
    fitted = set_cell_size(text, min(cell_len(text), width))
    padding = max(width - cell_len(fitted), 0)
    left = padding // 2
    return " " * left + fitted + " " * (padding - left)


def _fit(text: str, width: int) -> str:
    return set_cell_size(text, min(cell_len(text), width)).rstrip()

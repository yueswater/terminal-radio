"""Render listening statistics as compact terminal-native ASCII charts."""

from __future__ import annotations

from app.constants.analytics import (
    BAR_GLYPH,
    CHART_BAR_WIDTH,
    DAYPART_ORDER,
    SPARKLINE_GLYPHS,
)
from app.core.i18n import Translator
from app.services import ListeningStatistics
from app.tui.formatting import format_clock, truncate


def render_listening_statistics(
    report: ListeningStatistics,
    translator: Translator,
    *,
    width: int = 80,
) -> str:
    """Return a localized report combining several plain-text chart styles."""
    t = translator
    if report.play_count == 0:
        return f"{t('stats.title')}\n\n{t('stats.no_data')}"

    lines = [
        t("stats.title"),
        "═" * min(max(width - 2, 20), 72),
        (
            f"{t('stats.total')} {format_clock(report.total_listened_seconds)}  │  "
            f"{t('stats.plays')} {report.play_count}  │  "
            f"{t('stats.active_days')} {report.active_days}"
        ),
        (
            f"{t('stats.longest')} {format_clock(report.longest_session_seconds)}  │  "
            f"{t('stats.average')} {format_clock(report.average_session_seconds)}"
        ),
        "",
        t("stats.top_stations"),
    ]
    lines.extend(_ranking_lines(report, width))
    lines.extend(("", t("stats.trend"), _sparkline(report)))
    lines.extend(("", t("stats.weekdays")))
    lines.extend(
        _bar_lines(
            [
                (t(f"stats.weekday.{key}"), seconds)
                for key, seconds in zip(
                    ("mon", "tue", "wed", "thu", "fri", "sat", "sun"),
                    report.weekday_seconds,
                    strict=True,
                )
            ]
        )
    )
    lines.extend(("", t("stats.dayparts")))
    lines.extend(
        _bar_lines(
            [
                (t(f"stats.daypart.{part.value}"), report.daypart_seconds[part])
                for part in DAYPART_ORDER
            ]
        )
    )
    lines.extend(("", t("stats.bands")))
    lines.extend(_share_lines(report.band_seconds))
    return "\n".join(lines)


def _ranking_lines(report: ListeningStatistics, width: int) -> list[str]:
    maximum = max(item.listened_seconds for item in report.top_stations)
    name_width = min(28, max(12, width - CHART_BAR_WIDTH - 22))
    lines: list[str] = []
    for index, item in enumerate(report.top_stations, start=1):
        bar = _bar(item.listened_seconds, maximum)
        name = truncate(item.station_name, name_width).ljust(name_width)
        lines.append(
            f"{index:>2}. {name} {bar:<{CHART_BAR_WIDTH}} "
            f"{format_clock(item.listened_seconds)}"
        )
    return lines


def _sparkline(report: ListeningStatistics) -> str:
    values = [point.seconds for point in report.daily_trend]
    maximum = max(values, default=0.0)
    glyphs = "".join(_spark_glyph(value, maximum) for value in values)
    start = report.daily_trend[0].day.strftime("%m/%d")
    end = report.daily_trend[-1].day.strftime("%m/%d")
    return f"{start}  {glyphs}  {end}  {format_clock(sum(values))}"


def _spark_glyph(value: float, maximum: float) -> str:
    if maximum <= 0:
        return SPARKLINE_GLYPHS[0]
    index = round((len(SPARKLINE_GLYPHS) - 1) * value / maximum)
    return SPARKLINE_GLYPHS[index]


def _bar_lines(items: list[tuple[str, float]]) -> list[str]:
    maximum = max((seconds for _, seconds in items), default=0.0)
    label_width = max((len(label) for label, _ in items), default=1)
    return [
        f"{label:<{label_width}}  {_bar(seconds, maximum):<{CHART_BAR_WIDTH}} "
        f"{format_clock(seconds)}"
        for label, seconds in items
    ]


def _share_lines(bands: dict[str, float]) -> list[str]:
    total = sum(bands.values())
    maximum = max(bands.values(), default=0.0)
    return [
        f"{band:<5} {_bar(seconds, maximum):<{CHART_BAR_WIDTH}} "
        f"{(seconds / total * 100) if total else 0:5.1f}%"
        for band, seconds in bands.items()
    ]


def _bar(value: float, maximum: float) -> str:
    if value <= 0 or maximum <= 0:
        return ""
    length = max(1, round(CHART_BAR_WIDTH * value / maximum))
    return BAR_GLYPH * length

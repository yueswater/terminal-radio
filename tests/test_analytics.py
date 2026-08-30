"""Listening statistics and terminal chart tests."""

from __future__ import annotations

import tempfile
import unittest
from inspect import signature
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from rich.cells import cell_len

from app.core.i18n import LocaleRepository
from app.enums import Daypart, HistoryEventType
from app.models import HistoryEvent
from app.services import HistoryLog, build_listening_statistics
from app.tui.statistics import render_listening_statistics


def ended(
    at: datetime,
    slug: str,
    name: str,
    dial: str,
    duration: float,
    *,
    paused: float = 0,
    interrupted: float = 0,
) -> HistoryEvent:
    """Build one completed play fixture."""
    return HistoryEvent(
        at=at,
        type=HistoryEventType.PLAY_ENDED,
        station_slug=slug,
        station_name=name,
        station_dial=dial,
        duration_seconds=duration,
        paused_seconds=paused,
        interrupted_seconds=interrupted,
    )


class ListeningStatisticsTests(unittest.TestCase):
    def test_statistics_use_completed_plays_and_local_calendar_buckets(self) -> None:
        """Totals, rankings, days, dayparts, and bands share one event source."""
        today = date(2026, 8, 30)
        events = (
            ended(
                datetime(2026, 8, 30, 7, tzinfo=UTC),
                "a",
                "Alpha",
                "FM 90.1",
                120,
                paused=20,
                interrupted=10,
            ),
            ended(
                datetime(2026, 8, 30, 14, tzinfo=UTC),
                "a",
                "Alpha",
                "FM 90.1",
                50,
            ),
            ended(
                datetime(2026, 8, 29, 22, tzinfo=UTC),
                "b",
                "Bravo",
                "AM 1000",
                200,
            ),
            HistoryEvent(
                at=datetime(2026, 8, 30, 12, tzinfo=UTC),
                type=HistoryEventType.PLAY_STARTED,
                station_slug="ignored",
                duration_seconds=999,
            ),
        )

        report = build_listening_statistics(events, today=today, timezone=UTC)

        self.assertEqual(report.play_count, 3)
        self.assertEqual(report.total_listened_seconds, 340)
        self.assertEqual(report.active_days, 2)
        self.assertEqual(report.longest_session_seconds, 200)
        self.assertAlmostEqual(report.average_session_seconds, 340 / 3)
        self.assertEqual(
            [(item.station_slug, item.listened_seconds) for item in report.top_stations],
            [("b", 200), ("a", 140)],
        )
        self.assertEqual(report.daily_trend[-2].seconds, 200)
        self.assertEqual(report.daily_trend[-1].seconds, 140)
        self.assertEqual(report.daypart_seconds[Daypart.MORNING], 90)
        self.assertEqual(report.daypart_seconds[Daypart.AFTERNOON], 50)
        self.assertEqual(report.daypart_seconds[Daypart.NIGHT], 200)
        self.assertEqual(report.band_seconds, {"FM": 140, "AM": 200})

    def test_history_read_all_is_not_limited_by_table_cap(self) -> None:
        """Analytics can consume the whole log while normal reads stay capped."""
        with tempfile.TemporaryDirectory() as directory:
            log = HistoryLog(Path(directory) / "history.jsonl", limit=2)
            start = datetime(2026, 8, 1, tzinfo=UTC)
            for index in range(5):
                log.append(
                    ended(
                        start + timedelta(days=index),
                        str(index),
                        f"Station {index}",
                        "FM 90.1",
                        60,
                    )
                )

            self.assertEqual(len(log.read()), 2)
            self.assertEqual(len(log.read_all()), 5)
            self.assertEqual(len(log.summarize_all()), 5)

    def test_report_uses_vertical_charts_and_fills_a_wide_page(self) -> None:
        """Charts rise vertically, avoid divider rules, and use the full width."""
        translator = LocaleRepository.from_directory(
            Path("locales"), "en"
        ).translator("en")
        report = build_listening_statistics(
            (
                ended(
                    datetime(2026, 8, 30, 7, tzinfo=UTC),
                    "a",
                    "Alpha",
                    "FM 90.1",
                    120,
                ),
                ended(
                    datetime(2026, 8, 29, 18, tzinfo=UTC),
                    "b",
                    "Bravo",
                    "AM 1000",
                    60,
                ),
            ),
            today=date(2026, 8, 30),
            timezone=UTC,
        )

        rendered = render_listening_statistics(
            report,
            translator,
            width=120,
        )
        lines = rendered.splitlines()

        self.assertIn("Alpha", rendered)
        self.assertIn("█", rendered)
        self.assertIn("FM", rendered)
        self.assertIn("14-day trend", rendered)
        self.assertNotIn("═", rendered)
        self.assertNotRegex(rendered, "[▁▂▃▄▅▆▇]")
        self.assertEqual(rendered.count("┌"), 6)
        self.assertEqual(rendered.count("└"), 6)
        self.assertIn("┄", rendered)
        self.assertIn("┆", rendered)
        self.assertEqual(max(cell_len(line) for line in lines), 120)
        self.assertTrue(
            any(
                "Listening by weekday" in line
                and "Listening by time of day" in line
                and "Band share" in line
                for line in lines
            )
        )
        for label in ("Mon", "Wed", "Sun", "Afternoon", "Night", "AM"):
            self.assertIn(label, rendered)

        ranking_border = next(
            index for index, line in enumerate(lines) if "Top 10 stations" in line
        )
        first_bar = next(
            index
            for index, line in enumerate(lines[ranking_border + 1 :], ranking_border + 1)
            if "█" in line
        )
        value_row = "\n".join(lines[ranking_border + 1 : first_bar])
        self.assertIn("00:02:00", value_row)
        self.assertIn("00:01:00", value_row)

        axis_index = next(
            index
            for index, line in enumerate(lines[ranking_border + 1 :], ranking_border + 1)
            if "01" in line and "02" in line and ":" not in line
        )
        bar_rows = lines[max(0, axis_index - 8) : axis_index]
        occupied_columns = [
            {index for index, character in enumerate(line) if character == "█"}
            for line in bar_rows
        ]
        self.assertTrue(
            any(
                upper & lower
                for upper, lower in zip(
                    occupied_columns,
                    occupied_columns[1:],
                    strict=False,
                )
            )
        )

    def test_narrow_report_stacks_panels_without_overflow(self) -> None:
        """Compact terminals keep every chart inside the available width."""
        translator = LocaleRepository.from_directory(
            Path("locales"), "zh-Hant"
        ).translator("zh-Hant")
        report = build_listening_statistics(
            (
                ended(
                    datetime(2026, 8, 30, 7, tzinfo=UTC),
                    "a",
                    "警察廣播電臺",
                    "FM 90.1",
                    120,
                ),
            ),
            today=date(2026, 8, 30),
            timezone=UTC,
        )

        rendered = render_listening_statistics(
            report,
            translator,
            width=54,
        )

        self.assertLessEqual(
            max(cell_len(line) for line in rendered.splitlines()),
            54,
        )
        headings = [
            line
            for line in rendered.splitlines()
            if any(
                title in line
                for title in ("每週收聽分布", "時段分布", "波段占比")
            )
        ]
        self.assertEqual(len(headings), 3)

    def test_report_scales_chart_height_with_the_viewport(self) -> None:
        """A taller statistics page receives taller vertical columns."""
        self.assertIn(
            "height",
            signature(render_listening_statistics).parameters,
            "renderer must accept the available viewport height",
        )
        translator = LocaleRepository.from_directory(
            Path("locales"), "en"
        ).translator("en")
        report = build_listening_statistics(
            (
                ended(
                    datetime(2026, 8, 30, 7, tzinfo=UTC),
                    "a",
                    "Alpha",
                    "FM 90.1",
                    120,
                ),
            ),
            today=date(2026, 8, 30),
            timezone=UTC,
        )

        compact = render_listening_statistics(
            report, translator, width=100, height=26
        )
        tall = render_listening_statistics(
            report, translator, width=100, height=46
        )

        self.assertGreater(tall.count("█"), compact.count("█"))


if __name__ == "__main__":
    unittest.main()

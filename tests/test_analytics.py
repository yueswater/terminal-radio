"""Listening statistics and terminal chart tests."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

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

    def test_ascii_report_contains_multiple_chart_styles(self) -> None:
        """The statistics page includes ranking bars, a sparkline, and shares."""
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

        rendered = render_listening_statistics(report, translator, width=88)

        self.assertIn("Alpha", rendered)
        self.assertIn("█", rendered)
        self.assertRegex(rendered, "[▁▂▃▄▅▆▇█]")
        self.assertIn("FM", rendered)
        self.assertIn("14-day trend", rendered)


if __name__ == "__main__":
    unittest.main()

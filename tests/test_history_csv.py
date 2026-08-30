"""Localized listening-history CSV export tests."""

from __future__ import annotations

import csv
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from terminal_radio.services import StationSummary, history_csv_filename, write_history_csv


class HistoryCsvTests(unittest.TestCase):
    def test_export_uses_supplied_language_headers_and_utf8_bom(self) -> None:
        """Spreadsheet fields follow the active locale and preserve Unicode."""
        headers = ("頻率", "電台", "次數", "收聽時間", "暫停時間", "最後收聽")
        summary = StationSummary(
            station_slug="alpha",
            station_name="測試, 電台",
            station_dial="FM 90.1",
            play_count=2,
            listened_seconds=3661,
            paused_seconds=2,
            last_played_at=datetime(2026, 8, 30, 8, 0, tzinfo=UTC),
        )

        with tempfile.TemporaryDirectory() as directory:
            target = write_history_csv(
                Path(directory),
                (summary,),
                headers,
                filename="history_test.csv",
            )

            self.assertTrue(target.read_bytes().startswith(b"\xef\xbb\xbf"))
            with target.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))

        self.assertEqual(tuple(rows[0]), headers)
        self.assertEqual(rows[1][1], "測試, 電台")
        self.assertEqual(rows[1][3], "01:01:01")
        self.assertEqual(rows[1][4], "00:00:02")
        self.assertEqual(rows[1][5], "2026-08-30T08:00:00+00:00")

    def test_filename_is_timestamped_csv(self) -> None:
        self.assertEqual(
            history_csv_filename(datetime(2026, 8, 30, 18, 30, 5, 123000)),
            "history_20260830_183005_123.csv",
        )


if __name__ == "__main__":
    unittest.main()

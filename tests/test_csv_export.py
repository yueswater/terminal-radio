"""Localized CSV export tests: the two shapes, and the writer under them."""

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
        # Local time, the same reading the History table gives. A listener
        # opening their own export should not have to convert from UTC to
        # work out when they were listening.
        self.assertEqual(
            rows[1][5],
            datetime(2026, 8, 30, 8, 0, tzinfo=UTC)
            .astimezone()
            .isoformat(timespec="seconds"),
        )

    def test_filename_is_timestamped_csv(self) -> None:
        self.assertEqual(
            history_csv_filename(datetime(2026, 8, 30, 18, 30, 5, 123000)),
            "history_20260830_183005_123.csv",
        )


if __name__ == "__main__":
    unittest.main()


class NowPlayingCsvTests(unittest.TestCase):
    """The track log export, which shares its writer with the history one."""

    def _entry(self, title: str = "Coldplay - Yellow") -> "NowPlayingEntry":
        from terminal_radio.models.now_playing import NowPlayingEntry

        return NowPlayingEntry(
            at=datetime(2026, 8, 31, 13, 5, 0, tzinfo=UTC),
            station_slug="icrt",
            station_name="ICRT",
            title=title,
        )

    def test_the_columns_are_the_time_the_station_and_the_title(self) -> None:
        from terminal_radio.services import write_now_playing_csv

        headers = ("時間", "電台", "曲目")
        with tempfile.TemporaryDirectory() as directory:
            target = write_now_playing_csv(
                Path(directory),
                (self._entry(),),
                headers,
                filename="tracks_test.csv",
            )
            with target.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))

        self.assertEqual(tuple(rows[0]), headers)
        self.assertEqual(rows[1][1], "ICRT")
        self.assertEqual(rows[1][2], "Coldplay - Yellow")

    def test_a_comma_in_a_title_survives_the_round_trip(self) -> None:
        from terminal_radio.services import write_now_playing_csv

        with tempfile.TemporaryDirectory() as directory:
            target = write_now_playing_csv(
                Path(directory),
                (self._entry("Earth, Wind & Fire - September"),),
                ("Time", "Station", "Title"),
                filename="tracks_test.csv",
            )
            with target.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))

        self.assertEqual(rows[1][2], "Earth, Wind & Fire - September")

    def test_the_spreadsheet_is_told_its_encoding(self) -> None:
        from terminal_radio.services import write_now_playing_csv

        with tempfile.TemporaryDirectory() as directory:
            target = write_now_playing_csv(
                Path(directory),
                (self._entry("周杰倫 - 稻香"),),
                ("時間", "電台", "曲目"),
                filename="tracks_test.csv",
            )

            self.assertTrue(target.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_the_filename_is_stamped_and_distinct_from_the_history_one(self) -> None:
        from terminal_radio.services import now_playing_csv_filename

        self.assertEqual(
            now_playing_csv_filename(datetime(2026, 8, 30, 18, 30, 5, 123000)),
            "tracks_20260830_183005_123.csv",
        )


class CsvWriterTests(unittest.TestCase):
    """The mechanism, apart from anything that uses it."""

    def test_a_filename_cannot_escape_the_folder_it_was_aimed_at(self) -> None:
        from terminal_radio.core.exceptions import RadioError
        from terminal_radio.services import write_csv

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RadioError):
                write_csv(Path(directory), ("a",), [], "../escaped.csv")

    def test_no_half_written_file_is_left_behind(self) -> None:
        """A row that cannot be written must not leave a plausible export."""
        from terminal_radio.core.exceptions import RadioError
        from terminal_radio.services import write_csv

        class Exploding:
            def __iter__(self):
                yield ("fine",)
                raise OSError("disk went away")

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RadioError):
                write_csv(Path(directory), ("a",), Exploding(), "out.csv")

            self.assertEqual(list(Path(directory).iterdir()), [])

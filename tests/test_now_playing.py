"""The station timeline: what was announced, deduplicated and kept in bounds."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from textual.widgets import TabbedContent

from terminal_radio.constants.tui import HISTORY_TAB, HOME_TAB
from terminal_radio.core.config import Settings
from terminal_radio.enums import Band
from terminal_radio.models import Station
from terminal_radio.models.now_playing import NowPlayingEntry
from terminal_radio.services import HistoryLog, RadioService, StateStore, StationCatalog
from terminal_radio.services.now_playing import NowPlayingLog, normalize_title

ALPHA = Station(
    slug="alpha", name="Alpha", band=Band.FM, frequency="99.9", url="https://a/live"
)
BETA = Station(
    slug="beta", name="Beta", band=Band.FM, frequency="88.1", url="https://b/live"
)


class TitleNormalizationTests(unittest.TestCase):
    def test_runs_of_whitespace_collapse(self) -> None:
        self.assertEqual(
            normalize_title("  Coldplay   -   Yellow  "), "Coldplay - Yellow"
        )


class NowPlayingLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "now-playing.jsonl"
        self.log = NowPlayingLog(self.path)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_a_title_is_recorded_and_read_back_newest_first(self) -> None:
        self.log.record(ALPHA, "First")
        self.log.record(ALPHA, "Second")

        self.assertEqual(
            [item.title for item in self.log.read()], ["Second", "First"]
        )

    def test_a_repeated_title_is_not_written_twice(self) -> None:
        """A reconnect makes the station announce what was already playing."""
        self.log.record(ALPHA, "Yellow")
        self.log.record(ALPHA, "Yellow")
        self.log.record(ALPHA, "  Yellow  ")

        self.assertEqual(len(self.log.read()), 1)

    def test_two_stations_do_not_silence_each_other(self) -> None:
        self.log.record(ALPHA, "Yellow")
        self.log.record(BETA, "Yellow")

        self.assertEqual(
            [item.station_slug for item in self.log.read()], ["beta", "alpha"]
        )

    def test_the_same_title_returns_after_the_repeat_window(self) -> None:
        """A song genuinely played twice in an evening is two entries."""
        self.log.record(ALPHA, "Yellow")
        self.log.record(ALPHA, "Clocks")
        self.log.record(ALPHA, "Yellow")

        self.assertEqual(
            [item.title for item in self.log.read()], ["Yellow", "Clocks", "Yellow"]
        )

    def test_an_empty_title_is_not_recorded(self) -> None:
        self.assertIsNone(self.log.record(ALPHA, "   "))
        self.assertEqual(self.log.read(), ())

    def test_a_limit_returns_only_the_newest(self) -> None:
        for index in range(5):
            self.log.record(ALPHA, f"Track {index}")

        self.assertEqual(
            [item.title for item in self.log.read(2)], ["Track 4", "Track 3"]
        )

    def test_a_corrupt_line_is_skipped_rather_than_fatal(self) -> None:
        self.log.record(ALPHA, "Good")
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write("{ not json\n")

        self.assertEqual([item.title for item in self.log.read()], ["Good"])

    def test_clearing_removes_everything(self) -> None:
        self.log.record(ALPHA, "Yellow")

        self.assertTrue(self.log.clear())
        self.assertEqual(self.log.read(), ())

    def test_an_unwritable_location_is_survived(self) -> None:
        """A log that cannot be written must not take playback down with it."""
        log = NowPlayingLog(Path(self.directory.name) / "missing" / "x" / "n.jsonl")
        log._path.parent.mkdir(parents=True)
        log._path.parent.chmod(0o500)
        try:
            self.assertIsNone(log.record(ALPHA, "Yellow"))
        finally:
            log._path.parent.chmod(0o700)


class RetentionTests(unittest.TestCase):
    def test_entries_past_the_window_are_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "now-playing.jsonl"
            now = datetime.now(UTC)
            written = (
                NowPlayingEntry(
                    at=now - timedelta(days=40), station_slug="alpha",
                    station_name="Alpha", title="Ancient",
                ),
                NowPlayingEntry(
                    at=now - timedelta(days=1), station_slug="alpha",
                    station_name="Alpha", title="Recent",
                ),
            )
            path.write_text(
                "".join(item.model_dump_json() + "\n" for item in written),
                encoding="utf-8",
            )
            log = NowPlayingLog(path, retention_days=30)

            self.assertEqual(log.trim(), 1)
            self.assertEqual([item.title for item in log.read()], ["Recent"])

    def test_trimming_nothing_leaves_the_file_alone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = NowPlayingLog(Path(directory) / "n.jsonl", retention_days=30)
            log.record(ALPHA, "Fresh")

            self.assertEqual(log.trim(), 0)
            self.assertEqual(len(log.read()), 1)


class AnnouncingPlayer:
    """A backend that hands over titles the way the IPC thread collects them."""

    def __init__(self) -> None:
        self.queued: list[str] = []
        self.running = False

    def queue(self, *titles: str) -> None:
        self.queued.extend(titles)

    def fade_out(self, seconds: float) -> None:
        self.faded = seconds

    def drain_program_changes(self) -> tuple[str, ...]:
        drained, self.queued = tuple(self.queued), []
        return drained

    @property
    def is_running(self) -> bool:
        return self.running

    @property
    def is_paused(self) -> bool:
        return False

    def start(self, url: str) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def set_paused(self, paused: bool) -> None:
        pass

    @property
    def volume(self) -> int:
        return 100

    def set_volume(self, volume: int) -> None:
        pass

    @property
    def is_muted(self) -> bool:
        return False

    def set_muted(self, muted: bool) -> None:
        pass

    def program(self) -> str | None:
        return None

    def device(self) -> str | None:
        return None


class ServiceRecordingTests(unittest.TestCase):
    """Draining happens on the same status call the interface already makes."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.player = AnnouncingPlayer()
        self.log = NowPlayingLog(root / "now-playing.jsonl")
        self.service = RadioService(
            catalog=StationCatalog([ALPHA, BETA]),
            player=self.player,
            history=HistoryLog(root / "history.jsonl"),
            state=StateStore(root / "state.json"),
            autoplay_last_station=False,
            now_playing=self.log,
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_titles_are_attributed_to_the_station_that_was_playing(self) -> None:
        self.service.play("alpha")
        self.player.queue("Coldplay - Yellow")
        self.service.status()

        entries = self.service.now_playing()

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].station_slug, "alpha")
        self.assertEqual(entries[0].title, "Coldplay - Yellow")

    def test_every_title_is_kept_even_between_two_status_calls(self) -> None:
        """A title that only lasted a moment is still part of the timeline."""
        self.service.play("alpha")
        self.player.queue("First", "Second", "Third")

        self.service.status()

        self.assertEqual(
            [item.title for item in self.service.now_playing()],
            ["Third", "Second", "First"],
        )

    def test_nothing_is_recorded_before_a_station_is_playing(self) -> None:
        self.player.queue("Orphan")

        self.service.status()

        self.assertEqual(self.service.now_playing(), ())

    def test_a_service_without_a_log_still_reports_playback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = RadioService(
                catalog=StationCatalog([ALPHA]),
                player=AnnouncingPlayer(),
                history=HistoryLog(root / "history.jsonl"),
                state=StateStore(root / "state.json"),
                autoplay_last_station=False,
            )
            service.play("alpha")

            self.assertEqual(service.now_playing(), ())
            self.assertFalse(service.clear_now_playing())

    def test_the_log_is_separate_from_the_listening_history(self) -> None:
        """Two files, because they answer two different questions."""
        self.service.play("alpha")
        self.player.queue("Yellow")
        self.service.status()
        self.service.stop()

        history = json.loads(
            (Path(self.directory.name) / "history.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )

        self.assertNotIn("title", history)
        self.assertEqual(len(self.service.now_playing()), 1)


class ConsoleOutputTests(unittest.TestCase):
    """What the console prints for the station on air right now."""

    def _status(self, **overrides: object) -> dict[str, object]:
        status: dict[str, object] = {
            "state": "playing",
            "station": {"name": "ICRT", "dial": "FM 100.7"},
            "program": "Coldplay - Yellow",
            "volume": 100,
            "elapsed_seconds": 42.0,
        }
        status.update(overrides)
        return status

    def test_the_station_and_the_title_are_two_lines(self) -> None:
        from terminal_radio.cli import _format_now

        self.assertEqual(
            _format_now(self._status()), "ICRT FM 100.7\nColdplay - Yellow"
        )

    def test_a_station_announcing_nothing_still_names_itself(self) -> None:
        from terminal_radio.cli import _format_now

        self.assertEqual(_format_now(self._status(program=None)), "ICRT FM 100.7")

    def test_nothing_playing_has_nothing_to_show(self) -> None:
        from terminal_radio.cli import _format_now

        self.assertIsNone(_format_now(self._status(station=None, state="stopped")))

    def test_the_summary_marks_the_title_as_one(self) -> None:
        """Two bare lines in a row read as one wrapped station name."""
        from terminal_radio.cli import _format_status

        self.assertIn("♪ Coldplay - Yellow", _format_status(self._status()))

    def test_the_summary_survives_a_stopped_radio(self) -> None:
        from terminal_radio.cli import _format_status

        summary = _format_status({"state": "stopped", "volume": 0})

        self.assertIn("STOPPED", summary)


class TitleFilterTests(unittest.TestCase):
    """What mpv calls a title is often the name of the file it is fetching."""

    def _player(self, url: str = "https://stream.example/live/PBS/playlist.m3u8"):
        from terminal_radio.services.player import MpvPlayer

        player = MpvPlayer(("mpv",), Path("/tmp/unused.sock"))
        player._url_basename = url.rsplit("/", 1)[-1]
        return player

    def test_a_playlist_name_is_not_a_programme(self) -> None:
        """The bug: a station with no metadata announced playlist.m3u8."""
        player = self._player()
        player._media_title = "playlist.m3u8"

        self.assertIsNone(player.program())

    def test_a_playlist_name_is_rejected_before_the_filename_arrives(self) -> None:
        """mpv reports the title and the filename separately, title first."""
        player = self._player()
        player._media_title = "playlist.m3u8"
        player._filename = None

        self.assertIsNone(player.program())

    def test_a_stream_identifier_is_not_a_programme(self) -> None:
        player = self._player("https://n03.rcs.revma.com/ndk05tyy2tzuv")
        player._media_title = "ndk05tyy2tzuv"

        self.assertIsNone(player.program())

    def test_the_last_part_of_the_address_is_not_a_programme(self) -> None:
        player = self._player("https://example.com/live/taipei")
        player._media_title = "taipei"

        self.assertIsNone(player.program())

    def test_the_whole_address_is_not_a_programme(self) -> None:
        """A station whose address ends in a slash reports the URL itself."""
        player = self._player("http://211.20.119.101:8081/")
        player._media_title = "http://211.20.119.101:8081/"

        self.assertIsNone(player.program())

    def test_a_real_title_survives_every_filter(self) -> None:
        for title in (
            "Coldplay - Yellow",
            "周杰倫 - 稻香",
            "鄭弘儀主持《寶島全世界》",
            "R.E.M. - Losing My Religion",
        ):
            with self.subTest(title=title):
                player = self._player()
                player._icy_title = title

                self.assertEqual(player.program(), title)

    def test_a_title_the_station_sends_beats_the_media_title(self) -> None:
        player = self._player()
        player._media_title = "playlist.m3u8"
        player._icy_title = "Coldplay - Yellow"

        self.assertEqual(player.program(), "Coldplay - Yellow")

    def test_junk_is_never_announced(self) -> None:
        """Nothing filtered out of program() may reach the log either."""
        player = self._player()
        player._media_title = "playlist.m3u8"
        player._announce()

        self.assertEqual(player.drain_program_changes(), ())


class TitleTidyingTests(unittest.TestCase):
    """Some stations prefix a real title with a separator."""

    def test_a_leading_separator_is_dropped(self) -> None:
        from terminal_radio.services.player import tidy_title

        self.assertEqual(tidy_title(" - 晚安FUN音樂〔週一〕- A"), "晚安FUN音樂〔週一〕- A")

    def test_the_trailing_end_is_left_alone(self) -> None:
        """What looks like noise there is the station's own format."""
        from terminal_radio.services.player import tidy_title

        self.assertEqual(tidy_title("薛凱琪 / 方大同 - 復刻回憶"), "薛凱琪 / 方大同 - 復刻回憶")

    def test_a_title_that_is_only_punctuation_is_nothing(self) -> None:
        from terminal_radio.services.player import tidy_title

        self.assertEqual(tidy_title(" - · "), "")


class LiveTableTests(unittest.IsolatedAsyncioTestCase):
    """A log that grows while its table is on screen reloads it."""

    def _app(self, directory: str):
        from terminal_radio.core.i18n import LocaleRepository
        from terminal_radio.services import NowPlayingLog, ThemeRepository
        from terminal_radio.tui.app import RadioApp

        settings = Settings(
            data_dir=Path(directory),
            autoplay_last_station=False,
            status_refresh_seconds=60,
        )
        service = RadioService(
            catalog=StationCatalog.from_file(settings.stations_file),
            player=AnnouncingPlayer(),
            history=HistoryLog(settings.history_file),
            state=StateStore(settings.state_file),
            autoplay_last_station=False,
            now_playing=NowPlayingLog(settings.now_playing_file),
        )
        app = RadioApp(
            service,
            ThemeRepository.from_file(settings.themes_file),
            LocaleRepository.from_directory(settings.locales_dir, settings.locale),
            settings,
        )
        return app, service

    async def test_a_title_announced_while_watching_appears(self) -> None:
        from terminal_radio.tui.widgets import NowPlayingTable

        with tempfile.TemporaryDirectory() as directory:
            app, service = self._app(directory)
            async with app.run_test(size=(160, 48)) as pilot:
                app.query_one(TabbedContent).active = "tab-now-playing"
                await pilot.pause()
                await pilot.pause()
                table = app.query_one("#now-playing-log", NowPlayingTable)
                self.assertEqual(table.row_count, 0)

                service.play("icrt")
                service._player.queue("Coldplay - Yellow")
                service.status()
                app.sync_open_log()
                await pilot.pause()

                self.assertEqual(table.row_count, 1)

    async def test_a_finished_play_reaches_the_history_table(self) -> None:
        from terminal_radio.tui.widgets import HistoryTable

        with tempfile.TemporaryDirectory() as directory:
            app, service = self._app(directory)
            async with app.run_test(size=(160, 48)) as pilot:
                app.query_one(TabbedContent).active = HISTORY_TAB
                await pilot.pause()
                await pilot.pause()
                table = app.query_one(HistoryTable)
                self.assertEqual(table.row_count, 0)

                service.play("icrt")
                service.stop()
                app.sync_open_log()
                await pilot.pause()

                self.assertEqual(table.row_count, 1)

    async def test_an_unchanged_log_is_not_redrawn(self) -> None:
        """Rebuilding a table every second would drag the cursor about."""
        from terminal_radio.tui.widgets import NowPlayingTable

        with tempfile.TemporaryDirectory() as directory:
            app, _ = self._app(directory)
            async with app.run_test(size=(160, 48)) as pilot:
                app.query_one(TabbedContent).active = "tab-now-playing"
                await pilot.pause()
                await pilot.pause()

                drawn = []
                table = app.query_one("#now-playing-log", NowPlayingTable)
                original = table.show
                table.show = lambda entries: (drawn.append(entries), original(entries))[1]

                for _ in range(5):
                    app.sync_open_log()
                await pilot.pause()

                self.assertEqual(drawn, [])

    async def test_the_cursor_stays_where_the_listener_left_it(self) -> None:
        """New titles arrive at the top; the row being read must not slide."""
        from terminal_radio.services import NowPlayingLog
        from terminal_radio.tui.widgets import NowPlayingTable

        with tempfile.TemporaryDirectory() as directory:
            app, service = self._app(directory)
            log = NowPlayingLog(Settings(data_dir=Path(directory)).now_playing_file)
            for title in ("First", "Second", "Third"):
                log.record(service.get_station("icrt"), title)

            async with app.run_test(size=(160, 48)) as pilot:
                app.query_one(TabbedContent).active = "tab-now-playing"
                await pilot.pause()
                await pilot.pause()
                table = app.query_one("#now-playing-log", NowPlayingTable)
                table.move_cursor(row=2)
                await pilot.pause()
                held = table.selected_entry

                service.play("icrt")
                service._player.queue("Fourth")
                service.status()
                app.sync_open_log()
                await pilot.pause()

                self.assertEqual(table.row_count, 4)
                self.assertEqual(table.selected_entry, held)

    async def test_only_the_tab_in_front_is_reloaded(self) -> None:
        from terminal_radio.tui.widgets import NowPlayingTable

        with tempfile.TemporaryDirectory() as directory:
            app, service = self._app(directory)
            async with app.run_test(size=(160, 48)) as pilot:
                app.query_one(TabbedContent).active = HOME_TAB
                await pilot.pause()

                service.play("icrt")
                service._player.queue("Coldplay - Yellow")
                service.status()
                app.sync_open_log()
                await pilot.pause()

                table = app.query_one("#now-playing-log", NowPlayingTable)
                self.assertEqual(table.row_count, 0)

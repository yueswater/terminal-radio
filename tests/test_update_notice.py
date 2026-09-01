"""Noticing a newer release, telling the listener at most three times, and
knowing how to fetch it."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from terminal_radio.constants.update import UPDATE_NOTICE_LIMIT
from terminal_radio.core.config import Settings
from terminal_radio.services import HistoryLog, RadioService, StateStore, StationCatalog
from terminal_radio.services.update import (
    Installation,
    describe_installation,
    is_newer,
    latest_release,
    parse_version,
)


class MemoryPlayer:
    """Stand-in backend, enough for a service to be built around."""

    @property
    def is_running(self) -> bool:
        return False

    @property
    def is_paused(self) -> bool:
        return False

    def start(self, url: str) -> None:
        pass

    def stop(self) -> None:
        pass

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

    def fade_out(self, seconds: float) -> None:
        pass

    def drain_program_changes(self) -> tuple[str, ...]:
        return ()


class VersionComparisonTests(unittest.TestCase):
    def test_a_later_patch_release_counts(self) -> None:
        """0.3.0 to 0.3.1 is exactly the case this feature exists for."""
        self.assertTrue(is_newer("0.3.1", "0.3.0"))

    def test_numbers_are_compared_as_numbers(self) -> None:
        """As text, 0.3.10 sorts before 0.3.9."""
        self.assertTrue(is_newer("0.3.10", "0.3.9"))

    def test_the_same_version_is_not_newer(self) -> None:
        self.assertFalse(is_newer("0.3.0", "0.3.0"))

    def test_an_older_version_is_not_newer(self) -> None:
        self.assertFalse(is_newer("0.3.0", "0.3.1"))

    def test_missing_segments_count_as_zero(self) -> None:
        self.assertTrue(is_newer("0.4", "0.3.9"))
        self.assertFalse(is_newer("0.3", "0.3.0"))

    def test_a_prerelease_is_never_announced(self) -> None:
        """Somebody on a stable version is not sent to a candidate."""
        self.assertFalse(is_newer("0.4.0rc1", "0.3.0"))
        self.assertIsNone(parse_version("0.4.0rc1"))

    def test_nonsense_is_not_a_version(self) -> None:
        self.assertIsNone(parse_version("latest"))
        self.assertIsNone(parse_version(""))


class LatestReleaseTests(unittest.TestCase):
    def test_the_index_answer_is_read(self) -> None:
        class Response:
            def read(self, *_: object) -> bytes:
                return b'{"info": {"version": "9.9.9"}}'

            def __enter__(self) -> "Response":
                return self

            def __exit__(self, *_: object) -> None:
                return None

        with patch("terminal_radio.services.update.urllib.request.urlopen", return_value=Response()):
            self.assertEqual(latest_release("radiotui-tw"), "9.9.9")

    def test_being_offline_is_not_an_error(self) -> None:
        """A listener opening a radio is not told the version check failed."""
        with patch(
            "terminal_radio.services.update.urllib.request.urlopen",
            side_effect=OSError("no route to host"),
        ):
            self.assertIsNone(latest_release("radiotui-tw"))

    def test_an_unexpected_answer_is_not_an_error(self) -> None:
        class Response:
            def read(self, *_: object) -> bytes:
                return b"<html>maintenance</html>"

            def __enter__(self) -> "Response":
                return self

            def __exit__(self, *_: object) -> None:
                return None

        with patch("terminal_radio.services.update.urllib.request.urlopen", return_value=Response()):
            self.assertIsNone(latest_release("radiotui-tw"))


class InstallationTests(unittest.TestCase):
    """How to upgrade is read off the installation, not guessed."""

    def _distribution(self, location: str, direct_url: str | None = None):
        class Fake:
            version = "0.3.0"

            @staticmethod
            def read_text(name: str) -> str | None:
                return direct_url if name == "direct_url.json" else None

            @staticmethod
            def locate_file(_name: str) -> str:
                return location

        return Fake()

    def _describe(self, location: str, direct_url: str | None = None, tools=("uv", "pipx")):
        with patch(
            "terminal_radio.services.update.Distribution.from_name",
            return_value=self._distribution(location, direct_url),
        ), patch(
            "terminal_radio.services.update.shutil.which",
            side_effect=lambda name: f"/usr/bin/{name}" if name in tools else None,
        ):
            return describe_installation("radiotui-tw")

    def test_a_uv_tool_install_is_upgraded_with_uv(self) -> None:
        found = self._describe(
            "/home/me/.local/share/uv/tools/radiotui-tw/lib/python3.12/site-packages"
        )

        self.assertEqual(
            found.upgrade_command, ("uv", "tool", "upgrade", "radiotui-tw")
        )

    def test_a_pipx_install_is_upgraded_with_pipx(self) -> None:
        found = self._describe(
            "/home/me/.local/pipx/venvs/radiotui-tw/lib/python3.12/site-packages"
        )

        self.assertEqual(found.upgrade_command, ("pipx", "upgrade", "radiotui-tw"))

    def test_a_checkout_is_never_upgraded_from_inside(self) -> None:
        """Upgrading a working copy means git, and is not ours to do."""
        found = self._describe(
            "/home/me/terminal-radio/.venv/lib/python3.12/site-packages",
            direct_url=json.dumps(
                {"url": "file:///home/me/terminal-radio", "dir_info": {"editable": True}}
            ),
        )

        self.assertFalse(found.upgradable)
        self.assertTrue(found.editable)
        self.assertEqual(
            found.manual_command,
            ("git", "-C", "/home/me/terminal-radio", "pull", "--ff-only"),
        )

    def test_an_install_we_cannot_name_offers_nothing(self) -> None:
        """Better to say so than to run a command that may be wrong."""
        found = self._describe("/usr/lib/python3.12/site-packages")

        self.assertFalse(found.upgradable)
        self.assertFalse(found.editable)

    def test_a_manager_that_is_not_installed_is_not_offered(self) -> None:
        """The directory names uv, but this machine has no uv to run."""
        found = self._describe(
            "/home/me/.local/share/uv/tools/radiotui-tw/lib/python3.12/site-packages",
            tools=(),
        )

        self.assertFalse(found.upgradable)


class UpdateNoticeTests(unittest.TestCase):
    """The service decides whether to speak, and counts how often it has."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings = Settings(data_dir=Path(self.directory.name))
        self.service = self._service()

    def _service(self, **overrides: object) -> RadioService:
        return RadioService(
            catalog=StationCatalog.from_file(self.settings.stations_file),
            player=MemoryPlayer(),
            history=HistoryLog(self.settings.history_file),
            state=StateStore(self.settings.state_file),
            autoplay_last_station=False,
            **overrides,
        )

    def _check(self, current: str = "0.3.0", latest: str | None = "0.3.1", **kwargs):
        with patch(
            "terminal_radio.services.radio.latest_release", return_value=latest
        ):
            return self.service.check_for_update(current, **kwargs)

    def test_a_newer_release_is_announced(self) -> None:
        self.assertEqual(self._check(), "0.3.1")

    def test_the_current_release_is_not_announced(self) -> None:
        self.assertIsNone(self._check(current="0.3.1"))

    def test_it_is_announced_three_times_and_then_left_alone(self) -> None:
        """Saying no three times is an answer."""
        shown = 0
        for _ in range(6):
            if self._check() is not None:
                self.service.record_update_notice()
                shown += 1

        self.assertEqual(shown, UPDATE_NOTICE_LIMIT)

    def test_a_newer_release_starts_the_count_again(self) -> None:
        """A version they have not been told about is a fresh notice."""
        for _ in range(UPDATE_NOTICE_LIMIT):
            self._check()
            self.service.record_update_notice()
        self.assertIsNone(self._check())

        self.assertEqual(self._check(latest="0.4.0", now=1e12), "0.4.0")

    def test_the_index_is_asked_once_a_day(self) -> None:
        with patch(
            "terminal_radio.services.radio.latest_release", return_value="0.3.1"
        ) as asked:
            self.service.check_for_update("0.3.0", now=1000.0)
            self.service.check_for_update("0.3.0", now=2000.0)

        self.assertEqual(asked.call_count, 1)

    def test_a_day_later_the_index_is_asked_again(self) -> None:
        with patch(
            "terminal_radio.services.radio.latest_release", return_value="0.3.1"
        ) as asked:
            self.service.check_for_update("0.3.0", now=1000.0)
            self.service.check_for_update("0.3.0", now=1000.0 + 24 * 60 * 60)

        self.assertEqual(asked.call_count, 2)

    def test_a_failed_check_is_retried_rather_than_waiting_out_the_day(self) -> None:
        with patch(
            "terminal_radio.services.radio.latest_release", return_value=None
        ) as asked:
            self.service.check_for_update("0.3.0", now=1000.0)
            self.service.check_for_update("0.3.0", now=1001.0)

        self.assertEqual(asked.call_count, 2)

    def test_upgrading_lets_the_next_release_be_announced(self) -> None:
        """The count is spent against a version, not against the listener.

        Somebody who declined three notices for 0.3.1, installed it anyway, and
        then met 0.3.2 would otherwise never hear about it.
        """
        for _ in range(UPDATE_NOTICE_LIMIT):
            self._check(current="0.3.0", latest="0.3.1")
            self.service.record_update_notice()
        self.assertIsNone(self._check(current="0.3.0", latest="0.3.1"))

        announced = self._check(current="0.3.1", latest="0.3.2")

        self.assertEqual(announced, "0.3.2")

    def test_catching_up_asks_the_index_again_the_same_day(self) -> None:
        """The cached answer was recorded for a version no longer running."""
        with patch(
            "terminal_radio.services.radio.latest_release", return_value="0.3.1"
        ):
            self.service.check_for_update("0.3.0", now=1000.0)

        with patch(
            "terminal_radio.services.radio.latest_release", return_value="0.3.2"
        ) as asked:
            answer = self.service.check_for_update("0.3.1", now=1001.0)

        self.assertEqual(asked.call_count, 1)
        self.assertEqual(answer, "0.3.2")

    def test_being_up_to_date_still_asks_only_once_a_day(self) -> None:
        """Catching up is a reason to re-check, not to check on every launch."""
        with patch(
            "terminal_radio.services.radio.latest_release", return_value="0.3.2"
        ) as asked:
            for _ in range(4):
                self.service.check_for_update("0.3.1", now=1000.0)

        self.assertEqual(asked.call_count, 1)

    def test_the_check_can_be_turned_off(self) -> None:
        service = self._service(check_for_updates=False)

        with patch(
            "terminal_radio.services.radio.latest_release", return_value="9.9.9"
        ) as asked:
            answer = service.check_for_update("0.3.0")

        self.assertIsNone(answer)
        self.assertEqual(asked.call_count, 0)

    def test_the_environment_can_turn_it_off(self) -> None:
        from terminal_radio.core.config import get_settings

        with patch.dict("os.environ", {"RADIO_CHECK_FOR_UPDATES": "0"}):
            get_settings.cache_clear()
            self.addCleanup(get_settings.cache_clear)

            self.assertFalse(get_settings().check_for_updates)


class UpdateScreenTests(unittest.IsolatedAsyncioTestCase):
    """What the listener sees, and what leaving with it does."""

    def _app(self, directory: str):
        from terminal_radio.core.i18n import LocaleRepository
        from terminal_radio.services import ThemeRepository
        from terminal_radio.tui.app import RadioApp

        settings = Settings(
            data_dir=Path(directory),
            autoplay_last_station=False,
            status_refresh_seconds=60,
        )
        service = RadioService(
            catalog=StationCatalog.from_file(settings.stations_file),
            player=MemoryPlayer(),
            history=HistoryLog(settings.history_file),
            state=StateStore(settings.state_file),
            autoplay_last_station=False,
        )
        app = RadioApp(
            service,
            ThemeRepository.from_file(settings.themes_file),
            LocaleRepository.from_directory(settings.locales_dir, settings.locale),
            settings,
        )
        return app, service

    async def test_the_notice_names_both_versions(self) -> None:
        from textual.widgets import Static

        from terminal_radio.tui.screens import UpdateScreen

        with tempfile.TemporaryDirectory() as directory:
            app, _ = self._app(directory)
            async with app.run_test(size=(96, 24)) as pilot:
                await pilot.pause()
                app.push_screen(
                    UpdateScreen(
                        app.t,
                        "0.3.0",
                        "0.3.1",
                        Installation(("uv", "tool", "upgrade", "radiotui-tw")),
                    )
                )
                await pilot.pause()

                title = str(app.screen.query_one("#update-title", Static).render())
                versions = str(app.screen.query_one("#update-versions", Static).render())

                self.assertIn("0.3.1", title)
                self.assertIn("0.3.0", versions)
                self.assertIn("0.3.1", versions)

    async def test_later_leaves_the_radio_running(self) -> None:
        from terminal_radio.tui.screens import UpdateScreen

        with tempfile.TemporaryDirectory() as directory:
            app, _ = self._app(directory)
            async with app.run_test(size=(96, 24)) as pilot:
                await pilot.pause()
                app.push_screen(
                    UpdateScreen(
                        app.t, "0.3.0", "0.3.1", Installation(("uv", "tool", "upgrade", "x"))
                    ),
                    lambda accepted: app.finish_update_offer("0.3.1", accepted),
                )
                await pilot.pause()

                await pilot.click("#update-later")
                await pilot.pause()

                self.assertIsNone(app.pending_upgrade)
                self.assertNotIsInstance(app.screen, UpdateScreen)

    async def test_escape_is_the_same_as_later(self) -> None:
        from terminal_radio.tui.screens import UpdateScreen

        with tempfile.TemporaryDirectory() as directory:
            app, _ = self._app(directory)
            async with app.run_test(size=(96, 24)) as pilot:
                await pilot.pause()
                app.push_screen(
                    UpdateScreen(
                        app.t, "0.3.0", "0.3.1", Installation(("uv", "tool", "upgrade", "x"))
                    ),
                    lambda accepted: app.finish_update_offer("0.3.1", accepted),
                )
                await pilot.pause()

                await pilot.press("escape")
                await pilot.pause()

                self.assertIsNone(app.pending_upgrade)

    async def test_updating_leaves_the_command_for_the_shell(self) -> None:
        """The interface cannot replace the files it is running from."""
        from terminal_radio.tui.screens import UpdateScreen

        command = ("uv", "tool", "upgrade", "radiotui-tw")
        with tempfile.TemporaryDirectory() as directory:
            app, _ = self._app(directory)
            async with app.run_test(size=(96, 24)) as pilot:
                await pilot.pause()
                with patch(
                    "terminal_radio.tui.app.describe_installation",
                    return_value=Installation(command),
                ):
                    app.push_screen(
                        UpdateScreen(app.t, "0.3.0", "0.3.1", Installation(command)),
                        lambda accepted: app.finish_update_offer("0.3.1", accepted),
                    )
                    await pilot.pause()

                    await pilot.click("#update-now")
                    await pilot.pause()

                self.assertEqual(app.pending_upgrade, command)
                self.assertEqual(app.upgrade_version, "0.3.1")

    async def test_a_copy_that_cannot_upgrade_is_told_so_instead(self) -> None:
        from textual.widgets import Static

        from terminal_radio.tui.screens import UpdateScreen

        with tempfile.TemporaryDirectory() as directory:
            app, _ = self._app(directory)
            async with app.run_test(size=(96, 24)) as pilot:
                await pilot.pause()
                app.push_screen(
                    UpdateScreen(
                        app.t,
                        "0.3.0",
                        "0.3.1",
                        Installation(
                            None,
                            editable=True,
                            manual_command=(
                                "git",
                                "-C",
                                "/home/me/terminal-radio",
                                "pull",
                                "--ff-only",
                            ),
                        ),
                    )
                )
                await pilot.pause()

                self.assertFalse(app.screen.query("#update-now"))
                hint = str(app.screen.query_one("#update-hint", Static).render())
                self.assertIn(
                    "git -C /home/me/terminal-radio pull --ff-only",
                    hint,
                )

    async def test_showing_the_notice_uses_one_of_the_three(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app, service = self._app(directory)
            async with app.run_test(size=(96, 24)) as pilot:
                await pilot.pause()
                with patch(
                    "terminal_radio.tui.app.describe_installation",
                    return_value=Installation(None),
                ):
                    app.offer_update("0.3.0", "0.3.1")
                    await pilot.pause()

                stored = service.preferences()
                self.assertEqual(stored.update_notice_count, 1)

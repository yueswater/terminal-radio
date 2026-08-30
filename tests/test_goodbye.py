"""Farewell screen copy, layout and duration regressions."""

from __future__ import annotations

import unittest

from textual.app import App
from textual.widgets import Static

from terminal_radio.constants.config import default_locales_dir
from terminal_radio.core.i18n import LocaleRepository
from terminal_radio.tui.formatting import format_clock
from terminal_radio.tui.screens import GoodbyeScreen


class GoodbyeCopyTests(unittest.TestCase):
    def test_farewell_copy_uses_the_requested_tilde_in_each_language(self) -> None:
        locales = LocaleRepository.from_directory(default_locales_dir(), "zh-Hant")

        self.assertEqual(locales.translator("zh-Hant")("goodbye.title"), "下次見～")
        self.assertEqual(locales.translator("en")("goodbye.title"), "See you~")

    def test_session_duration_always_includes_hours_minutes_and_seconds(self) -> None:
        self.assertEqual(format_clock(0), "00:00:00")
        self.assertEqual(format_clock(65), "00:01:05")
        self.assertEqual(format_clock(3_661), "01:01:01")


class GoodbyeLayoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_farewell_title_is_plain_localized_text(self) -> None:
        locales = LocaleRepository.from_directory(default_locales_dir(), "zh-Hant")

        for code, expected in (("zh-Hant", "下次見～"), ("en", "See you~")):
            with self.subTest(code=code):
                app = App[None]()
                screen = GoodbyeScreen(locales.translator(code), 0, delay=60)
                async with app.run_test(size=(100, 30)) as pilot:
                    await app.push_screen(screen)
                    await pilot.pause()

                    title = screen.query_one("#goodbye-title", Static)
                    self.assertEqual(str(title.render()), expected)

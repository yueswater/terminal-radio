"""Single ownership of the player, and the commands that reach whoever has it."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from terminal_radio.control import ControlClient, ControlError
from terminal_radio.core.config import Settings
from terminal_radio.services.daemon import IdleTimer
from terminal_radio.services.runtime import (
    OwnerLock,
    clear_stale_socket,
    is_owned,
    socket_is_live,
    wait_for_socket,
)


class OwnerLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "control.lock"

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_only_one_holder_at_a_time(self) -> None:
        first, second = OwnerLock(self.path), OwnerLock(self.path)
        self.addCleanup(first.release)

        self.assertTrue(first.acquire())
        self.assertFalse(second.acquire())

    def test_releasing_hands_the_claim_on(self) -> None:
        first, second = OwnerLock(self.path), OwnerLock(self.path)
        self.addCleanup(second.release)
        first.acquire()

        first.release()

        self.assertTrue(second.acquire())

    def test_the_holder_records_which_process_it_is(self) -> None:
        lock = OwnerLock(self.path)
        self.addCleanup(lock.release)
        lock.acquire()

        self.assertEqual(lock.holder_pid(), os.getpid())

    def test_a_dead_holder_leaves_nothing_behind(self) -> None:
        """The kernel drops a flock when its process ends, crash or not."""
        script = (
            "from pathlib import Path;"
            "from terminal_radio.services.runtime import OwnerLock;"
            f"OwnerLock(Path({str(self.path)!r})).acquire()"
        )
        subprocess.run([sys.executable, "-c", script], check=True)

        self.assertFalse(is_owned(self.path))

    def test_nobody_holding_it_is_not_ownership(self) -> None:
        self.assertFalse(is_owned(self.path))


class StaleSocketTests(unittest.TestCase):
    def test_a_socket_nobody_listens_on_is_not_live(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "control.sock"
            path.touch()

            self.assertFalse(socket_is_live(path))

    def test_a_leftover_socket_is_cleared_out_of_the_way(self) -> None:
        """A crash leaves the file behind, and a new owner must be able to bind."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "control.sock"
            path.touch()

            clear_stale_socket(path)

            self.assertFalse(path.exists())


class IdleTimerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = [0.0]
        self.timer = IdleTimer(idle_seconds=300, clock=lambda: self.now[0])

    def test_an_owner_with_nothing_to_do_stands_down(self) -> None:
        self.now[0] = 300

        self.assertTrue(self.timer.expired(playing=False))

    def test_an_owner_still_playing_stays(self) -> None:
        self.now[0] = 10_000

        self.assertFalse(self.timer.expired(playing=True))

    def test_being_asked_something_keeps_it_alive(self) -> None:
        self.now[0] = 299
        self.timer.touch()
        self.now[0] = 500

        self.assertFalse(self.timer.expired(playing=False))


class ControlClientTests(unittest.TestCase):
    def test_reaching_for_a_radio_that_is_not_there_says_so(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = ControlClient(Path(directory) / "control.sock", timeout=1)

            with self.assertRaises(ControlError) as raised:
                client.get("/player")

        self.assertIn("No radio is running", str(raised.exception))


class LiveDaemonTests(unittest.TestCase):
    """A real process, a real socket, real commands over it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        root = Path(cls.directory.name)
        cls.settings = Settings(
            data_dir=root / "state",
            runtime_dir=root / "run",
            autoplay_last_station=False,
        )
        cls.process = subprocess.Popen(
            [sys.executable, "-m", "terminal_radio.cli", "daemon"],
            env={
                **os.environ,
                "RADIO_DATA_DIR": str(root / "state"),
                "RADIO_RUNTIME_DIR": str(root / "run"),
                "RADIO_AUTOPLAY_LAST_STATION": "0",
                # Never spawn a real player: these tests are about the socket.
                "RADIO_PLAYER_COMMAND": "true",
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls.started = wait_for_socket(cls.settings.control_socket, timeout=20)
        cls.client = ControlClient(cls.settings.control_socket)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.process.terminate()
        cls.process.wait(timeout=10)
        cls.directory.cleanup()

    def setUp(self) -> None:
        if not self.started:
            self.skipTest("the daemon did not start")

    def test_the_daemon_answers_on_its_socket(self) -> None:
        self.assertEqual(self.client.get("/player")["state"], "stopped")

    def test_the_socket_is_private_to_the_user(self) -> None:
        mode = self.settings.control_socket.stat().st_mode & 0o777

        self.assertEqual(mode, 0o600)

    def test_a_second_owner_refuses_to_start(self) -> None:
        """The lock is what stops two processes driving two players."""
        self.assertTrue(is_owned(self.settings.control_lock))

    def test_the_volume_can_be_set_and_stepped(self) -> None:
        self.assertEqual(self.client.post("/player/volume", {"level": 40})["volume"], 40)
        self.assertEqual(self.client.post("/player/volume", {"delta": 15})["volume"], 55)

    def test_muting_is_idempotent(self) -> None:
        self.assertTrue(self.client.post("/player/mute", {"muted": True})["muted"])
        self.assertTrue(self.client.post("/player/mute", {"muted": True})["muted"])
        self.assertFalse(self.client.post("/player/mute", {"muted": False})["muted"])

    def test_the_catalog_is_served_with_its_filters(self) -> None:
        answer = self.client.get("/stations", genre="classical")

        self.assertEqual(
            [item["slug"] for item in answer["items"]], ["classical-977"]
        )

    def test_an_unknown_station_is_reported_not_crashed(self) -> None:
        with self.assertRaises(ControlError) as raised:
            self.client.post("/player/play", {"slug": "nope"})

        self.assertIn("nope", str(raised.exception))

    def test_a_rejected_payload_comes_back_as_a_message(self) -> None:
        with self.assertRaises(ControlError):
            self.client.post("/player/sleep", {"minutes": 99_999})

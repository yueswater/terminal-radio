"""Command line entry point of the radio project."""

from __future__ import annotations

import argparse
import sys

from terminal_radio.core.about import get_version
from terminal_radio.core.config import Settings, get_settings
from terminal_radio.constants.about import COMMAND
from terminal_radio.enums import Band, Genre, Region

# Commands that drive a running radio rather than reading a file.
CONTROL_COMMANDS = frozenset(
    {
        "play",
        "pause",
        "resume",
        "stop",
        "volume",
        "mute",
        "unmute",
        "sleep",
        "status",
        "now",
    }
)


def build_parser(settings: Settings) -> argparse.ArgumentParser:
    """Build the argument parser, using settings for the displayed defaults."""
    parser = argparse.ArgumentParser(
        prog=COMMAND,
        description="Terminal radio player. Run without arguments to open the UI.",
    )
    parser.add_argument("--version", action="version", version=get_version())

    commands = parser.add_subparsers(dest="command")

    ui = commands.add_parser("ui", help="Open the terminal UI, the default command")
    ui.add_argument(
        "--no-autoplay",
        action="store_true",
        help="Do not resume the station played during the previous run",
    )

    api = commands.add_parser("api", help="Serve the HTTP control API")
    api.add_argument("--host", default=settings.api_host, help="Address to bind")
    api.add_argument("--port", type=int, default=settings.api_port, help="Port to bind")
    api.add_argument("--reload", action="store_true", help="Restart on code changes")

    stations = commands.add_parser(
        "stations",
        help="Print the station catalog",
        description=(
            "Print the station catalog. A query may name filters as key:value "
            "and free text to rank by, for example: genre:news region:taipei 廣播. "
            "The flags below are shorthand for the same filters."
        ),
    )
    stations.add_argument(
        "query",
        nargs="?",
        default="",
        help="Search query, mixing key:value filters and free text",
    )
    stations.add_argument(
        "--band", choices=[band.value for band in Band], help="Restrict to one band"
    )
    stations.add_argument(
        "--genre",
        action="append",
        choices=[genre.value for genre in Genre],
        help="Restrict to a genre, repeatable to widen",
    )
    stations.add_argument(
        "--region",
        action="append",
        choices=[region.value for region in Region],
        metavar="REGION",
        help="Restrict to a service area, repeatable to widen",
    )
    stations.add_argument(
        "--language",
        action="append",
        metavar="TAG",
        help="Restrict to a BCP 47 language, repeatable to widen",
    )
    stations.add_argument(
        "--network", action="append", help="Restrict to a station family"
    )
    stations.add_argument(
        "--json", action="store_true", help="Print JSON instead of a table"
    )

    daemon = commands.add_parser(
        "daemon",
        help="Run the process that owns the player",
        description=(
            "Own the player and answer commands on the control socket. "
            "Control commands start one of these by themselves when none is "
            "running, so this is rarely typed by hand."
        ),
    )
    daemon.add_argument(
        "action",
        nargs="?",
        default="run",
        choices=["run", "stop", "status"],
        help="Run one in the foreground, stop the running one, or report on it",
    )

    for name, help_text in (
        ("pause", "Pause the loaded station"),
        ("resume", "Resume the paused station"),
        ("stop", "Stop playback"),
        ("mute", "Silence the output"),
        ("unmute", "Bring the output back"),
    ):
        commands.add_parser(name, help=help_text)

    play = commands.add_parser("play", help="Play a station")
    play.add_argument("slug", help="Station slug, as printed by radio stations")

    volume = commands.add_parser("volume", help="Show or set the output volume")
    volume.add_argument(
        "level",
        nargs="?",
        help="A level such as 50, or a step such as +10 or -10. Omit to show it",
    )

    sleep = commands.add_parser("sleep", help="Stop playback after a while")
    sleep.add_argument(
        "minutes",
        nargs="?",
        help="Minutes to play for, or off to cancel. Omit to show the timer",
    )

    status = commands.add_parser("status", help="Print what the radio is doing")
    status.add_argument(
        "--json", action="store_true", help="Print JSON instead of a summary"
    )

    now = commands.add_parser(
        "now",
        help="Print the station and title playing right now",
        description=(
            "Print one line for the station and one for what it says it is "
            "playing. For the whole timeline, see radio now-playing."
        ),
    )
    now.add_argument(
        "--json", action="store_true", help="Print JSON instead of the two lines"
    )

    now = commands.add_parser(
        "now-playing",
        help="Print the titles the stations announced",
        description=(
            "Print what the stations said they were playing, newest first. "
            "The log is written while a radio is running and is read here "
            "straight off disk, so this works whether or not one is."
        ),
    )
    now.add_argument(
        "--limit", type=int, default=20, help="Entries to print, newest first"
    )
    now.add_argument(
        "--station", help="Restrict to one station slug"
    )
    now.add_argument(
        "--json", action="store_true", help="Print JSON instead of a table"
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Dispatch the requested command and return a process exit code."""
    settings = get_settings()
    arguments = build_parser(settings).parse_args(argv)

    match arguments.command:
        case "api":
            return _run_api(arguments.host, arguments.port, arguments.reload)
        case "stations":
            return _print_stations(settings, arguments)
        case "now-playing":
            return _print_now_playing(settings, arguments)
        case "daemon":
            return _run_daemon(settings, arguments.action)
        case command if command in CONTROL_COMMANDS:
            return _run_control(settings, command, arguments)
        case _:
            return _run_ui(settings, no_autoplay=getattr(arguments, "no_autoplay", False))


def _run_ui(settings: Settings, no_autoplay: bool) -> int:
    """Start the terminal UI, which owns the player while it is open."""
    from terminal_radio.core.i18n import LocaleRepository
    from terminal_radio.services import ThemeRepository, build_radio_service
    from terminal_radio.services.daemon import serve_in_background
    from terminal_radio.services.runtime import OwnerLock, unlink_socket
    from terminal_radio.tui.app import RadioApp

    # One process owns the player. Without this a second window would start a
    # second mpv, and both would write the same state file over each other.
    lock = OwnerLock(settings.control_lock)
    if not lock.acquire():
        pid = lock.holder_pid()
        where = f" (process {pid})" if pid else ""
        print(f"A radio is already running{where}.", file=sys.stderr)
        print("Stop it with: radio daemon stop", file=sys.stderr)
        return 1

    if no_autoplay:
        settings = settings.model_copy(update={"autoplay_last_station": False})

    service = build_radio_service(settings)
    try:
        # Control commands typed in another window reach this radio, not a new one.
        serve_in_background(settings, service)
    except OSError:
        pass

    try:
        RadioApp(
            service=service,
            themes=ThemeRepository.from_file(settings.themes_file),
            locales=LocaleRepository.from_directory(
                settings.locales_dir, settings.locale
            ),
            settings=settings,
        ).run()
    finally:
        unlink_socket(settings.control_socket)
        lock.release()
    return 0


def _run_daemon(settings: Settings, action: str) -> int:
    """Run, stop or report on the process that owns the player."""
    from terminal_radio.services.daemon import owner_pid, serve, stop_owner

    match action:
        case "stop":
            if not stop_owner(settings):
                print("No radio is running.", file=sys.stderr)
                return 1
            print("Asked the radio to stop.")
            return 0
        case "status":
            pid = owner_pid(settings)
            if pid is None:
                print("No radio is running.")
                return 1
            print(f"Radio running as process {pid}.")
            print(f"Socket {settings.control_socket}")
            return 0
        case _:
            return serve(settings)


def _run_control(
    settings: Settings, command: str, arguments: argparse.Namespace
) -> int:
    """Send one command to the owner, starting one when there is none."""
    from terminal_radio.control import ControlClient, ControlError
    from terminal_radio.services.runtime import ensure_daemon

    # Asking a question should not conjure a radio out of nothing; asking for
    # something to happen should.
    starts_one = command != "status"
    if starts_one:
        if not ensure_daemon(settings.control_socket, settings.control_lock):
            print("Could not start the radio.", file=sys.stderr)
            return 1

    client = ControlClient(settings.control_socket)
    try:
        status = _dispatch_control(client, command, arguments)
    except ControlError as error:
        print(str(error), file=sys.stderr)
        return 1

    if getattr(arguments, "json", False):
        import json

        print(json.dumps({"schema": 1, **status}, ensure_ascii=False, indent=2))
    elif command == "now":
        line = _format_now(status)
        if line is None:
            print("Nothing is playing.", file=sys.stderr)
            return 1
        print(line)
    else:
        print(_format_status(status))
    return 0


def _dispatch_control(
    client: object, command: str, arguments: argparse.Namespace
) -> dict[str, object]:
    """Turn one command into one request and return the status it answers with."""
    match command:
        case "status" | "now":
            return client.get("/player")  # type: ignore[attr-defined]
        case "play":
            return client.post("/player/play", {"slug": arguments.slug})  # type: ignore[attr-defined]
        case "pause" | "resume" | "stop":
            return client.post(f"/player/{command}")  # type: ignore[attr-defined]
        case "mute" | "unmute":
            return client.post("/player/mute", {"muted": command == "mute"})  # type: ignore[attr-defined]
        case "volume":
            return client.post("/player/volume", _volume_body(arguments.level))  # type: ignore[attr-defined]
        case "sleep":
            return client.post("/player/sleep", _sleep_body(arguments.minutes))  # type: ignore[attr-defined]
    raise ValueError(f"unhandled control command: {command}")


def _volume_body(level: str | None) -> dict[str, object]:
    """Read 50 as a level and +10 or -10 as a step."""
    if level is None:
        return {}
    text = level.strip()
    try:
        if text.startswith(("+", "-")):
            return {"delta": int(text)}
        return {"level": int(text)}
    except ValueError:
        raise SystemExit(f"Not a volume: {level}") from None


def _sleep_body(minutes: str | None) -> dict[str, object]:
    """Read a number of minutes, or off to cancel the timer."""
    if minutes is None:
        return {}
    if minutes.strip().casefold() in {"off", "cancel", "none"}:
        return {"minutes": None}
    try:
        return {"minutes": int(minutes)}
    except ValueError:
        raise SystemExit(f"Not a number of minutes: {minutes}") from None


def _format_now(status: dict[str, object]) -> str | None:
    """Return the station and the title on air, or None when nothing is.

    Two short lines, because this is the answer to "what is this" and is what a
    status bar or a notification will paste in whole.
    """
    station = status.get("station")
    if not isinstance(station, dict):
        return None

    dial = str(station.get("dial", "")).strip()
    name = str(station.get("name", "")).strip()
    heading = f"{name} {dial}".strip()
    title = status.get("program")
    return f"{heading}\n{title}" if title else heading


def _format_status(status: dict[str, object]) -> str:
    """Return the human readable summary printed by every control command."""
    from terminal_radio.tui.formatting import format_clock

    state = str(status.get("state", "stopped"))
    glyph = {"playing": "▶", "paused": "⏸", "stopped": "■", "reconnecting": "↻"}
    lines = [f"{glyph.get(state, '·')} {state.upper()}"]

    station = status.get("station")
    if isinstance(station, dict):
        lines.append("")
        lines.append(str(station.get("name", "")))
        lines.append(str(station.get("dial", "")))
        if program := status.get("program"):
            lines.append(f"♪ {program}")

    lines.append("")
    lines.append(f"Volume   {status.get('volume', 0)}%"
                 + ("  (muted)" if status.get("muted") else ""))
    lines.append(
        f"Elapsed  {format_clock(float(status.get('elapsed_seconds') or 0))}"
    )
    if status.get("using_fallback"):
        lines.append(
            f"Stream   backup {status.get('stream_index')}"
            f" of {status.get('stream_count')}"
        )
    if (remaining := status.get("sleep_remaining_seconds")) is not None:
        lines.append(f"Sleep    {format_clock(float(remaining))}")
    return "\n".join(lines)


def _run_api(host: str, port: int, reload: bool) -> int:
    """Serve the FastAPI application with uvicorn."""
    import uvicorn

    uvicorn.run("terminal_radio.main:app", host=host, port=port, reload=reload)
    return 0


def _build_query(arguments: argparse.Namespace) -> str:
    """Fold the filter flags into the query grammar the search already speaks."""
    terms = [arguments.query] if arguments.query else []
    for key, values in (
        ("band", [arguments.band] if arguments.band else []),
        ("genre", arguments.genre or []),
        ("region", arguments.region or []),
        ("language", arguments.language or []),
        ("network", arguments.network or []),
    ):
        terms.extend(f"{key}:{value}" for value in values)
    return " ".join(terms)


def _print_now_playing(settings: Settings, arguments: argparse.Namespace) -> int:
    """Print the announced titles, newest first."""
    import json

    from terminal_radio.services import NowPlayingLog

    log = NowPlayingLog(settings.now_playing_file)
    # One station's titles are a slice of the same log, so it is read wide
    # enough that filtering still has the asked-for number to give back.
    entries = log.read(None if arguments.station else arguments.limit)
    if arguments.station:
        entries = tuple(
            item for item in entries if item.station_slug == arguments.station
        )[: arguments.limit]

    if arguments.json:
        print(
            json.dumps(
                [item.model_dump(mode="json") for item in entries],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    for item in entries:
        moment = item.at.astimezone().strftime("%m-%d %H:%M")
        print(f"{moment}  {item.station_name:<18} {item.title}")

    if not entries:
        print("Nothing has been announced yet.", file=sys.stderr)
        return 1
    return 0


def _print_stations(settings: Settings, arguments: argparse.Namespace) -> int:
    """Print the stations answering the query, as a table or as JSON."""
    import json

    from terminal_radio.services import StationCatalog, search_stations

    catalog = StationCatalog.from_file(settings.stations_file)
    stations = search_stations(catalog.all(), _build_query(arguments))

    if arguments.json:
        print(
            json.dumps(
                [station.model_dump(mode="json") for station in stations],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    for station in stations:
        print(f"{station.slug:<18} {station.dial:<10} {station.name}")

    # An empty result is worth a word on stderr, so a pipe still sees nothing
    # while a person is told the query matched rather than the catalog being bare.
    if not stations:
        print("No station matches that query.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

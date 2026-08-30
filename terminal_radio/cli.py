"""Command line entry point of the radio project."""

from __future__ import annotations

import argparse

from terminal_radio.core.about import get_version
from terminal_radio.core.config import Settings, get_settings
from terminal_radio.constants.about import COMMAND
from terminal_radio.enums import Band


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

    stations = commands.add_parser("stations", help="Print the station catalog")
    stations.add_argument(
        "--band", choices=[band.value for band in Band], help="Restrict to one band"
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
            return _print_stations(settings, arguments.band)
        case _:
            return _run_ui(settings, no_autoplay=getattr(arguments, "no_autoplay", False))


def _run_ui(settings: Settings, no_autoplay: bool) -> int:
    """Start the terminal UI."""
    from terminal_radio.core.i18n import LocaleRepository
    from terminal_radio.services import ThemeRepository, build_radio_service
    from terminal_radio.tui.app import RadioApp

    if no_autoplay:
        settings = settings.model_copy(update={"autoplay_last_station": False})

    RadioApp(
        service=build_radio_service(settings),
        themes=ThemeRepository.from_file(settings.themes_file),
        locales=LocaleRepository.from_directory(settings.locales_dir, settings.locale),
        settings=settings,
    ).run()
    return 0


def _run_api(host: str, port: int, reload: bool) -> int:
    """Serve the FastAPI application with uvicorn."""
    import uvicorn

    uvicorn.run("terminal_radio.main:app", host=host, port=port, reload=reload)
    return 0


def _print_stations(settings: Settings, band: str | None = None) -> int:
    """Print the catalog as an aligned table."""
    from terminal_radio.services import StationCatalog

    catalog = StationCatalog.from_file(settings.stations_file)
    stations = catalog.by_band(Band(band)) if band else catalog.all()

    for station in stations:
        print(f"{station.slug:<18} {station.dial:<10} {station.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

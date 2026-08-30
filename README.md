# Radio

<p align="right">
  <strong>English</strong> · <a href="README.zh-Hant.md">繁體中文</a>
</p>

<p align="center">
  <img src="assets/radio-logo.svg" width="600" alt="RADIO in colorful gradient ASCII art">
</p>

![python](https://img.shields.io/badge/python-3.12%2B-3fb950?style=flat-square&logo=python&logoColor=white) ![Textual](https://img.shields.io/badge/Textual-8.2-3fb950?style=flat-square) ![FastAPI](https://img.shields.io/badge/FastAPI-0.141-3fb950?style=flat-square&logo=fastapi&logoColor=white) ![player](https://img.shields.io/badge/player-mpv-3fb950?style=flat-square&logo=mpv&logoColor=white) ![stations](https://img.shields.io/badge/stations-44-3fb950?style=flat-square) ![themes](https://img.shields.io/badge/themes-14-3fb950?style=flat-square) ![i18n](https://img.shields.io/badge/i18n-zh--Hant%20%7C%20en-3fb950?style=flat-square) ![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-3fb950?style=flat-square&logo=apple&logoColor=white) ![license](https://img.shields.io/badge/license-MIT-3fb950?style=flat-square)

A terminal player for Taiwanese radio stations. The Textual interface and FastAPI control API share the same service layer.

## Prerequisites

Radio requires Python 3.12 or later, [uv](https://docs.astral.sh/uv/) and [mpv](https://mpv.io/). Install mpv for your system first:

```sh
# macOS (Homebrew)
brew install mpv

# Ubuntu / Debian
sudo apt update
sudo apt install mpv

# Arch Linux
sudo pacman -S mpv
```

For other systems, see the [mpv installation guide](https://mpv.io/installation/). After installation, run `mpv --version` to confirm that the command is available in your terminal.

## Install

```sh
make link      # uv tool install --editable . --force
```

This installs the `radio` command directly into PATH, so it can be run from any directory. It is an editable installation, which means project changes take effect without reinstalling. To remove it, run:

```sh
make unlink
```

## Run

```sh
radio                     # terminal interface
radio ui --no-autoplay    # do not resume the last station at startup
radio api                 # HTTP API; docs at http://127.0.0.1:8000/docs
radio stations --band AM
radio --help
```

Without installing, use `make run`, `make api` or `uv run radio ...`.

## Terminal interface

The tabs include **Home**, FM, AM, **Favorites**, **History**, **Themes**, **Settings** and **About**. Every launch starts on Home, even when the app also resumes the last station. The bottom bar shows the playback state, frequency, station, program title, elapsed time, audio output and volume. Click the playback state at the bottom left to pause or resume. The output device name is limited to fifteen characters. By default, the last station resumes at startup.

| Key | Action |
| --- | --- |
| `←` `→` | Move to the previous or next tab |
| `↑` `↓` `j` `k` | Move the cursor |
| `enter` | Use the selected item: play or resume a station, apply a theme or change a setting |
| `space` | Pause or resume |
| `s` | Stop playback |
| `f` | Add or remove a favorite |
| `+` `=` | Raise the volume |
| `-` `_` | Lower the volume |
| `m` | Mute or unmute |
| `t` | Switch to the next theme |
| `e` | Export settings |
| `i` | Import settings |
| `w` | Switch between English and Traditional Chinese |
| `q` | Quit |

## Scrolling

When columns are wider than the window, use a mouse or trackpad to scroll horizontally. The horizontal scrollbar is hidden so it does not look like a volume bar. The left and right arrow keys still only switch tabs.

If all rows fit on screen but the columns are too wide, scrolling down moves right and scrolling up moves left. When more rows are available below, the wheel keeps its normal vertical movement.

Favorites, volume, mute, the last station and the active theme are stored in `.radio/state.json`.

## Configuration files

| File | Contents |
| --- | --- |
| `stations.toml` | Station slug, name, band, frequency and stream URL |
| `themes.yml` | All color palettes and the default theme |
| `locales/*.yml` | English and Traditional Chinese interface text |
| `app/tui/radio.tcss` | Terminal interface layout |
| `.radio/history.jsonl` | Listening history, with one JSON event per line |
| `.radio/state.json` | Favorites, volume, mute, autoplay, animations, language, station and theme |

To add a station, append a block to `stations.toml`:

```toml
[[stations]]
slug = "example"
name = "Example FM"
band = "FM"
frequency = "99.9"
description = "Optional description"
url = "https://example.com/live/playlist.m3u8"
```

## Audio output

The bottom bar shows where the sound is being sent. `mpv` only reports `auto`, so macOS runs `system_profiler SPAudioDataType` in the background every fifteen seconds and caches the result. On other platforms, or when detection fails, the app shows the name of the mpv output driver instead.

## Languages

Radio currently includes only English and Traditional Chinese. Their messages are stored in `locales/en.yml` and `locales/zh-Hant.yml`, and Traditional Chinese is the default. Press `w` to switch between them. The **Settings** page also shows the current language.

All text written by the app is translated. Station names, descriptions and program titles come from the catalog or stream data, so they remain in their original language. When interface text changes, update both locale files. If a translation key is missing, the app first falls back to Traditional Chinese and then displays the key itself.

## Themes, settings and about

The **Themes** page previews every palette in `themes.yml`. Each card uses its own background, foreground and color swatches. Press `enter` to apply the selected theme. When you return to this page, the cursor stays on the active theme.

The **Settings** page lists options such as autoplay, animations, language, theme and volume. Press `enter` to change editable items, and the notes column shows the related key. Read-only items show their value and the environment variable that can override it. Select **Restore defaults** and confirm to reset these settings while keeping favorites, the last station and listening history.

Animations are off by default.

The **About** page shows the version, copyright and packages used by the app. The author, year and project URL are defined in `app/core/about.py`.

## Exporting and importing settings

Press `e`, or select **Export settings**, to list the available Desktop, Documents, Downloads, home, project and data folders. Press `enter` to write the file or `escape` to cancel.

The file name follows the format `settings_<timestamp>.radio.config`, with time recorded to the millisecond.

```json
{
  "version": "0.1.0",
  "exported_at": "2026-08-30T13:44:24.355+08:00",
  "settings": { "...": "..." },
  "preferences": { "favorites": [], "volume": 100, "...": "..." }
}
```

Press `i` to search the same folders for `.radio.config` files, listed from newest to oldest. Importing restores favorites, volume, mute, theme, language, autoplay and animations. Every page is updated at once.

The app only applies the `preferences` section. The `settings` section records the environment at the time of export, so its paths and commands belong to the original device and are not transferred during import. Files with an invalid format or the wrong value types are rejected. Stations that no longer exist are also removed from favorites and the last-played record.

## Listening history

Each session start, session end, play, pause and resume is written to `.radio/history.jsonl` with timing data. A `play_ended` event records the total elapsed time and paused time. The actual listening time is `duration_seconds - paused_seconds`. The table always shows listening and paused time as `HH:MM:SS`. Select **Clear listening history** and confirm to remove all saved events.

## API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/stations?band=FM` | List stations, optionally filtered by band |
| GET | `/stations/{slug}` | Get one station |
| GET | `/player` | Get playback state, program title and timers |
| POST | `/player/play` | Play a station |
| POST | `/player/toggle` | Toggle playback for a station |
| POST | `/player/pause` | Pause playback |
| POST | `/player/resume` | Resume playback |
| POST | `/player/stop` | Stop playback |
| GET | `/history` | Get recent listening events |
| GET | `/history/summary` | Get listening totals for each station |
| GET | `/themes` | List available themes |

## Contributing and security

Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request. Report security issues privately by following [SECURITY.md](SECURITY.md), and do not open a public issue. All participants must follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

Radio uses the [MIT License](LICENSE).

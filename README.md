# Terminal Radio

<p align="right">
  <strong>English</strong> · <a href="https://github.com/yueswater/terminal-radio/blob/main/README.zh-Hant.md">繁體中文</a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/yueswater/terminal-radio/main/assets/terminal-radio-logo.svg" width="560"
       alt="A terminal screen beside the RADIO word mark, in gradient ASCII art">
</p>

![python](https://img.shields.io/badge/python-3.12%2B-3fb950?style=flat-square&logo=python&logoColor=white) ![Textual](https://img.shields.io/badge/Textual-8.2-3fb950?style=flat-square) ![FastAPI](https://img.shields.io/badge/FastAPI-0.141-3fb950?style=flat-square&logo=fastapi&logoColor=white) ![player](https://img.shields.io/badge/player-mpv-3fb950?style=flat-square&logo=mpv&logoColor=white) ![stations](https://img.shields.io/badge/stations-44-3fb950?style=flat-square) ![themes](https://img.shields.io/badge/themes-14-3fb950?style=flat-square) ![i18n](https://img.shields.io/badge/i18n-zh--Hant%20%7C%20en-3fb950?style=flat-square) ![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-3fb950?style=flat-square) ![license](https://img.shields.io/badge/license-MIT-3fb950?style=flat-square)

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

> **macOS and Linux only.** The player reaches mpv over a unix socket. Windows
> is not supported and is not tested. It runs under WSL.

## Install

```sh
curl -LsSf https://raw.githubusercontent.com/yueswater/terminal-radio/main/install.sh | sh
```

That installs uv if it is missing, then the `radio` command, and tells you how
to install mpv if you do not have it. Nothing needs cloning.

If you would rather do it yourself:

```sh
uv tool install radiotui-tw
# or
pipx install radiotui-tw
```

To remove it, run `uv tool uninstall radiotui-tw`.

### Working on the project

Clone the repository and install it in editable form, so changes take effect
without reinstalling:

```sh
make link      # uv tool install --editable . --force
make unlink    # remove it again
```

## Run

```sh
radio                     # terminal interface
radio ui --no-autoplay    # do not resume the last station at startup
radio api                 # HTTP API; docs at http://127.0.0.1:8000/docs
radio --help
```

Without installing, use `make run`, `make api` or `uv run radio ...`.

## Staying up to date

Opening the radio asks the index, at most once a day, whether a newer release
exists. When there is one you are told, and offered the update if this copy was
installed by a package manager it can drive — `uv tool` or `pipx`. Choosing it
closes the radio and runs the upgrade, because a program cannot replace the
files it is running from.

Saying **Later** brings the notice back next time, three times in all, and then
it stops until a version you have not been told about appears. A copy running
from a checkout is never offered an upgrade, only told that one exists. Set
`RADIO_CHECK_FOR_UPDATES=0` to ask nothing, ever.

Upgrading by hand, whichever way it was installed:

```sh
uv tool upgrade radiotui-tw
pipx upgrade radiotui-tw
```

## Command line control

The radio can be driven without opening the interface at all.

```sh
radio play news98
radio pause / radio resume / radio stop
radio status
radio status --json      # for scripts: radio status --json | jq -r .program
radio volume 50          # an absolute level
radio volume +10         # a step
radio mute / radio unmute
radio sleep 30           # stop after thirty minutes
radio sleep off
radio now                # the station and title on air right now
radio now-playing        # everything they have announced
```

**One process owns the player.** It holds a lock file and listens on a unix
socket in the runtime directory. Two owners would mean two audio streams and
two writers of the same state file, so the second one is refused.

The owner is started for you: `radio play` with nothing running launches a
headless one in the background, and a headless owner with nothing playing and
nobody asking stands down after five minutes. When the terminal interface is
open it is the owner, so `radio play` typed in another window drives the radio
already on screen rather than starting a second one.

```sh
radio daemon             # run one in the foreground
radio daemon status      # report which process owns the player
radio daemon stop        # ask it to shut down
```

Every control command is an HTTP request over that socket, which is the same
application `radio api` serves over a port. The socket is created readable only
by the user who started it.

## Terminal interface

The tabs include **Home**, FM, AM, **Favorites**, **History**, **Tracks**, **Statistics**, **Themes**, **Settings** and **About**. Every launch starts on Home, even when the app resumes the last station. The bottom bar shows the playback state, frequency, station, program title, elapsed time, audio output, sleep timer and volume. Click the playback state at the bottom left to pause or resume. The output device name is limited to fifteen characters. By default, the last station resumes at startup.

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
| `/` | Search all built-in and custom stations |
| `?` | Open the keyboard shortcut guide |
| `q` | Quit, fading the sound out across the farewell |

Leaving fades the sound down over `RADIO_GOODBYE_SECONDS` rather than cutting
it off, across the same moment the farewell is on screen. The level you chose is
untouched by the fade, so the next run starts where you left it. Set the
duration to zero to leave at once.

## Scrolling

When columns are wider than the window, use a mouse or trackpad to scroll horizontally. The horizontal scrollbar is hidden so it does not look like a volume bar. The left and right arrow keys still only switch tabs.

If all rows fit on screen but the columns are too wide, scrolling down moves right and scrolling up moves left. When more rows are available below, the wheel keeps its normal vertical movement. The FM, AM, Favorites, History and Settings tables stay centred with the same space above and below. Their pages remain fixed while only the table rows scroll.

Favorites, volume, mute, autoplay, reconnect, station checks, language, the last station and the active theme are stored in `<state>/state.json`.

## Configuration files

| File | Contents |
| --- | --- |
| `app/data/stations.toml` | Station identity, classification and stream addresses |
| `app/data/themes.yml` | All color palettes and the default theme |
| `app/data/locales/*.yml` | English and Traditional Chinese interface text |
| `app/tui/radio.tcss` | Terminal interface layout |
| `<state>/history.jsonl` | Listening history, with one JSON event per line |
| `<state>/now-playing.jsonl` | Titles the stations announced, one per line |
| `<state>/state.json` | Favorites, volume, mute, autoplay, animations, language, station and theme |
| `<state>/custom-stations.toml` | Stations added from the Settings page |
| `<runtime>/control.sock` | Socket every command reaches the owner on |
| `<runtime>/control.lock` | Claim on the player, held by the owner |

`<state>` is the per-user directory the program writes to, outside the
installation, so upgrading or reinstalling never loses a history:
`~/Library/Application Support/terminal-radio` on macOS and
`~/.local/state/terminal-radio` on Linux. `RADIO_DATA_DIR` overrides it.

`<runtime>` holds only what a running radio needs and nothing that should
outlive a restart: `$XDG_RUNTIME_DIR/terminal-radio`, or a per-user
directory under the system temporary directory. It is deliberately not the
state directory, because a unix socket path is capped near a hundred bytes
and the state directory alone is most of that budget on macOS.
`RADIO_RUNTIME_DIR` overrides it.

The bundled catalogue, themes and locales are read-only. To use your own without
touching the installation, drop a `stations.toml`, `themes.yml` or `locales/`
into the config directory, `~/Library/Application Support/terminal-radio` on
macOS and `~/.config/terminal-radio` on Linux, and it is read in preference.

Built-in stations live in `app/data/stations.toml`. You can also open **Custom stations** from **Settings** to add, edit or delete a local station without changing the project file. Custom stream URLs must use HTTP or HTTPS. To add a built-in station, append a block to `app/data/stations.toml`:

```toml
[[stations]]
slug = "example"
name = "Example FM"
band = "FM"
frequency = "99.9"
description = "Optional description"

network = "Example Network"       # optional, groups a family of frequencies
regions = ["taipei"]              # optional, where it is mainly heard
genres = ["news", "talk"]         # optional, what it broadcasts
languages = ["zh-Hant"]           # optional, BCP 47 tags

url = "https://example.com/live/playlist.m3u8"
fallback_urls = []                # optional, tried in turn when the first goes quiet
```

`regions` and `genres` are closed sets: their values are the ones listed in
`terminal_radio/enums/station.py`, and anything else is a load error rather than
a station nobody can find.

## Audio output

The bottom bar shows where the sound is being sent. `mpv` only reports `auto`, so macOS runs `system_profiler SPAudioDataType` in the background every fifteen seconds and caches the result. On other platforms, or when detection fails, the app shows the name of the mpv output driver instead.

## Playback tools

Press `/` to search by frequency, station name, description or band. Results update while you type, and `enter` plays the highlighted station.

Automatic reconnect is enabled by default. When a stream drops, Radio retries after 1, 2, 4, 8 and 15 seconds. It stops retrying after the fifth failure. You can turn this off in **Settings**.

The sleep timer can be turned off or set to 15, 30, 60 or a custom number of minutes from 1 to 1440. Its countdown appears in the bottom bar and only lasts for the current run.

Radio can check whether station streams are online, slow or offline. Automatic checks are cached for five minutes, and **Check all stations now** runs a fresh check. At most four streams are checked at once.

## Languages

Radio currently includes only English and Traditional Chinese. Their messages are stored in `app/data/locales/en.yml` and `app/data/locales/zh-Hant.yml`, and Traditional Chinese is the default. Press `w` to switch between them. The **Settings** page also shows the current language.

All text written by the app is translated. Station names, descriptions and program titles come from the catalog or stream data, so they remain in their original language. When interface text changes, update both locale files. If a translation key is missing, the app first falls back to Traditional Chinese and then displays the key itself.

## Themes, settings and about

The **Themes** page previews every palette in `app/data/themes.yml`. Each card uses its own background, foreground and color swatches. Press `enter` to apply the selected theme. When you return to this page, the cursor stays on the active theme.

The **Settings** page includes autoplay, reconnect, sleep timer, station checks, custom stations, keyboard shortcuts, animations, language, theme and volume. Press `enter` to change an editable item. Read-only items show their value and the environment variable that can override it. Select **Restore defaults** and confirm to reset preferences while keeping favorites, custom stations, the last station and listening history.

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
  "preferences": { "favorites": [], "volume": 100, "...": "..." },
  "custom_stations": []
}
```

Press `i` to search the same folders for `.radio.config` files, listed from newest to oldest. Importing restores custom stations, favorites, volume, mute, theme, language, autoplay, reconnect, station checks and animations. Every page is updated at once. Older exports without `custom_stations` remain supported.

The app only applies the `preferences` section. The `settings` section records the environment at the time of export, so its paths and commands belong to the original device and are not transferred during import. Files with an invalid format or the wrong value types are rejected. Stations that no longer exist are also removed from favorites and the last-played record.

## Finding a station

Press `/` anywhere, or click the search icon at the right of the tab bar. The
same query grammar works there, on the command line and over HTTP:

```sh
radio stations "genre:news region:taipei"
radio stations "genre:news genre:talk"    # the same key widens
radio stations --genre classical --json
```

Filters are `genre:`, `region:`, `lang:`, `network:` and `band:`. Terms naming
different keys narrow the result; terms naming the same key widen it. Anything
that is not a filter is free text, ranked so a dial you typed in full comes
before the same digits inside somebody's description.

Every station also records the family it belongs to, where it is mainly heard,
what it broadcasts and the languages it is heard in. Those are language neutral
codes in the catalog and translated names on screen. See the comments at the
top of `terminal_radio/data/stations.toml`.

## Backup streams

A station may list `fallback_urls` beside its `url`. The first address is
always tried first. When a stream goes quiet the existing reconnect delays are
unchanged, but each retry moves to the next address in turn. Whichever one
works is then kept, rather than switching back and interrupting the sound; the
primary is tried again the next time the station is asked for. The bottom bar
shows a quiet badge only while a backup is carrying the sound.

A station counts as online when any one of its addresses answers, and the
health check stops at the first that does.

## Track log

The station is asked for its current title outright when playback starts,
rather than waiting for playback to reach the first metadata block, which puts
the title on screen with the sound instead of two seconds behind it. A title
too long for its slot slides along; turn that off from **Settings** or with
`RADIO_SCROLL_TITLES=0`.

Only a few stations publish titles at all. Of the bundled catalogue three do,
and the rest send station identity but no track information, over ICY and over
HLS alike.

While a radio is running, the titles the stations announce are written to
`<state>/now-playing.jsonl`. This is the station's timeline, kept apart from
the listening history, which is the listener's. The same title is not recorded
twice in a row, so a reconnect does not duplicate a song, and entries older
than `RADIO_NOW_PLAYING_RETENTION_DAYS` days (30 by default) are dropped as the
log grows.

The **Tracks** tab lists the same thing on screen, newest first, with
buttons to export it as CSV or clear it.

```sh
radio now                        # just what is on right now
radio now-playing --limit 10
radio now-playing --station icrt
radio now-playing --json
```

## Listening history

Each session start, session end, play, pause and resume is written to `<state>/history.jsonl` with timing data. A `play_ended` event records the total elapsed, paused and interrupted time. Listening time excludes both pauses and reconnect interruptions. The table always uses `HH:MM:SS`.

Select **Export CSV** to save the complete station summary with a UTF-8 BOM. Column names follow the current interface language. Select **Clear listening history** and confirm to remove all saved events.

The **Statistics** page reads the complete valid history and draws terminal charts for total listening time, play count, active days, the ten most-listened stations, a 14-day trend, weekdays, time of day and FM/AM share. Only completed plays are counted.

## API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/stations?q=genre:news region:taipei` | List stations, filtered and ranked |
| GET | `/stations/{slug}` | Get one station |
| GET | `/player` | Get playback state, program title and timers |
| POST | `/player/play` | Play a station |
| POST | `/player/toggle` | Toggle playback for a station |
| POST | `/player/pause` | Pause playback |
| POST | `/player/resume` | Resume playback |
| POST | `/player/stop` | Stop playback |
| POST | `/player/volume` | Set an absolute level, or move by a step |
| POST | `/player/mute` | Silence the output, or bring it back |
| POST | `/player/sleep` | Stop playback after a number of minutes |
| GET | `/history` | Get recent listening events |
| GET | `/history/summary` | Get listening totals for each station |
| GET | `/history/now-playing` | Get the titles the stations announced |
| GET | `/themes` | List available themes |

## Contributing and security

Read [CONTRIBUTING.md](https://github.com/yueswater/terminal-radio/blob/main/CONTRIBUTING.md) before submitting a pull request. Report security issues privately by following [SECURITY.md](https://github.com/yueswater/terminal-radio/blob/main/SECURITY.md), and do not open a public issue. All participants must follow the [Code of Conduct](https://github.com/yueswater/terminal-radio/blob/main/CODE_OF_CONDUCT.md).

## License

Radio uses the [MIT License](https://github.com/yueswater/terminal-radio/blob/main/LICENSE).

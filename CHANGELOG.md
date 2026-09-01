# Changelog

## [0.3.0](https://github.com/yueswater/terminal-radio/compare/v0.2.0...v0.3.0) (2026-09-01)


### Features

* **stations:** classify every station by the family it belongs to, where it is heard, what it broadcasts and the languages it is heard in, and search them with one query grammar — `genre:news region:taipei` — shared by the search bar, `radio stations` and the HTTP API ([b871994](https://github.com/yueswater/terminal-radio/commit/b8719945309f5bbac4a31199488a976bcd6c5456))
* **player:** fall back to backup stream addresses, moving to the next one on each retry without changing the reconnect schedule, and stay on whichever works rather than interrupting a stream to return to the first ([b871994](https://github.com/yueswater/terminal-radio/commit/b8719945309f5bbac4a31199488a976bcd6c5456))
* **cli:** control a running radio from the shell with `radio play`, `pause`, `status`, `volume`, `mute`, `sleep` and `now`, plus `--json` for scripts. One process owns the player, and control commands start a headless one when there is none ([b871994](https://github.com/yueswater/terminal-radio/commit/b8719945309f5bbac4a31199488a976bcd6c5456))
* **tui:** keep a log of the titles stations announce, on its own tab and exportable as CSV, apart from the listening history. The station is asked for its title outright when playback starts, so it arrives with the sound ([b871994](https://github.com/yueswater/terminal-radio/commit/b8719945309f5bbac4a31199488a976bcd6c5456))
* **tui:** open search from the tab bar as well as `/`, slide titles too long for their slot, and fade the sound out on the way to the farewell ([b871994](https://github.com/yueswater/terminal-radio/commit/b8719945309f5bbac4a31199488a976bcd6c5456))


### Fixes

* **stations:** correct where the southern AM stations are heard ([00b26df](https://github.com/yueswater/terminal-radio/commit/00b26dfcd60fd8e4137afa3b06c9b3148ad0af64))
* **stations:** keep a custom station's short name when it is saved ([b871994](https://github.com/yueswater/terminal-radio/commit/b8719945309f5bbac4a31199488a976bcd6c5456))
* **player:** stop the interface and the API each building their own player, which meant two mpv processes writing the same state file over each other ([b871994](https://github.com/yueswater/terminal-radio/commit/b8719945309f5bbac4a31199488a976bcd6c5456))

## [0.2.0](https://github.com/yueswater/terminal-radio/compare/v0.1.0...v0.2.0) (2026-08-30)


### Features

* install with one curl command, which brings uv and mpv with it ([02ba80e](https://github.com/yueswater/terminal-radio/commit/02ba80ef2a6d9e1e94a8ae2056b4e9877c0fd24b))


### Fixes

* focus the confirmation dialog through AUTO_FOCUS, so a keypress cannot arrive before the safe button has it ([64a824e](https://github.com/yueswater/terminal-radio/commit/64a824e24da42d3cb20077e8d2301a8a02263b52))


### Notes

Windows support was written and then withdrawn in
[1be739c](https://github.com/yueswater/terminal-radio/commit/1be739c6), because
mpv could never be provisioned on the Windows runner and the named pipe path
therefore never ran. The player is for macOS and Linux.

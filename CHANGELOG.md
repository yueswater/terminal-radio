# Changelog

## [0.4.0](https://github.com/yueswater/terminal-radio/compare/v0.3.0...v0.4.0) (2026-09-01)


### Features

* add custom station library ([48c3aae](https://github.com/yueswater/terminal-radio/commit/48c3aae3eea76a4e3d468bd84ebf04311082253c))
* add reconnect backoff schedule ([85273b7](https://github.com/yueswater/terminal-radio/commit/85273b731929818f9fa1ac503b755c489e6e6ed3))
* add sleep timer service ([39aa7b8](https://github.com/yueswater/terminal-radio/commit/39aa7b8673a960dd8634ea24c9cbc16f6ff5b8de))
* add station health and centralize constants ([72b2ad5](https://github.com/yueswater/terminal-radio/commit/72b2ad5dda65cf58db510546cec907757c97fedb))
* add station tools and listening insights ([fb7ef98](https://github.com/yueswater/terminal-radio/commit/fb7ef982c693f28950994ce1e81a00a07caee073))
* add terminal radio application ([71a9f43](https://github.com/yueswater/terminal-radio/commit/71a9f4373d3e655d702dfec22d5749b3230b7b00))
* centralize enums and add reconnect state ([a64d039](https://github.com/yueswater/terminal-radio/commit/a64d039ab86dcbc7ec130aaa2b28c1348be23d35))
* emphasize statistics chart structure ([78ce378](https://github.com/yueswater/terminal-radio/commit/78ce3782a3d2061f0bc939eb7e4cf8c3b3df76c2))
* expose reconnect and sleep settings ([65be815](https://github.com/yueswater/terminal-radio/commit/65be8156d6519f8560c3f072467a9b0f4159bbbb))
* reconnect dropped radio streams ([66e0790](https://github.com/yueswater/terminal-radio/commit/66e0790764c4c09e28f87f725bc8645dec6fcdd5))
* redesign listening statistics charts ([a1363dd](https://github.com/yueswater/terminal-radio/commit/a1363dd3c6bb9bab3b6e8403c7c06e40805fe77b))
* run on Windows ([02ba80e](https://github.com/yueswater/terminal-radio/commit/02ba80ef2a6d9e1e94a8ae2056b4e9877c0fd24b))
* simplify listening station rankings ([d48d0b4](https://github.com/yueswater/terminal-radio/commit/d48d0b46075ee26deca7067d9944f9b29c851b36))
* station metadata, backup streams, shell control and a track log ([b871994](https://github.com/yueswater/terminal-radio/commit/b8719945309f5bbac4a31199488a976bcd6c5456))
* transfer and search custom stations ([02501f8](https://github.com/yueswater/terminal-radio/commit/02501f8020ce1477bb4e052a2bd6bb0edc0cc2d8))


### Fixes

* focus the safe button after the dialog has been drawn ([f456f94](https://github.com/yueswater/terminal-radio/commit/f456f943e8ccf40fa5f4ff280433b6cd14b4c253))
* let the framework focus the confirmation dialog ([64a824e](https://github.com/yueswater/terminal-radio/commit/64a824e24da42d3cb20077e8d2301a8a02263b52))
* **stations:** correct where the southern AM stations are heard ([00b26df](https://github.com/yueswater/terminal-radio/commit/00b26dfcd60fd8e4137afa3b06c9b3148ad0af64))


### Refactoring

* rename package and make the project installable ([d1aaa03](https://github.com/yueswater/terminal-radio/commit/d1aaa0304c85bbc1bee43744b740fffb691654fb))


### Packaging

* keep the logo generator out of the distribution ([b741eaa](https://github.com/yueswater/terminal-radio/commit/b741eaa97b7c5dc18110391679e72e915b9b2f51))
* publish under the name radiotui-tw ([aef13db](https://github.com/yueswater/terminal-radio/commit/aef13db91deba1f018aae8bdc9ddd714baa5fbe2))

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

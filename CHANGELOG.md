# Changelog

## [0.3.0](https://github.com/yueswater/terminal-radio/compare/v0.2.0...v0.3.0) (2026-09-01)


### Features

* station metadata, backup streams, shell control and a track log ([42993fb](https://github.com/yueswater/terminal-radio/commit/42993fb39be48141a8783d93440bae94d13e766a))


### Fixes

* **stations:** correct where the southern AM stations are heard ([9b030dc](https://github.com/yueswater/terminal-radio/commit/9b030dc90e73ccd1162ca7944c0b9666d5f7a4f5))

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

# Contributing to Radio

Small, focused fixes and additions are welcome. Before starting a larger change,
open an issue so the direction can be agreed on first.

## Set up the project

You need Python 3.12 or newer, [uv](https://docs.astral.sh/uv/) and `mpv`.

```sh
uv sync
make run
```

The API can be started with `make api`. Its interactive documentation is at
`http://127.0.0.1:8000/docs`.

## Run the checks

```sh
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q app tests
```

Add a regression test for behavior changes and bug fixes. Tests should exercise
the real component where practical; keep fakes at external boundaries such as
the audio process or filesystem.

## Keep changes consistent

- Follow the existing Python style and type annotations.
- Keep commits and pull requests limited to one purpose.
- Do not commit `.radio/`, bytecode caches or local virtual environments.
- Radio ships with two interface languages: English and Traditional Chinese.
  When UI copy changes, update both `locales/en.yml` and
  `locales/zh-Hant.yml`.
- If user-facing documentation changes, update both `README.md` and
  `README.zh-Hant.md` where the change applies.
- New settings should include their `RADIO_*` environment variable in both
  READMEs.

## Stations and themes

For a station change, verify the band, frequency and stream URL. Prefer a stable
HTTPS stream and keep the `slug` unique. For a theme change, check that text,
selection, success, warning and error colors remain readable on its background.

## Pull requests

Include:

- a short explanation of the problem and the chosen fix;
- the commands used to verify the change;
- screenshots or terminal captures when the visual result matters;
- documentation updates for changed commands, settings or UI behavior.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
Do not report vulnerabilities in a public issue; use the process in
[SECURITY.md](SECURITY.md).

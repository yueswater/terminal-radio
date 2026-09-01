"""Draw the project logo as an SVG.

The terminal UI draws its word mark from `app.constants.logo.LOGO`, which is
limited to what fits in a few terminal rows. The README has no such limit, so
this script redraws the same idea on a finer grid: an app icon carrying a prompt
and a pair of antennas, beside the WAVEPICK word mark, all under one gradient.

The letters come from `app.constants.logo`, the same font the terminal UI draws,
so the two marks can never drift apart.

The prompt is knocked out of the icon rather than painted on it, so the icon
works on a light and a dark page alike.

Run it with `make logo` after changing anything here.
"""

from __future__ import annotations

from pathlib import Path

from terminal_radio.constants.logo import BLOCK, GLYPH_ROWS, render_word

OUTPUT = Path(__file__).resolve().parent.parent / "assets" / "terminal-radio-logo.svg"

CELL = 14           # side of one font cell
ICON = 104          # the icon is square
RADIUS = 22
PROMPT_STEP = 10    # size of one prompt block, and the step between blocks
PROMPT_X = 22
PROMPT_Y = 20
GAP = CELL * 3      # space between the icon and the word

ANTENNA_H = 40      # room above the icon for the antennas
ANTENNA_W = 7       # stroke width
ANTENNA_TIP = 7     # radius of the knob at each tip
ANTENNA_SPREAD = 16 # how far apart the antennas leave the icon
ANTENNA_INSET = 10  # how close each tip comes to the edge of the drawing

GRADIENT = (
    ("0%", "#ff4d6d"),
    ("18%", "#ff9f1c"),
    ("36%", "#ffd60a"),
    ("54%", "#2ec4b6"),
    ("70%", "#00b4d8"),
    ("86%", "#4361ee"),
    ("100%", "#b5179e"),
)

Rect = tuple[int, int, int, int]


def word_rects(scale: int, origin_x: int, origin_y: int) -> tuple[list[Rect], int]:
    """Return one rect per run of blocks in the word, plus the width it occupies.

    Runs are merged into single rects, so a stroke of six cells is one rect
    rather than six. It keeps the file small and the edges seamless.
    """
    rows = render_word()
    rects: list[Rect] = []

    for row, line in enumerate(rows):
        start: int | None = None
        for column in range(len(line) + 1):
            filled = column < len(line) and line[column] == BLOCK
            if filled and start is None:
                start = column
            elif not filled and start is not None:
                rects.append(
                    (
                        origin_x + start * scale,
                        origin_y + row * scale,
                        (column - start) * scale,
                        scale,
                    )
                )
                start = None

    return rects, len(rows[0]) * scale


def prompt_rects() -> list[Rect]:
    """Return the blocks of the chevron, sitting in the upper left of the icon.

    Five blocks in a staircase read as a chevron. A three block one blurs into an
    arrow at this size.
    """
    steps = [(step, step) for step in range(3)]
    steps += [(2 - step, 2 + step) for step in range(1, 3)]
    return [
        (
            PROMPT_X + column * PROMPT_STEP,
            PROMPT_Y + row * PROMPT_STEP,
            PROMPT_STEP,
            PROMPT_STEP,
        )
        for column, row in steps
    ]


def antenna_markup() -> str:
    """Return the two antennas rising from the top of the icon."""
    root_y = ANTENNA_H + 6
    tip_y = ANTENNA_H - 26
    left_root, right_root = ICON / 2 - ANTENNA_SPREAD, ICON / 2 + ANTENNA_SPREAD
    left_tip, right_tip = ANTENNA_INSET, ICON - ANTENNA_INSET

    return f"""  <g stroke="url(#spectrum)" stroke-width="{ANTENNA_W}" stroke-linecap="round">
    <line x1="{left_root}" y1="{root_y}" x2="{left_tip}" y2="{tip_y}"/>
    <line x1="{right_root}" y1="{root_y}" x2="{right_tip}" y2="{tip_y}"/>
  </g>
  <circle cx="{left_tip}" cy="{tip_y}" r="{ANTENNA_TIP}" fill="url(#spectrum)"/>
  <circle cx="{right_tip}" cy="{tip_y}" r="{ANTENNA_TIP}" fill="url(#spectrum)"/>"""


def render() -> str:
    """Return the finished SVG document."""
    top = ANTENNA_H
    letters, word_width = word_rects(
        CELL, ICON + GAP, top + (ICON - GLYPH_ROWS * CELL) // 2
    )
    width = ICON + GAP + word_width
    height = top + ICON

    stops = "\n".join(
        f'      <stop offset="{offset}" stop-color="{color}"/>' for offset, color in GRADIENT
    )
    holes = "\n".join(
        f'      <rect x="{x}" y="{y + top}" width="{w}" height="{h}" fill="#000"/>'
        for x, y, w, h in prompt_rects()
    )
    glyphs = "\n".join(
        f'    <rect x="{x}" y="{y}" width="{w}" height="{h}"/>' for x, y, w, h in letters
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">Wavepick</title>
  <desc id="desc">An app icon with antennas and a prompt, beside the WAVEPICK word mark.</desc>
  <defs>
    <linearGradient id="spectrum" gradientUnits="userSpaceOnUse"
                    x1="0" y1="0" x2="{width}" y2="0">
{stops}
    </linearGradient>
    <mask id="prompt">
      <rect x="0" y="{top}" width="{ICON}" height="{ICON}" rx="{RADIUS}" fill="#fff"/>
{holes}
    </mask>
  </defs>
{antenna_markup()}
  <rect x="0" y="{top}" width="{ICON}" height="{ICON}" rx="{RADIUS}"
        fill="url(#spectrum)" mask="url(#prompt)"/>
  <g fill="url(#spectrum)" shape-rendering="crispEdges">
{glyphs}
  </g>
</svg>
"""


def main() -> int:
    """Write the SVG and report where it landed."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""The word mark, and the block font it is drawn with.

This is the one place the shape of the mark is defined. The terminal UI reads
`LOGO` from here, and `scripts/render_logo.py` reads the font from here to draw
the same letters as an SVG, so the two can never drift apart.
"""

from __future__ import annotations

BLOCK = "█"

# Five rows per glyph. Strokes are two cells wide, which is what keeps the
# letters legible once a terminal renders them at one cell per character.
FONT: dict[str, tuple[str, ...]] = {
    "R": ("██████ ", "██   ██", "██████ ", "██   ██", "██   ██"),
    "A": (" █████ ", "██   ██", "███████", "██   ██", "██   ██"),
    "D": ("██████ ", "██   ██", "██   ██", "██   ██", "██████ "),
    "I": ("██", "██", "██", "██", "██"),
    "O": (" ██████ ", "██    ██", "██    ██", "██    ██", " ██████ "),
}

GLYPH_ROWS = 5
WORD = "RADIO"

# A shell prompt, drawn as a staircase. Five steps read as a chevron where three
# blur into an arrow.
PROMPT: tuple[str, ...] = (
    "██    ",
    "  ██  ",
    "    ██",
    "  ██  ",
    "██    ",
)
PROMPT_GAP = 3


def render_word(text: str = WORD) -> tuple[str, ...]:
    """Return the text drawn in the block font, one string per row."""
    return tuple(
        " ".join(FONT[character][row] for character in text)
        for row in range(GLYPH_ROWS)
    )


def render_mark(text: str = WORD, gap: int = PROMPT_GAP) -> tuple[str, ...]:
    """Return the prompt and the word side by side, one string per row."""
    word = render_word(text)
    separator = " " * gap
    return tuple(PROMPT[row] + separator + word[row] for row in range(GLYPH_ROWS))


# Built once at import. The terminal UI redraws the mark on every resize, so it
# reads a ready made tuple rather than composing one each time.
LOGO: tuple[str, ...] = render_mark()

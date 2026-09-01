"""The public word mark stays readable and carries the Wavepick identity."""

from terminal_radio.constants.logo import LOGO, render_word


def test_default_word_mark_draws_wavepick() -> None:
    """Reverting the default to RADIO must fail the rendered identity contract."""
    expected = (
        "██   ██  █████  ██   ██ ███████ ██████  ██  ██████  ██   ██",
        "██   ██ ██   ██ ██   ██ ██      ██   ██ ██ ██       ██  ██ ",
        "██ █ ██ ███████ ██   ██ █████   ██████  ██ ██       █████  ",
        "███████ ██   ██  ██ ██  ██      ██      ██ ██       ██  ██ ",
        " ██ ██  ██   ██   ███   ███████ ██      ██  ██████  ██   ██",
    )

    assert render_word() == expected
    assert all(line.endswith(word_line) for line, word_line in zip(LOGO, expected))

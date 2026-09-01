"""Names for the language neutral codes a station is classified with.

The catalog stores codes, not words: ``traffic``, ``hualien``, ``nan``. That is
what makes a filter work the same in every language. The words live in the
locale files, and this is the one place that joins the two.
"""

from __future__ import annotations

from collections.abc import Iterable

from terminal_radio.core.i18n import Translator

TAG_SEPARATOR = " · "


def label(translator: Translator, prefix: str, code: str) -> str:
    """Return the name of one code, falling back to the code itself.

    A translator answers an unknown key with the key, which would put
    ``language.ja`` on screen. A tag nobody has named yet reads better raw.
    """
    key = f"{prefix}.{code}"
    name = translator(key)
    return code if name == key else name


def genre_label(translator: Translator, code: str) -> str:
    """Return the name of one genre."""
    return label(translator, "genre", code)


def region_label(translator: Translator, code: str) -> str:
    """Return the name of one service area."""
    return label(translator, "region", code)


def language_label(translator: Translator, tag: str) -> str:
    """Return the name of one BCP 47 language tag."""
    return label(translator, "language", tag)


def format_tags(
    translator: Translator, prefix: str, codes: Iterable[str]
) -> str:
    """Return the codes named and joined for one table cell."""
    return TAG_SEPARATOR.join(label(translator, prefix, str(code)) for code in codes)

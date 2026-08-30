"""Loading of the interface languages and lookup of translated messages."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

from terminal_radio.core.exceptions import LocaleError


class Locale(BaseModel):
    """One interface language and the messages it defines."""

    model_config = {"frozen": True}

    code: str
    name: str
    messages: dict[str, str] = Field(default_factory=dict)


class Translator:
    """Resolves message keys against a locale, falling back to a default one."""

    def __init__(self, locale: Locale, fallback: Locale | None = None) -> None:
        self._locale = locale
        self._fallback = fallback

    @property
    def locale(self) -> Locale:
        """Return the locale currently in use."""
        return self._locale

    @property
    def code(self) -> str:
        """Return the code of the locale currently in use."""
        return self._locale.code

    def __call__(self, key: str, **values: object) -> str:
        """Return the message for the key, formatted with the given values."""
        template = self._locale.messages.get(key)
        if template is None and self._fallback is not None:
            template = self._fallback.messages.get(key)
        if template is None:
            return key

        try:
            return template.format(**values) if values else template
        except (IndexError, KeyError):
            return template


class LocaleRepository:
    """Every language found in the locale directory."""

    def __init__(self, locales: list[Locale], default: str | None = None) -> None:
        if not locales:
            raise LocaleError("No locale file found")

        self._locales = tuple(locales)
        self._by_code = {locale.code: locale for locale in self._locales}

        if len(self._by_code) != len(self._locales):
            raise LocaleError("Locale codes must be unique")
        if default is not None and default not in self._by_code:
            raise LocaleError(f"Unknown default locale: {default}")

        self._default = default or self._locales[0].code

    @classmethod
    def from_directory(
        cls, path: Path, default: str | None = None
    ) -> "LocaleRepository":
        """Read every YAML file of the directory as one locale."""
        try:
            files = sorted(path.glob("*.yml"))
        except OSError as error:
            raise LocaleError(f"Cannot read locale directory: {path}") from error

        locales: list[Locale] = []
        for file in files:
            try:
                raw = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
                locales.append(Locale(**raw))
            except (OSError, yaml.YAMLError) as error:
                raise LocaleError(f"Cannot read locale file: {file}") from error
            except (TypeError, ValidationError) as error:
                raise LocaleError(f"Invalid locale file: {file}") from error

        return cls(locales, default)

    @property
    def default_code(self) -> str:
        """Return the code of the language selected on startup."""
        return self._default

    def all(self) -> tuple[Locale, ...]:
        """Return every locale, sorted by file name."""
        return self._locales

    def codes(self) -> tuple[str, ...]:
        """Return every locale code, sorted by file name."""
        return tuple(locale.code for locale in self._locales)

    def get(self, code: str) -> Locale:
        """Return one locale by code or raise LocaleError."""
        try:
            return self._by_code[code]
        except KeyError:
            raise LocaleError(f"Unknown locale: {code}") from None

    def next_after(self, code: str) -> Locale:
        """Return the locale following the given one, wrapping around."""
        codes = self.codes()
        index = codes.index(code) if code in self._by_code else -1
        return self._locales[(index + 1) % len(self._locales)]

    def translator(self, code: str | None = None) -> Translator:
        """Build a translator for the given code, or for the default one."""
        wanted = code if code in self._by_code else self._default
        fallback = self._by_code.get(self._default)
        return Translator(self._by_code[wanted], fallback)

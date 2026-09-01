"""Atomic persistence for user-defined stations."""

from __future__ import annotations

import json
import os
import tempfile
import tomllib
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from terminal_radio.core.exceptions import CatalogError
from terminal_radio.models import Station


class CustomStationStore:
    """Read and atomically replace a small custom-station TOML file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> tuple[Station, ...]:
        """Return saved stations in file order; a missing file is empty."""
        if not self.path.exists():
            return ()
        try:
            raw = tomllib.loads(self.path.read_text(encoding="utf-8"))
        except OSError as error:
            raise CatalogError(f"Cannot read custom stations: {self.path}") from error
        except tomllib.TOMLDecodeError as error:
            raise CatalogError(f"Malformed custom stations: {self.path}") from error

        entries = raw.get("stations", [])
        if not isinstance(entries, list):
            raise CatalogError(f"Invalid custom stations: {self.path}")
        try:
            stations = tuple(Station.model_validate(entry) for entry in entries)
        except (TypeError, ValidationError) as error:
            raise CatalogError(f"Invalid custom station in {self.path}") from error

        slugs = [item.slug for item in stations]
        if len(slugs) != len(set(slugs)):
            raise CatalogError("Custom station slugs must be unique")
        return stations

    def save(self, stations: Sequence[Station]) -> None:
        """Validate and atomically replace the complete custom catalog."""
        items = tuple(stations)
        slugs = [item.slug for item in items]
        if len(slugs) != len(set(slugs)):
            raise CatalogError("Custom station slugs must be unique")

        temporary: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
            )
            temporary = Path(temporary_name)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(self._serialize(items))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            temporary = None
        except OSError as error:
            raise CatalogError(f"Cannot write custom stations: {self.path}") from error
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _serialize(stations: Sequence[Station]) -> str:
        """Encode the limited TOML subset used by the station catalog."""
        lines = ["# User-defined radio stations."]
        for item in stations:
            lines.extend(("", "[[stations]]"))
            lines.append(_string("slug", item.slug))
            lines.append(_string("name", item.name))
            if item.short_name is not None:
                lines.append(_string("short_name", item.short_name))
            lines.append(_string("band", item.band.value))
            if item.frequency is not None:
                lines.append(_string("frequency", item.frequency))
            if item.description is not None:
                lines.append(_string("description", item.description))
            if item.network is not None:
                lines.append(_string("network", item.network))
            if item.regions:
                lines.append(_array("regions", [str(v) for v in item.regions]))
            if item.genres:
                lines.append(_array("genres", [str(v) for v in item.genres]))
            if item.languages:
                lines.append(_array("languages", item.languages))
            lines.append(_string("url", item.url))
            if item.fallback_urls:
                lines.append(_array("fallback_urls", item.fallback_urls))
        return "\n".join(lines) + "\n"


def _quote(value: str) -> str:
    """Return a TOML basic string.

    JSON and TOML escape a basic string the same way, so the encoder in the
    standard library saves carrying one of our own.
    """
    return json.dumps(value, ensure_ascii=False)


def _string(key: str, value: str) -> str:
    """Return one ``key = "value"`` line."""
    return f"{key} = {_quote(value)}"


def _array(key: str, values: Sequence[str]) -> str:
    """Return one ``key = ["a", "b"]`` line."""
    return f"{key} = [{', '.join(_quote(value) for value in values)}]"

"""Endpoints exposing the color themes of the terminal UI."""

from __future__ import annotations

from fastapi import APIRouter

from terminal_radio.dependencies import ThemeRepositoryDep
from terminal_radio.schemas import ThemeListRead

router = APIRouter(prefix="/themes", tags=["themes"])


@router.get("", response_model=ThemeListRead, summary="List themes")
def list_themes(themes: ThemeRepositoryDep) -> ThemeListRead:
    """Return every theme defined in the theme file."""
    return ThemeListRead.from_domain(themes.all(), themes.default_name)

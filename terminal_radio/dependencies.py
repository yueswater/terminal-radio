"""FastAPI dependency providers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from terminal_radio.core.config import Settings, get_settings
from terminal_radio.services import RadioService, ThemeRepository


def provide_settings() -> Settings:
    """Return the cached application settings."""
    return get_settings()


def provide_radio_service(request: Request) -> RadioService:
    """Return the radio service created during application startup."""
    return request.app.state.radio_service


def provide_theme_repository(request: Request) -> ThemeRepository:
    """Return the theme repository created during application startup."""
    return request.app.state.themes


SettingsDep = Annotated[Settings, Depends(provide_settings)]
RadioServiceDep = Annotated[RadioService, Depends(provide_radio_service)]
ThemeRepositoryDep = Annotated[ThemeRepository, Depends(provide_theme_repository)]

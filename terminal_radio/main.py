"""FastAPI application factory and ASGI entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from terminal_radio.core.config import Settings, get_settings
from terminal_radio.core.exceptions import PlayerError, RadioError, StationNotFoundError
from terminal_radio.routers import api_router
from terminal_radio.services import RadioService, ThemeRepository, build_radio_service


def create_app(
    settings: Settings | None = None, service: RadioService | None = None
) -> FastAPI:
    """Build a configured FastAPI application.

    A service may be supplied by a caller that already owns one, such as the
    terminal UI serving the control socket alongside its own interface. Only
    the application that built the service shuts it down: borrowing one and
    stopping it would silence a radio somebody else is still holding.
    """
    settings = settings or get_settings()
    borrowed = service is not None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Own the radio service for the lifetime of the application."""
        app.state.settings = settings
        app.state.radio_service = service or build_radio_service(settings)
        app.state.themes = ThemeRepository.from_file(settings.themes_file)
        try:
            yield
        finally:
            if not borrowed:
                app.state.radio_service.stop()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.include_router(api_router)
    register_exception_handlers(app)
    return app


def register_exception_handlers(app: FastAPI) -> None:
    """Map domain errors onto HTTP responses."""

    @app.exception_handler(StationNotFoundError)
    async def handle_station_not_found(
        request: Request, error: StationNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(error)}
        )

    @app.exception_handler(PlayerError)
    async def handle_player_error(request: Request, error: PlayerError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": str(error)},
        )

    @app.exception_handler(RadioError)
    async def handle_radio_error(request: Request, error: RadioError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(error)},
        )


app = create_app()

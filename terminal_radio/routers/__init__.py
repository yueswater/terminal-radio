"""HTTP routers mounted by the FastAPI application."""

from fastapi import APIRouter

from terminal_radio.routers import history, player, stations, themes

api_router = APIRouter()
api_router.include_router(stations.router)
api_router.include_router(player.router)
api_router.include_router(history.router)
api_router.include_router(themes.router)

__all__ = ["api_router"]

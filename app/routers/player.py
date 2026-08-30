"""Endpoints controlling playback."""

from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import RadioServiceDep
from app.schemas import PlayerStatusRead, PlayRequest

router = APIRouter(prefix="/player", tags=["player"])


@router.get("", response_model=PlayerStatusRead, summary="Get playback status")
def read_status(service: RadioServiceDep) -> PlayerStatusRead:
    """Return what the player is doing right now."""
    return PlayerStatusRead.from_domain(service.status())


@router.post("/play", response_model=PlayerStatusRead, summary="Play a station")
def play(payload: PlayRequest, service: RadioServiceDep) -> PlayerStatusRead:
    """Start playing the requested station."""
    return PlayerStatusRead.from_domain(service.play(payload.slug))


@router.post("/toggle", response_model=PlayerStatusRead, summary="Toggle a station")
def toggle(payload: PlayRequest, service: RadioServiceDep) -> PlayerStatusRead:
    """Stop the requested station when it is loaded, otherwise start it."""
    return PlayerStatusRead.from_domain(service.toggle(payload.slug))


@router.post("/pause", response_model=PlayerStatusRead, summary="Pause playback")
def pause(service: RadioServiceDep) -> PlayerStatusRead:
    """Pause the loaded stream."""
    return PlayerStatusRead.from_domain(service.pause())


@router.post("/resume", response_model=PlayerStatusRead, summary="Resume playback")
def resume(service: RadioServiceDep) -> PlayerStatusRead:
    """Resume the paused stream."""
    return PlayerStatusRead.from_domain(service.resume())


@router.post("/stop", response_model=PlayerStatusRead, summary="Stop playback")
def stop(service: RadioServiceDep) -> PlayerStatusRead:
    """Stop playback."""
    return PlayerStatusRead.from_domain(service.stop())

"""Endpoints controlling playback."""

from __future__ import annotations

from fastapi import APIRouter

from terminal_radio.dependencies import RadioServiceDep
from terminal_radio.core.exceptions import RadioError
from terminal_radio.schemas import (
    MuteRequest,
    PlayerStatusRead,
    PlayRequest,
    SleepRequest,
    VolumeRequest,
)

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


@router.post("/volume", response_model=PlayerStatusRead, summary="Set the volume")
def set_volume(payload: VolumeRequest, service: RadioServiceDep) -> PlayerStatusRead:
    """Set an absolute level, or move the current one by a step."""
    if payload.level is not None:
        return PlayerStatusRead.from_domain(service.set_volume(payload.level))
    if payload.delta is not None:
        return PlayerStatusRead.from_domain(service.adjust_volume(payload.delta))
    return PlayerStatusRead.from_domain(service.status())


@router.post("/mute", response_model=PlayerStatusRead, summary="Mute or unmute")
def set_muted(payload: MuteRequest, service: RadioServiceDep) -> PlayerStatusRead:
    """Silence the output, or bring it back."""
    if service.status().muted != payload.muted:
        service.toggle_mute()
    return PlayerStatusRead.from_domain(service.status())


@router.post("/sleep", response_model=PlayerStatusRead, summary="Set the sleep timer")
def set_sleep_timer(
    payload: SleepRequest, service: RadioServiceDep
) -> PlayerStatusRead:
    """Stop playback after the given number of minutes, or cancel the timer."""
    try:
        return PlayerStatusRead.from_domain(service.set_sleep_timer(payload.minutes))
    except ValueError as error:
        raise RadioError(str(error)) from error

"""Use cases combining the station catalog, an audio backend and the history."""

from __future__ import annotations

import time

from app.core.config import Settings, get_settings
from app.core.exceptions import StationNotFoundError
from app.models import (
    Band,
    HistoryEvent,
    HistoryEventType,
    PlaybackState,
    PlayerStatus,
    Station,
)
from app.services.catalog import StationCatalog
from app.services.history import HistoryLog, StationSummary, build_event
from app.services.player import MpvPlayer, Player
from app.services.state import PersistedState, StateStore


class RadioService:
    """Single entry point used by both the terminal UI and the HTTP API."""

    def __init__(
        self,
        catalog: StationCatalog,
        player: Player,
        history: HistoryLog,
        state: StateStore,
        autoplay_last_station: bool = True,
        enable_animations: bool = False,
    ) -> None:
        self._catalog = catalog
        self._player = player
        self._history = history
        self._state = state

        # A choice made on the settings page outlives the environment default.
        stored = state.load()
        self._autoplay = (
            autoplay_last_station
            if stored.autoplay_last_station is None
            else stored.autoplay_last_station
        )
        self._animations = (
            enable_animations
            if stored.enable_animations is None
            else stored.enable_animations
        )
        self._favorites = list(stored.favorites)
        self._player.set_volume(stored.volume)
        self._player.set_muted(stored.muted)

        self._session_listened = 0.0
        self._current: Station | None = None
        self._started_at: float | None = None
        self._paused_at: float | None = None
        self._paused_total = 0.0

    @property
    def catalog(self) -> StationCatalog:
        """Return the underlying station catalog."""
        return self._catalog

    def list_stations(self, band: Band | None = None) -> tuple[Station, ...]:
        """Return every station, optionally restricted to one band."""
        return self._catalog.by_band(band) if band else self._catalog.all()

    def favorites(self) -> tuple[Station, ...]:
        """Return the starred stations, in catalog order."""
        return tuple(
            station for station in self._catalog.all() if station.slug in self._favorites
        )

    def is_favorite(self, slug: str) -> bool:
        """Return whether the given station is starred."""
        return slug in self._favorites

    def toggle_favorite(self, slug: str) -> bool:
        """Star or unstar a station and return its new state."""
        self._catalog.get(slug)
        if slug in self._favorites:
            self._favorites.remove(slug)
        else:
            self._favorites.append(slug)

        self._state.update(favorites=list(self._favorites))
        return slug in self._favorites

    def get_station(self, slug: str) -> Station:
        """Return one station or raise StationNotFoundError."""
        return self._catalog.get(slug)

    def last_station(self) -> Station | None:
        """Return the station played during the previous run, when it still exists."""
        slug = self._state.load().last_station_slug
        if slug is None:
            return None
        try:
            return self._catalog.get(slug)
        except StationNotFoundError:
            return None

    def start_session(self) -> PlayerStatus:
        """Log the session start and resume the last station when autoplay is on."""
        self._history.append(build_event(HistoryEventType.SESSION_STARTED))

        station = self.last_station()
        if self._autoplay and station is not None:
            return self.play(station.slug)
        return self.status()

    def end_session(self) -> None:
        """Stop playback and log the session end."""
        self.stop()
        self._history.append(build_event(HistoryEventType.SESSION_ENDED))

    def status(self) -> PlayerStatus:
        """Return the playback status, reconciled with the backend process."""
        if not self._player.is_running:
            self._reset_play()
            return PlayerStatus(
                volume=self._player.volume,
                muted=self._player.is_muted,
                device=self._player.device(),
            )

        state = PlaybackState.PAUSED if self._player.is_paused else PlaybackState.PLAYING
        return PlayerStatus(
            state=state,
            station=self._current,
            program=self._player.program(),
            elapsed_seconds=self._elapsed_seconds(),
            paused_seconds=self._paused_seconds(),
            volume=self._player.volume,
            muted=self._player.is_muted,
            device=self._player.device(),
        )

    def play(self, slug: str) -> PlayerStatus:
        """Start playing the given station, closing the previous play entry."""
        station = self._catalog.get(slug)
        self._finish_play()
        self._player.start(station.url)

        self._current = station
        self._started_at = time.monotonic()
        self._paused_at = None
        self._paused_total = 0.0

        self._history.append(build_event(HistoryEventType.PLAY_STARTED, station))
        self._state.update(last_station_slug=station.slug)
        return self.status()

    def stop(self) -> PlayerStatus:
        """Stop playback and close the current play entry."""
        self._finish_play()
        self._player.stop()
        self._reset_play()
        return self.status()

    def toggle(self, slug: str) -> PlayerStatus:
        """Stop the given station when it is loaded, otherwise start it."""
        if self._current is not None and self._current.slug == slug and self._player.is_running:
            return self.stop()
        return self.play(slug)

    def pause(self) -> PlayerStatus:
        """Pause the loaded stream and start counting paused time."""
        if not self._player.is_running or self._player.is_paused:
            return self.status()

        self._player.set_paused(True)
        self._paused_at = time.monotonic()
        self._history.append(build_event(HistoryEventType.PAUSED, self._current))
        return self.status()

    def resume(self) -> PlayerStatus:
        """Resume the loaded stream and log how long it stayed paused."""
        if not self._player.is_running or not self._player.is_paused:
            return self.status()

        paused_seconds = self._close_pause()
        self._player.set_paused(False)
        self._history.append(
            build_event(
                HistoryEventType.RESUMED,
                self._current,
                duration_seconds=paused_seconds,
                paused_seconds=paused_seconds,
            )
        )
        return self.status()

    def toggle_pause(self) -> PlayerStatus:
        """Pause a playing stream or resume a paused one."""
        if not self._player.is_running:
            return self.status()
        return self.resume() if self._player.is_paused else self.pause()

    @property
    def autoplay(self) -> bool:
        """Return whether the last station is resumed on startup."""
        return self._autoplay

    def set_autoplay(self, autoplay: bool) -> bool:
        """Store whether the last station should be resumed on startup."""
        self._autoplay = autoplay
        self._state.update(autoplay_last_station=autoplay)
        return self._autoplay

    @property
    def animations(self) -> bool:
        """Return whether the UI animates its transitions."""
        return self._animations

    def set_animations(self, enabled: bool) -> bool:
        """Store whether the UI should animate its transitions."""
        self._animations = enabled
        self._state.update(enable_animations=enabled)
        return self._animations

    def volume(self) -> int:
        """Return the current output volume in percent."""
        return self._player.volume

    def set_volume(self, volume: int) -> PlayerStatus:
        """Set the output volume and remember it for the next run."""
        self._player.set_volume(volume)
        self._state.update(volume=self._player.volume)
        return self.status()

    def adjust_volume(self, delta: int) -> PlayerStatus:
        """Move the output volume by the given number of percent points."""
        return self.set_volume(self._player.volume + delta)

    def toggle_mute(self) -> PlayerStatus:
        """Mute or unmute the output and remember the choice."""
        self._player.set_muted(not self._player.is_muted)
        self._state.update(muted=self._player.is_muted)
        return self.status()

    def theme_name(self) -> str | None:
        """Return the theme chosen during a previous run, if any."""
        return self._state.load().theme_name

    def remember_theme(self, name: str) -> None:
        """Persist the theme so the next run starts with it."""
        self._state.update(theme_name=name)

    def preferences(self) -> PersistedState:
        """Return the preferences as they are stored on disk."""
        return self._state.load()

    def apply_preferences(self, incoming: PersistedState) -> PersistedState:
        """Adopt imported preferences, dropping the parts this catalog cannot serve."""
        known = {station.slug for station in self._catalog.all()}
        favorites = [slug for slug in incoming.favorites if slug in known]
        last = incoming.last_station_slug if incoming.last_station_slug in known else None

        merged = incoming.model_copy(
            update={"favorites": favorites, "last_station_slug": last}
        )
        current = self._state.load()
        if merged.autoplay_last_station is None:
            merged = merged.model_copy(
                update={"autoplay_last_station": current.autoplay_last_station}
            )
        if merged.enable_animations is None:
            merged = merged.model_copy(
                update={"enable_animations": current.enable_animations}
            )

        self._favorites = favorites
        self._autoplay = bool(merged.autoplay_last_station)
        self._animations = bool(merged.enable_animations)
        self._player.set_volume(merged.volume)
        self._player.set_muted(merged.muted)

        self._state.save(merged)
        return merged

    def reset_settings(
        self,
        *,
        autoplay: bool,
        animations: bool,
        locale: str,
        theme_name: str,
    ) -> PersistedState:
        """Restore app settings while preserving favorites and the last station."""
        current = self._state.load()
        defaults = PersistedState()
        restored = current.model_copy(
            update={
                "theme_name": theme_name,
                "volume": defaults.volume,
                "muted": defaults.muted,
                "autoplay_last_station": autoplay,
                "enable_animations": animations,
                "locale": locale,
            }
        )

        self._autoplay = autoplay
        self._animations = animations
        self._player.set_volume(restored.volume)
        self._player.set_muted(restored.muted)
        self._state.save(restored)
        return restored

    def locale_code(self) -> str | None:
        """Return the language chosen during a previous run, if any."""
        return self._state.load().locale

    def remember_locale(self, code: str) -> None:
        """Persist the language so the next run starts with it."""
        self._state.update(locale=code)

    def session_listened_seconds(self) -> float:
        """Return the time listened during this run, the current play included."""
        running = max(self._elapsed_seconds() - self._paused_seconds(), 0.0)
        return self._session_listened + running

    def history(self, limit: int | None = None) -> tuple[HistoryEvent, ...]:
        """Return the most recent history events, newest first."""
        return self._history.read(limit)

    def clear_history(self) -> bool:
        """Remove every persisted listening event."""
        return self._history.clear()

    def summaries(self, limit: int | None = None) -> tuple[StationSummary, ...]:
        """Return listening totals per station, most listened first."""
        return self._history.summarize(limit)

    def _elapsed_seconds(self) -> float:
        """Return the wall clock time since the current play entry started."""
        return 0.0 if self._started_at is None else time.monotonic() - self._started_at

    def _paused_seconds(self) -> float:
        """Return the paused time of the current play entry, pause in progress included."""
        running = 0.0 if self._paused_at is None else time.monotonic() - self._paused_at
        return self._paused_total + running

    def _close_pause(self) -> float:
        """Fold the running pause into the total and return its length."""
        if self._paused_at is None:
            return 0.0

        paused_seconds = time.monotonic() - self._paused_at
        self._paused_total += paused_seconds
        self._paused_at = None
        return paused_seconds

    def _finish_play(self) -> None:
        """Log the end of the current play entry, if there is one."""
        if self._current is None or self._started_at is None:
            return

        self._close_pause()
        duration = time.monotonic() - self._started_at
        self._session_listened += max(duration - self._paused_total, 0.0)
        self._history.append(
            build_event(
                HistoryEventType.PLAY_ENDED,
                self._current,
                duration_seconds=duration,
                paused_seconds=self._paused_total,
            )
        )

    def _reset_play(self) -> None:
        """Forget everything about the current play entry."""
        self._current = None
        self._started_at = None
        self._paused_at = None
        self._paused_total = 0.0


def build_radio_service(settings: Settings | None = None) -> RadioService:
    """Assemble a radio service from settings, wiring the default mpv backend."""
    settings = settings or get_settings()
    return RadioService(
        catalog=StationCatalog.from_file(settings.stations_file),
        player=MpvPlayer(settings.player_command, settings.ipc_socket),
        history=HistoryLog(settings.history_file, settings.history_limit),
        state=StateStore(settings.state_file),
        autoplay_last_station=settings.autoplay_last_station,
        enable_animations=settings.enable_animations,
    )

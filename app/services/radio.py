"""Use cases combining the station catalog, an audio backend and the history."""

from __future__ import annotations

import time
from collections.abc import Callable

from app.core.config import Settings, get_settings
from app.core.exceptions import CatalogError, PlayerError, StationNotFoundError
from app.enums import Band, HistoryEventType, PlaybackState
from app.models import HistoryEvent, PlayerStatus, Station
from app.services.catalog import StationCatalog
from app.services.analytics import ListeningStatistics, build_listening_statistics
from app.services.custom_stations import CustomStationStore
from app.services.history import HistoryLog, StationSummary, build_event
from app.services.player import MpvPlayer, Player
from app.services.reconnect import ReconnectSchedule
from app.services.sleep_timer import SleepTimer
from app.services.state import PersistedState, StateStore
from app.services.station_library import StationLibrary
from app.services.station_health import StationHealthService, StationHealthSnapshot


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
        auto_reconnect: bool = True,
        reconnect: ReconnectSchedule | None = None,
        sleep_timer: SleepTimer | None = None,
        clock: Callable[[], float] = time.monotonic,
        station_library: StationLibrary | None = None,
        auto_health_check: bool = True,
        station_health: StationHealthService | None = None,
    ) -> None:
        self._catalog = catalog
        self._station_library = station_library
        self._station_health = station_health or StationHealthService()
        self._player = player
        self._history = history
        self._state = state
        self._clock = clock
        self._reconnect = reconnect or ReconnectSchedule(clock)
        self._sleep_timer = sleep_timer or SleepTimer(clock)

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
        self._auto_reconnect = (
            auto_reconnect if stored.auto_reconnect is None else stored.auto_reconnect
        )
        self._auto_health_check = (
            auto_health_check
            if stored.auto_health_check is None
            else stored.auto_health_check
        )
        self._favorites = list(stored.favorites)
        self._player.set_volume(stored.volume)
        self._player.set_muted(stored.muted)

        self._session_listened = 0.0
        self._current: Station | None = None
        self._started_at: float | None = None
        self._paused_at: float | None = None
        self._paused_total = 0.0
        self._interrupted_at: float | None = None
        self._interrupted_total = 0.0

    @property
    def catalog(self) -> StationCatalog:
        """Return the underlying station catalog."""
        if self._station_library is not None:
            return self._station_library.catalog
        return self._catalog

    def list_stations(self, band: Band | None = None) -> tuple[Station, ...]:
        """Return every station, optionally restricted to one band."""
        return self.catalog.by_band(band) if band else self.catalog.all()

    def favorites(self) -> tuple[Station, ...]:
        """Return the starred stations, in catalog order."""
        return tuple(
            station for station in self.catalog.all() if station.slug in self._favorites
        )

    def is_favorite(self, slug: str) -> bool:
        """Return whether the given station is starred."""
        return slug in self._favorites

    def toggle_favorite(self, slug: str) -> bool:
        """Star or unstar a station and return its new state."""
        self.catalog.get(slug)
        if slug in self._favorites:
            self._favorites.remove(slug)
        else:
            self._favorites.append(slug)

        self._state.update(favorites=list(self._favorites))
        return slug in self._favorites

    def get_station(self, slug: str) -> Station:
        """Return one station or raise StationNotFoundError."""
        return self.catalog.get(slug)

    def search_stations(self, query: str) -> tuple[Station, ...]:
        """Search every station display field in catalog order."""
        if self._station_library is not None:
            return self._station_library.search(query)
        wanted = query.strip().casefold()
        if not wanted:
            return self.catalog.all()
        return tuple(
            item
            for item in self.catalog.all()
            if wanted
            in " ".join(
                (
                    item.dial,
                    item.name,
                    item.short_name or "",
                    item.description or "",
                    item.band.value,
                )
            ).casefold()
        )

    def custom_stations(self) -> tuple[Station, ...]:
        """Return user-defined stations in their saved order."""
        if self._station_library is None:
            return ()
        return self._station_library.custom_stations

    def add_custom_station(
        self,
        *,
        name: str,
        band: Band,
        url: str,
        frequency: str | None = None,
        description: str | None = None,
    ) -> Station:
        """Add one local custom station."""
        return self._require_station_library().add_custom(
            name=name,
            band=band,
            url=url,
            frequency=frequency,
            description=description,
        )

    def update_custom_station(
        self,
        slug: str,
        *,
        name: str,
        band: Band,
        url: str,
        frequency: str | None = None,
        description: str | None = None,
    ) -> Station:
        """Edit one local custom station without changing its slug."""
        changed = self._require_station_library().update_custom(
            slug,
            name=name,
            band=band,
            url=url,
            frequency=frequency,
            description=description,
        )
        if self._current is not None and self._current.slug == slug:
            self._current = changed
        return changed

    def delete_custom_station(self, slug: str) -> Station:
        """Delete one custom station and clean its remembered state."""
        library = self._require_station_library()
        if self._current is not None and self._current.slug == slug:
            self.stop()
        removed = library.delete_custom(slug)
        self._favorites = [item for item in self._favorites if item != slug]
        stored = self._state.load()
        self._state.save(
            stored.model_copy(
                update={
                    "favorites": list(self._favorites),
                    "last_station_slug": (
                        None
                        if stored.last_station_slug == slug
                        else stored.last_station_slug
                    ),
                }
            )
        )
        return removed

    def _require_station_library(self) -> StationLibrary:
        """Return the mutable local library or raise a clear domain error."""
        if self._station_library is None:
            raise CatalogError("Custom station storage is unavailable")
        return self._station_library

    def last_station(self) -> Station | None:
        """Return the station played during the previous run, when it still exists."""
        slug = self._state.load().last_station_slug
        if slug is None:
            return None
        try:
            return self.catalog.get(slug)
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
        if self._sleep_timer.expired():
            return self.stop()

        if not self._player.is_running:
            return self._status_for_stopped_player()

        if self._reconnect.stabilizing:
            if self._reconnect.stable:
                self._reconnect.reset()
            else:
                return self._player_status(PlaybackState.RECONNECTING)

        state = PlaybackState.PAUSED if self._player.is_paused else PlaybackState.PLAYING
        return self._player_status(state)

    def play(self, slug: str) -> PlayerStatus:
        """Start playing the given station, closing the previous play entry."""
        station = self.catalog.get(slug)
        self._finish_play()
        self._reconnect.reset()
        self._reset_play()
        self._player.start(station.url)

        self._current = station
        self._started_at = self._clock()
        self._paused_at = None
        self._paused_total = 0.0

        self._history.append(build_event(HistoryEventType.PLAY_STARTED, station))
        self._state.update(last_station_slug=station.slug)
        return self.status()

    def stop(self) -> PlayerStatus:
        """Stop playback and close the current play entry."""
        self._finish_play()
        self._reconnect.reset()
        self._sleep_timer.cancel()
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
        self._paused_at = self._clock()
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

    @property
    def auto_reconnect(self) -> bool:
        """Return whether unexpected stream exits should be retried."""
        return self._auto_reconnect

    def set_auto_reconnect(self, enabled: bool) -> bool:
        """Persist automatic reconnect and cancel pending retries when disabled."""
        self._auto_reconnect = enabled
        self._state.update(auto_reconnect=enabled)
        if not enabled and self._reconnect.active:
            if self._player.is_running:
                self._reconnect.reset()
            else:
                self._finish_play()
                self._reconnect.reset()
                self._reset_play()
        return self._auto_reconnect

    @property
    def auto_health_check(self) -> bool:
        """Return whether active station tabs are checked automatically."""
        return self._auto_health_check

    def set_auto_health_check(self, enabled: bool) -> bool:
        """Persist automatic station availability checks."""
        self._auto_health_check = enabled
        self._state.update(auto_health_check=enabled)
        return self._auto_health_check

    def station_health(self, slug: str) -> StationHealthSnapshot:
        """Return the current non-blocking health snapshot for one station."""
        self.catalog.get(slug)
        return self._station_health.snapshot(slug)

    def check_station_health(
        self,
        stations: tuple[Station, ...] | None = None,
        *,
        force: bool = False,
    ) -> tuple[StationHealthSnapshot, ...]:
        """Synchronously probe a station batch; callers run this off the UI thread."""
        return self._station_health.check_many(
            stations or self.catalog.all(), force=force
        )

    def set_sleep_timer(self, minutes: int | None) -> PlayerStatus:
        """Set or cancel the session-only sleep timer."""
        self._sleep_timer.set_minutes(minutes)
        return self.status()

    def sleep_remaining_seconds(self) -> float | None:
        """Return the active sleep timer countdown."""
        return self._sleep_timer.remaining_seconds()

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
        known = {station.slug for station in self.catalog.all()}
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
        if merged.auto_reconnect is None:
            merged = merged.model_copy(
                update={"auto_reconnect": self._auto_reconnect}
            )
        if merged.auto_health_check is None:
            merged = merged.model_copy(
                update={"auto_health_check": self._auto_health_check}
            )

        self._favorites = favorites
        self._autoplay = bool(merged.autoplay_last_station)
        self._animations = bool(merged.enable_animations)
        self._auto_reconnect = bool(merged.auto_reconnect)
        self._auto_health_check = bool(merged.auto_health_check)
        self._player.set_volume(merged.volume)
        self._player.set_muted(merged.muted)

        self._state.save(merged)
        return merged

    def apply_import(
        self,
        incoming: PersistedState,
        custom_stations: tuple[Station, ...] | None,
    ) -> PersistedState:
        """Atomically validate custom stations before adopting imported preferences."""
        if custom_stations is not None:
            self._require_station_library().replace_custom(custom_stations)
        return self.apply_preferences(incoming)

    def reset_settings(
        self,
        *,
        autoplay: bool,
        animations: bool,
        auto_reconnect: bool,
        auto_health_check: bool,
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
                "auto_reconnect": auto_reconnect,
                "auto_health_check": auto_health_check,
                "locale": locale,
            }
        )

        self._autoplay = autoplay
        self._animations = animations
        self._auto_reconnect = auto_reconnect
        self._auto_health_check = auto_health_check
        self._reconnect.reset()
        self._sleep_timer.cancel()
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
        running = max(
            self._elapsed_seconds()
            - self._paused_seconds()
            - self._interrupted_seconds(),
            0.0,
        )
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

    def all_summaries(self) -> tuple[StationSummary, ...]:
        """Return listening totals from the complete valid history log."""
        return self._history.summarize_all()

    def listening_statistics(self) -> ListeningStatistics:
        """Aggregate the complete valid history for the statistics page."""
        short_names = {
            station.slug: station.short_name
            for station in self.catalog.all()
            if station.short_name
        }
        return build_listening_statistics(
            self._history.read_all(), station_short_names=short_names
        )

    def _elapsed_seconds(self) -> float:
        """Return the wall clock time since the current play entry started."""
        return 0.0 if self._started_at is None else self._clock() - self._started_at

    def _paused_seconds(self) -> float:
        """Return the paused time of the current play entry, pause in progress included."""
        running = 0.0 if self._paused_at is None else self._clock() - self._paused_at
        return self._paused_total + running

    def _close_pause(self) -> float:
        """Fold the running pause into the total and return its length."""
        if self._paused_at is None:
            return 0.0

        paused_seconds = self._clock() - self._paused_at
        self._paused_total += paused_seconds
        self._paused_at = None
        return paused_seconds

    def _begin_interruption(self) -> None:
        """Start counting a playback outage once."""
        if self._interrupted_at is None:
            self._interrupted_at = self._clock()

    def _close_interruption(self) -> float:
        """Fold an active outage into the current play total."""
        if self._interrupted_at is None:
            return 0.0
        interrupted = self._clock() - self._interrupted_at
        self._interrupted_total += interrupted
        self._interrupted_at = None
        return interrupted

    def _interrupted_seconds(self) -> float:
        """Return completed and currently running outage time."""
        running = (
            0.0
            if self._interrupted_at is None
            else self._clock() - self._interrupted_at
        )
        return self._interrupted_total + running

    def _status_for_stopped_player(self) -> PlayerStatus:
        """Advance reconnect state after observing a dead backend."""
        if self._current is None or self._started_at is None:
            self._reconnect.reset()
            return self._player_status(PlaybackState.STOPPED)

        self._begin_interruption()
        if not self._auto_reconnect:
            self._finish_play()
            self._reset_play()
            return self._player_status(PlaybackState.STOPPED)

        if self._reconnect.stabilizing:
            if not self._reconnect.record_failure():
                self._finish_play()
                self._reset_play()
                return self._player_status(PlaybackState.STOPPED)
        elif not self._reconnect.active:
            self._reconnect.start()

        if self._reconnect.ready:
            self._reconnect.record_attempt()
            try:
                self._player.start(self._current.url)
            except PlayerError:
                if not self._reconnect.record_failure():
                    self._finish_play()
                    self._reset_play()
                    return self._player_status(PlaybackState.STOPPED)
            else:
                self._close_interruption()

        return self._player_status(PlaybackState.RECONNECTING)

    def _player_status(self, state: PlaybackState) -> PlayerStatus:
        """Build one status snapshot from current in-memory state."""
        return PlayerStatus(
            state=state,
            station=self._current,
            program=self._player.program() if self._player.is_running else None,
            elapsed_seconds=self._elapsed_seconds(),
            paused_seconds=self._paused_seconds(),
            volume=self._player.volume,
            muted=self._player.is_muted,
            device=self._player.device(),
            reconnect_attempt=self._reconnect.attempt,
            sleep_remaining_seconds=self._sleep_timer.remaining_seconds(),
        )

    def _finish_play(self) -> None:
        """Log the end of the current play entry, if there is one."""
        if self._current is None or self._started_at is None:
            return

        self._close_pause()
        self._close_interruption()
        duration = self._clock() - self._started_at
        self._session_listened += max(
            duration - self._paused_total - self._interrupted_total,
            0.0,
        )
        self._history.append(
            build_event(
                HistoryEventType.PLAY_ENDED,
                self._current,
                duration_seconds=duration,
                paused_seconds=self._paused_total,
                interrupted_seconds=self._interrupted_total,
            )
        )

    def _reset_play(self) -> None:
        """Forget everything about the current play entry."""
        self._current = None
        self._started_at = None
        self._paused_at = None
        self._paused_total = 0.0
        self._interrupted_at = None
        self._interrupted_total = 0.0


def build_radio_service(settings: Settings | None = None) -> RadioService:
    """Assemble a radio service from settings, wiring the default mpv backend."""
    settings = settings or get_settings()
    library = StationLibrary(
        StationCatalog.from_file(settings.stations_file),
        CustomStationStore(settings.custom_stations_file),
    )
    return RadioService(
        catalog=library.catalog,
        player=MpvPlayer(settings.player_command, settings.ipc_socket),
        history=HistoryLog(settings.history_file, settings.history_limit),
        state=StateStore(settings.state_file),
        autoplay_last_station=settings.autoplay_last_station,
        enable_animations=settings.enable_animations,
        auto_reconnect=settings.auto_reconnect,
        station_library=library,
        auto_health_check=settings.auto_health_check,
    )

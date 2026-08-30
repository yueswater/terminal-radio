"""Cached, bounded stream availability checks."""

from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen
from collections.abc import Callable, Sequence
from typing import Protocol

from terminal_radio.constants.station import (
    STATION_HEALTH_CACHE_SECONDS,
    STATION_HEALTH_MAX_WORKERS,
    STATION_PROBE_TIMEOUT_SECONDS,
    STATION_SLOW_SECONDS,
)
from terminal_radio.enums import StationHealth
from terminal_radio.models import Station


class UrlOpener(Protocol):
    def __call__(self, request: Request, *, timeout: float) -> object: ...


@dataclass(frozen=True)
class StationHealthSnapshot:
    """One cached result of probing a station stream."""

    station_slug: str
    health: StationHealth
    latency_seconds: float | None
    checked_at: float


class StationHealthService:
    """Probe streams without duplicate work or unbounded concurrency."""

    def __init__(
        self,
        *,
        opener: UrlOpener = urlopen,
        clock: Callable[[], float] = time.monotonic,
        cache_seconds: float = STATION_HEALTH_CACHE_SECONDS,
    ) -> None:
        self._opener = opener
        self._clock = clock
        self._cache_seconds = cache_seconds
        self._cache: dict[str, StationHealthSnapshot] = {}
        self._inflight: dict[str, Future[StationHealthSnapshot]] = {}
        self._lock = threading.Lock()

    def snapshot(self, slug: str) -> StationHealthSnapshot:
        """Return current cached/checking/unknown state without doing I/O."""
        with self._lock:
            cached = self._fresh_cached(slug)
            if cached is not None:
                return cached
            if slug in self._inflight:
                return StationHealthSnapshot(
                    slug, StationHealth.CHECKING, None, self._clock()
                )
        return StationHealthSnapshot(slug, StationHealth.UNKNOWN, None, self._clock())

    def check(self, station: Station, *, force: bool = False) -> StationHealthSnapshot:
        """Return a cached result or synchronously probe one stream."""
        with self._lock:
            if not force:
                cached = self._fresh_cached(station.slug)
                if cached is not None:
                    return cached
            future = self._inflight.get(station.slug)
            owner = future is None
            if future is None:
                future = Future()
                self._inflight[station.slug] = future

        if not owner:
            return future.result()

        try:
            result = self._probe(station)
        except Exception as error:
            future.set_exception(error)
            with self._lock:
                self._inflight.pop(station.slug, None)
            raise

        with self._lock:
            self._cache[station.slug] = result
            self._inflight.pop(station.slug, None)
        future.set_result(result)
        return result

    def check_many(
        self,
        stations: Sequence[Station],
        *,
        force: bool = False,
    ) -> tuple[StationHealthSnapshot, ...]:
        """Probe a batch with four worker threads at most, preserving order."""
        items = tuple(stations)
        if not items:
            return ()
        with ThreadPoolExecutor(
            max_workers=min(STATION_HEALTH_MAX_WORKERS, len(items))
        ) as executor:
            futures = [
                executor.submit(self.check, item, force=force) for item in items
            ]
            return tuple(future.result() for future in futures)

    def _fresh_cached(self, slug: str) -> StationHealthSnapshot | None:
        cached = self._cache.get(slug)
        if cached is None:
            return None
        if self._clock() - cached.checked_at >= self._cache_seconds:
            self._cache.pop(slug, None)
            return None
        return cached

    def _probe(self, station: Station) -> StationHealthSnapshot:
        started = self._clock()
        request = Request(
            station.url,
            headers={"Range": "bytes=0-0", "User-Agent": "radio/0.1"},
            method="GET",
        )
        try:
            with self._opener(
                request, timeout=STATION_PROBE_TIMEOUT_SECONDS
            ) as response:
                response.read(1)
        except (OSError, TimeoutError, URLError, ValueError):
            return StationHealthSnapshot(
                station.slug,
                StationHealth.OFFLINE,
                None,
                self._clock(),
            )

        elapsed = max(self._clock() - started, 0.0)
        health = (
            StationHealth.SLOW
            if elapsed >= STATION_SLOW_SECONDS
            else StationHealth.ONLINE
        )
        return StationHealthSnapshot(
            station.slug,
            health,
            elapsed,
            self._clock(),
        )

"""Relógio da gravação: conta só o tempo gravado (pausas não entram)."""

from __future__ import annotations

import time
from collections.abc import Callable


class RecordingClock:
    def __init__(self, time_fn: Callable[[], float] = time.perf_counter):
        self._time = time_fn
        self._start: float | None = None
        self._paused_at: float | None = None
        self._paused_total = 0.0

    def start(self) -> None:
        self._start = self._time()
        self._paused_at = None
        self._paused_total = 0.0

    @property
    def paused(self) -> bool:
        return self._paused_at is not None

    def pause(self) -> None:
        if self._start is not None and self._paused_at is None:
            self._paused_at = self._time()

    def resume(self) -> None:
        if self._paused_at is not None:
            self._paused_total += self._time() - self._paused_at
            self._paused_at = None

    def now_us(self) -> int:
        if self._start is None:
            return 0
        end = self._paused_at if self._paused_at is not None else self._time()
        return int(round((end - self._start - self._paused_total) * 1_000_000))

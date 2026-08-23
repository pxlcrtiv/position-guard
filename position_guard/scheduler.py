"""Scheduler loop used by `position-guard watch` — a fixed-interval poller
with graceful Ctrl-C and a run counter. Pure and testable (no sleep in
tests: inject a zero interval / mock time.sleep)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

log = logging.getLogger("position_guard.scheduler")


class WatchLoop:
    def __init__(
        self,
        interval: float,
        on_tick: Callable[[int], bool],
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.interval = max(0.0, interval)
        self.on_tick = on_tick
        self._sleep = sleep

    def run(self, max_ticks: int | None = None) -> int:
        """Run ticks until on_tick returns False, max_ticks is reached, or
        KeyboardInterrupt. Returns the number of completed ticks."""
        ticks = 0
        try:
            while max_ticks is None or ticks < max_ticks:
                ticks += 1
                if not self.on_tick(ticks):
                    break
                if self.interval and (max_ticks is None or ticks < max_ticks):
                    self._sleep(self.interval)
        except KeyboardInterrupt:
            log.info("watch stopped by user after %d ticks", ticks)
        return ticks
"""Section 8: high-frequency events are summarized, and repeating failures are not logged on every repeat."""
from __future__ import annotations

import threading
import time
from typing import Any, Callable

from .emit import EventLogger


class Summary:
    """Counts occurrences of a high-frequency success and writes one `events.summarized` line per window.

    `count()` is cheap and thread-safe; the line is written by whichever call crosses the window's end (or by
    `flush()`, e.g. at shutdown). A window with no occurrences writes nothing."""

    def __init__(self, logger: EventLogger, event: str, *, every_s: float = 300.0, key: str | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.logger, self.event, self.every_s, self.key, self.clock = logger, event, every_s, key, clock
        self._lock = threading.Lock()
        self._count = 0
        self._started = clock()

    def count(self, n: int = 1) -> None:
        with self._lock:
            self._count += n
            due = self.clock() - self._started >= self.every_s
        if due:
            self.flush()

    def flush(self) -> None:
        with self._lock:
            count, window = self._count, self.clock() - self._started
            self._count, self._started = 0, self.clock()
        if count:
            self.logger.event("events.summarized", summarizedEvent=self.event, count=count,
                              windowS=round(window, 1), key=self.key)


class FailureRun:
    """A dependency failing over and over: its first failure is written, repeats are counted, and recovery is
    written with how many failures it ended. The caller supplies the three declared events."""

    def __init__(self, logger: EventLogger, *, failed: str, recovered: str) -> None:
        self.logger, self.failed_event, self.recovered_event = logger, failed, recovered
        self._lock = threading.Lock()
        self._failures = 0

    def failed(self, error: BaseException | None = None, **attrs: Any) -> None:
        with self._lock:
            self._failures += 1
            first = self._failures == 1
        if first:
            self.logger.event(self.failed_event, error=error, **attrs)

    def succeeded(self, **attrs: Any) -> None:
        with self._lock:
            failures, self._failures = self._failures, 0
        if failures:
            self.logger.event(self.recovered_event, failures=failures, **attrs)


__all__ = ["FailureRun", "Summary"]

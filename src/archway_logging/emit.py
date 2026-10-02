"""Writing contract lines: one JSON object per line, one event per object (sections 2-7)."""
from __future__ import annotations

import datetime as _dt
import json
import logging
import sys
import threading
import traceback
from typing import Any, TextIO

from . import context as _context
from .catalogue import Catalogue
from .contract import LEVEL_RANK, MAX_MESSAGE_CHARS, MAX_STACK_CHARS, MAX_STACK_FRAMES
from .redact import redact

_STDLIB_LEVEL = {logging.DEBUG: "debug", logging.INFO: "info", logging.WARNING: "warn",
                 logging.ERROR: "error", logging.CRITICAL: "error"}


class UndeclaredEvent(ValueError):
    """Strict mode (tests): code emitted an event or attribute its catalogue does not declare."""


def error_object(exc: BaseException) -> dict[str, str]:
    """Section 6: one object -- type, bounded and redacted message, bounded stack."""
    frames = traceback.format_exception(type(exc), exc, exc.__traceback__)
    stack = "".join(frames[-MAX_STACK_FRAMES:])
    if len(stack) > MAX_STACK_CHARS:
        stack = "…" + stack[-(MAX_STACK_CHARS - 1):]
    return {"type": type(exc).__qualname__, "message": redact(str(exc), MAX_MESSAGE_CHARS),
            "stack": redact(stack, MAX_STACK_CHARS)}


def _value(value: Any, limit: int) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_value(item, limit) for item in list(value)[:50]]
    return redact(str(value), limit)


class EventLogger:
    """Emits a service's declared events. Created by `setup`; one per process."""

    def __init__(self, catalogue: Catalogue, *, release: str, stream: TextIO, level: str = "info",
                 strict: bool = False) -> None:
        self.catalogue = catalogue
        self.release = release
        self.stream = stream
        self.min_rank = LEVEL_RANK[level]
        self.strict = strict
        self._lock = threading.Lock()

    def _write(self, line: dict[str, Any]) -> None:
        text = json.dumps(line, separators=(",", ":"), ensure_ascii=False, default=str)
        with self._lock:
            self.stream.write(text + "\n")
            self.stream.flush()

    def event(self, name: str, msg: str | None = None, *, error: BaseException | None = None,
              level: str | None = None, **attrs: Any) -> None:
        """Write the declared event `name`. Undeclared events and attributes are never written: in strict mode
        they raise; otherwise a `logging.contract.violated` event says what was dropped."""
        spec = self.catalogue.events.get(name)
        undeclared = sorted(set(attrs) - set(spec.attrs)) if spec is not None else []
        if spec is None or undeclared:
            if self.strict:
                raise UndeclaredEvent(f"{name}: undeclared event" if spec is None
                                      else f"{name}: undeclared attributes {undeclared}")
            self.event("logging.contract.violated", undeclaredEvent=None if spec is not None else name,
                       undeclaredAttrs=",".join(undeclared) if spec is not None else None)
            if spec is None:
                return
            attrs = {k: v for k, v in attrs.items() if k in spec.attrs}
        chosen = level or spec.level
        if LEVEL_RANK[chosen] < self.min_rank:
            return
        line: dict[str, Any] = {
            "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": chosen, "service": self.catalogue.service, "release": self.release, "event": name,
            "msg": redact(msg or spec.description, MAX_MESSAGE_CHARS),
        }
        line.update(_context.current())
        written = {k: _value(v, spec.attrs[k].max_chars) for k, v in attrs.items() if v is not None}
        if written:
            line["attrs"] = written
        if error is not None:
            line["error"] = error_object(error)
        self._write(line)


class _StdlibHandler(logging.Handler):
    """Carries third-party libraries' logging into the contract as `library.log` events."""

    def __init__(self, logger: EventLogger) -> None:
        super().__init__()
        self.logger = logger

    def emit(self, record: logging.LogRecord) -> None:
        try:
            error = record.exc_info[1] if record.exc_info and record.exc_info[1] else None
            self.logger.event("library.log", level=_STDLIB_LEVEL.get(record.levelno, "info"), error=error,
                              logger=record.name, text=record.getMessage())
        except Exception:
            pass


_CURRENT: EventLogger | None = None


def setup(catalogue: Catalogue, *, release: str, stream: TextIO | None = None, level: str = "info",
          strict: bool = False, quiet: tuple[str, ...] = ()) -> EventLogger:
    """Make this process a contract-keeping service: our events, third-party logging and uncaught exceptions
    all become contract lines on `stream` (stdout). `quiet` names third-party loggers to silence entirely
    (e.g. a web server's own access log, which the service replaces with its declared one)."""
    global _CURRENT
    logger = EventLogger(catalogue, release=release, stream=stream or sys.stdout, level=level, strict=strict)
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.addHandler(_StdlibHandler(logger))
    root.setLevel(logging.DEBUG if level == "debug" else logging.INFO)
    for name in quiet:
        silenced = logging.getLogger(name)
        silenced.handlers.clear()
        silenced.propagate = False
        silenced.disabled = True

    def uncaught(exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
        logger.event("process.uncaught", error=exc.with_traceback(tb), thread="main")

    def uncaught_thread(args: threading.ExceptHookArgs) -> None:
        if args.exc_value is not None:
            logger.event("process.uncaught", error=args.exc_value,
                         thread=getattr(args.thread, "name", "") or "")

    sys.excepthook = uncaught
    threading.excepthook = uncaught_thread
    _CURRENT = logger
    return logger


def get() -> EventLogger:
    """The process's logger; `setup` must have run."""
    if _CURRENT is None:
        raise RuntimeError("archway_logging.setup has not run in this process")
    return _CURRENT


def event(name: str, msg: str | None = None, **kwargs: Any) -> None:
    get().event(name, msg, **kwargs)


__all__ = ["EventLogger", "UndeclaredEvent", "error_object", "event", "get", "setup"]

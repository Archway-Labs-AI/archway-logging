"""Request and execution identifiers attached to every line written while they are bound (section 3)."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Mapping

from .contract import CONTEXT_FIELDS

_CONTEXT: ContextVar[Mapping[str, str]] = ContextVar("archway_logging_context", default={})


@contextmanager
def bound(**fields: str | None) -> Iterator[None]:
    """Attach identifiers (requestId, traceId, executionId, ...) to every event written inside the block.
    Inner bindings add to outer ones; `None` values are ignored."""
    unknown = sorted(set(fields) - set(CONTEXT_FIELDS))
    if unknown:
        raise ValueError(f"not context fields: {unknown}; context fields are {CONTEXT_FIELDS}")
    merged = {**_CONTEXT.get(), **{k: str(v) for k, v in fields.items() if v is not None}}
    token = _CONTEXT.set(merged)
    try:
        yield
    finally:
        _CONTEXT.reset(token)


def current() -> dict[str, str]:
    return dict(_CONTEXT.get())


__all__ = ["bound", "current"]

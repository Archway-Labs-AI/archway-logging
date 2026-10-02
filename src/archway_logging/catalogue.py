"""A service's event catalogue (`CONTRACT.md` section 4): every event it may emit, declared."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from .contract import ATTRIBUTE_NAME, CADENCES, CLASSIFICATIONS, CONTEXT_FIELDS, EVENT_NAME, LEVELS
from .contract import DEFAULT_MAX_ATTRIBUTE_CHARS


class CatalogueError(ValueError):
    """A catalogue that breaks the contract."""


@dataclass(frozen=True)
class Attr:
    classification: str
    max_chars: int = DEFAULT_MAX_ATTRIBUTE_CHARS

    def __post_init__(self) -> None:
        if self.classification not in CLASSIFICATIONS:
            raise CatalogueError(f"attribute classification must be one of {CLASSIFICATIONS}")


@dataclass(frozen=True)
class Event:
    name: str
    level: str
    description: str
    cadence: str
    attrs: Mapping[str, Attr] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not EVENT_NAME.fullmatch(self.name):
            raise CatalogueError(f"event name {self.name!r} must be dotted lower-case, e.g. http.request.served")
        if self.level not in LEVELS:
            raise CatalogueError(f"event {self.name}: level must be one of {LEVELS}")
        if self.cadence not in CADENCES:
            raise CatalogueError(f"event {self.name}: cadence must be one of {CADENCES}")
        if not self.description.strip():
            raise CatalogueError(f"event {self.name} needs a description")
        for attribute in self.attrs:
            if not ATTRIBUTE_NAME.fullmatch(attribute) or attribute in CONTEXT_FIELDS:
                raise CatalogueError(f"event {self.name}: {attribute!r} is not a declarable attribute name")


def _common() -> tuple[Event, ...]:
    """Events every service has: its lifecycle, and the library's own reports."""
    return (
        Event("service.started", "info", "The process started.", "lifecycle",
              {"configuration": Attr("internal"), "pid": Attr("internal")}),
        Event("service.ready", "info", "The service is ready to serve.", "lifecycle",
              {"listen": Attr("internal")}),
        Event("service.stopping", "info", "The service is stopping.", "lifecycle", {"reason": Attr("internal")}),
        Event("service.stopped", "info", "The service stopped.", "lifecycle", {"reason": Attr("internal")}),
        Event("process.uncaught", "error", "An exception escaped every handler.", "per-failure",
              {"thread": Attr("internal")}),
        Event("library.log", "info", "A line from a third-party library, carried in the contract's shape.",
              "per-state-change", {"logger": Attr("internal"), "text": Attr("internal", 1000)}),
        Event("logging.contract.violated", "error",
              "Code emitted something the catalogue does not declare; it was dropped, not written.", "per-failure",
              {"undeclaredEvent": Attr("internal"), "undeclaredAttrs": Attr("internal")}),
        Event("events.summarized", "info", "Occurrences of a high-frequency event over a window.", "periodic",
              {"summarizedEvent": Attr("internal"), "count": Attr("internal"), "windowS": Attr("internal"),
               "key": Attr("internal")}),
    )


class Catalogue:
    """The events one service may emit: its own, plus the library's common events."""

    def __init__(self, service: str, events: Iterable[Event]) -> None:
        if not service or not service.replace("-", "").isalnum():
            raise CatalogueError("a service name is lower-case letters, digits and dashes")
        self.service = service
        self.events: dict[str, Event] = {}
        for event in (*_common(), *events):
            if event.name in self.events:
                raise CatalogueError(f"event {event.name} is declared twice")
            self.events[event.name] = event

    def __contains__(self, name: str) -> bool:
        return name in self.events

    def __getitem__(self, name: str) -> Event:
        return self.events[name]


__all__ = ["Attr", "Catalogue", "CatalogueError", "Event"]

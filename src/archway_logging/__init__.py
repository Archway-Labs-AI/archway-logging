"""Archway's logging contract (`CONTRACT.md`), kept: declared events, one JSON object per line.

    from archway_logging import Attr, Catalogue, Event, bound, setup

    CATALOGUE = Catalogue("identity", [
        Event("http.request.served", "info", "One request, answered.", "per-request",
              {"method": Attr("internal"), "route": Attr("internal"), "status": Attr("internal"),
               "ms": Attr("internal")}),
    ])
    log = setup(CATALOGUE, release=RELEASE)
    log.event("service.started")
    with bound(requestId=correlation.request_id, traceId=correlation.trace_id):
        log.event("http.request.served", method="GET", route="/health", status=200, ms=1.2)
"""
from .catalogue import Attr, Catalogue, CatalogueError, Event
from .context import bound, current
from .contract import CONTRACT_VERSION
from .emit import EventLogger, UndeclaredEvent, error_object, event, get, setup
from .redact import redact
from .summary import FailureRun, Summary

__all__ = [
    "Attr", "CONTRACT_VERSION", "Catalogue", "CatalogueError", "Event", "EventLogger", "FailureRun", "Summary",
    "UndeclaredEvent", "bound", "current", "error_object", "event", "get", "redact", "setup",
]

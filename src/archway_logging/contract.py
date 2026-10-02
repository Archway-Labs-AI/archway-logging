"""The contract's fixed vocabulary (`CONTRACT.md`, version 1)."""
from __future__ import annotations

import re

CONTRACT_VERSION = 1

#: Section 5. `error`: a person should look; `warn`: degraded but handled; `info`: lifecycle, state changes,
#: access lines; `debug`: development detail, off in production.
LEVELS = ("debug", "info", "warn", "error")
LEVEL_RANK = {level: rank for rank, level in enumerate(LEVELS)}

#: Section 3: present on every line.
REQUIRED_FIELDS = ("ts", "level", "service", "release", "event", "msg")
#: Section 3: attached automatically from the context when known; never passed as attributes.
CONTEXT_FIELDS = (
    "requestId", "traceId", "spanId", "principal", "executionId", "leaseId", "member", "workstreamId",
)
LINE_FIELDS = (*REQUIRED_FIELDS, *CONTEXT_FIELDS, "attrs", "error")

#: Section 4: an attribute's sensitivity. `public`: safe anywhere; `internal`: operational detail (a route, a
#: count, a duration); `identifier`: an opaque internal ID. Nothing else is loggable at all (section 7).
CLASSIFICATIONS = ("public", "internal", "identifier")
#: Section 8: how often an event occurs, so volume is designed rather than discovered.
CADENCES = ("per-request", "per-state-change", "per-failure", "periodic", "lifecycle")

EVENT_NAME = re.compile(r"[a-z][a-z0-9_]*(\.[a-z0-9_]+)+")
ATTRIBUTE_NAME = re.compile(r"[a-z][A-Za-z0-9_]{0,63}")

#: Section 6: an error's stack is bounded.
MAX_STACK_FRAMES = 30
MAX_STACK_CHARS = 8192
MAX_MESSAGE_CHARS = 1000
DEFAULT_MAX_ATTRIBUTE_CHARS = 256

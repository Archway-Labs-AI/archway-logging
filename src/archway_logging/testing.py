"""Conformance (section 4): check a service's output against the contract and its catalogue."""
from __future__ import annotations

import io
import json
import re
from contextlib import contextmanager
from typing import Iterator

from .catalogue import Catalogue
from .contract import CONTEXT_FIELDS, LEVELS, LINE_FIELDS, REQUIRED_FIELDS
from .emit import EventLogger, setup

_ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")
_SECRET_SHAPES = (re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\."), re.compile(r"(?i)bearer\s+\S{8,}"),
                  re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"), re.compile(r"(?i)[?&](code|state|token)=[^&\s\[]"))


class Captured:
    def __init__(self, stream: io.StringIO, logger: EventLogger) -> None:
        self.stream, self.logger = stream, logger

    @property
    def lines(self) -> list[dict]:
        return [json.loads(text) for text in self.stream.getvalue().splitlines() if text]


@contextmanager
def capture(catalogue: Catalogue, *, release: str = "test", level: str = "debug") -> Iterator[Captured]:
    """Set the process up in strict mode, writing to a buffer, for a test."""
    stream = io.StringIO()
    yield Captured(stream, setup(catalogue, release=release, stream=stream, level=level, strict=True))


def violations(text: str, catalogue: Catalogue) -> list[str]:
    """Every way `text` (a service's output) breaks the contract; empty when it conforms."""
    problems: list[str] = []
    for number, raw in enumerate(text.splitlines(), 1):
        try:
            line = json.loads(raw)
        except ValueError:
            problems.append(f"line {number}: not one JSON object")
            continue
        if not isinstance(line, dict):
            problems.append(f"line {number}: not an object")
            continue
        missing = [field for field in REQUIRED_FIELDS if not line.get(field)]
        extra = sorted(set(line) - set(LINE_FIELDS))
        if missing or extra:
            problems.append(f"line {number}: missing {missing} / unknown fields {extra}")
        if line.get("level") not in LEVELS or not _ISO.fullmatch(str(line.get("ts", ""))):
            problems.append(f"line {number}: bad level or timestamp")
        if line.get("service") != catalogue.service:
            problems.append(f"line {number}: service {line.get('service')!r} is not {catalogue.service!r}")
        spec = catalogue.events.get(line.get("event", ""))
        if spec is None:
            problems.append(f"line {number}: undeclared event {line.get('event')!r}")
        elif set(line.get("attrs") or {}) - set(spec.attrs):
            problems.append(f"line {number}: undeclared attributes {sorted(set(line['attrs']) - set(spec.attrs))}")
        for field in CONTEXT_FIELDS:
            if field in line and not isinstance(line[field], str):
                problems.append(f"line {number}: context field {field} is not a string")
        if any(pattern.search(raw) for pattern in _SECRET_SHAPES):
            problems.append(f"line {number}: carries a secret-shaped value")
    return problems


__all__ = ["Captured", "capture", "violations"]

"""The library keeps the contract (`CONTRACT.md`, version 1)."""
from __future__ import annotations

import io
import json
import logging
import threading
from pathlib import Path

import pytest

from archway_logging import Attr, Catalogue, CatalogueError, Event, FailureRun, Summary, UndeclaredEvent, bound
from archway_logging.emit import setup
from archway_logging.testing import capture, violations

CATALOGUE = Catalogue("plane-writer", [
    Event("http.request.served", "info", "One request, answered.", "per-request",
          {"method": Attr("internal"), "route": Attr("internal"), "status": Attr("internal"), "ms": Attr("internal")}),
    Event("request.failed.unhandled", "error", "A request failed through our fault.", "per-failure",
          {"route": Attr("internal")}),
    Event("identity.unavailable", "warn", "Identity did not answer; retrying.", "per-failure",
          {"attempt": Attr("internal")}),
    Event("identity.recovered", "info", "Identity answers again.", "per-state-change",
          {"failures": Attr("internal")}),
])


def test_one_event_is_one_json_line_with_the_contract_s_fields() -> None:
    with capture(CATALOGUE, release="r1") as out:
        out.logger.event("http.request.served", method="GET", route="/health", status=200, ms=1.5)
    (line,) = out.lines
    assert set(line) == {"ts", "level", "service", "release", "event", "msg", "attrs"}
    assert (line["service"], line["release"], line["event"], line["level"]) == (
        "plane-writer", "r1", "http.request.served", "info")
    assert line["msg"] == "One request, answered." and line["attrs"]["status"] == 200
    assert violations(out.stream.getvalue(), CATALOGUE) == []


def test_bound_identifiers_ride_on_every_line_and_nest() -> None:
    with capture(CATALOGUE) as out:
        with bound(requestId="req_0123456789abcdef", traceId="t" * 32):
            with bound(executionId="exec_1"):
                out.logger.event("http.request.served", status=200)
            out.logger.event("http.request.served", status=201)
        out.logger.event("http.request.served", status=202)
    first, second, third = out.lines
    assert first["requestId"] == "req_0123456789abcdef" and first["executionId"] == "exec_1"
    assert "executionId" not in second and second["traceId"] == "t" * 32
    assert "requestId" not in third
    with pytest.raises(ValueError):
        with bound(email="ben@example.com"):
            pass


def test_nothing_undeclared_is_written() -> None:
    with capture(CATALOGUE) as out:
        with pytest.raises(UndeclaredEvent):
            out.logger.event("made.up.event")
        with pytest.raises(UndeclaredEvent):
            out.logger.event("http.request.served", body="{\"secret\": 1}")
    assert out.lines == []
    stream = io.StringIO()
    lenient = setup(CATALOGUE, release="r", stream=stream)          # production: dropped, and said so
    lenient.event("http.request.served", status=200, body="{\"secret\": 1}")
    lenient.event("made.up.event")
    lines = [json.loads(text) for text in stream.getvalue().splitlines()]
    assert [line["event"] for line in lines] == [
        "logging.contract.violated", "http.request.served", "logging.contract.violated"]
    assert "body" not in lines[1].get("attrs", {}) and "secret" not in stream.getvalue()
    assert lines[2]["attrs"]["undeclaredEvent"] == "made.up.event"


def test_an_error_is_one_bounded_object_with_secrets_redacted() -> None:
    def deep(n: int) -> None:
        if n == 0:
            raise RuntimeError("upstream said: Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123 and ?code=XYZ123")
        deep(n - 1)

    with capture(CATALOGUE) as out:
        try:
            deep(80)
        except RuntimeError as exc:
            out.logger.event("request.failed.unhandled", error=exc, route="/x")
    (line,) = out.lines
    assert line["level"] == "error" and line["error"]["type"] == "RuntimeError"
    assert "abcdefghijklmnop" not in json.dumps(line) and "XYZ123" not in json.dumps(line)
    assert line["error"]["stack"].count("\n") < 80 and len(line["error"]["stack"]) <= 8192
    assert "\n" not in out.stream.getvalue().rstrip("\n"), "the stack is inside the one line"


def test_third_party_logging_and_uncaught_exceptions_keep_the_shape() -> None:
    with capture(CATALOGUE) as out:
        logging.getLogger("uvicorn.error").warning("worker restarted with token=abc123def456")
        thread = threading.Thread(target=lambda: 1 / 0, name="worker-7")
        thread.start()
        thread.join()
    library, uncaught = out.lines
    assert library["event"] == "library.log" and library["level"] == "warn"
    assert library["attrs"]["logger"] == "uvicorn.error" and "abc123def456" not in library["attrs"]["text"]
    assert uncaught["event"] == "process.uncaught" and uncaught["error"]["type"] == "ZeroDivisionError"
    assert uncaught["attrs"]["thread"] == "worker-7"
    assert violations(out.stream.getvalue(), CATALOGUE) == []


def test_quiet_loggers_say_nothing() -> None:
    stream = io.StringIO()
    setup(CATALOGUE, release="r", stream=stream, quiet=("uvicorn.access",))
    logging.getLogger("uvicorn.access").info('127.0.0.1 - "GET /auth/callback?code=SECRET HTTP/1.1" 200')
    assert stream.getvalue() == ""


def test_high_frequency_successes_are_summarized_and_failures_are_not_repeated() -> None:
    now = [0.0]
    with capture(CATALOGUE) as out:
        polls = Summary(out.logger, "node.poll.served", every_s=300, key="35d92506", clock=lambda: now[0])
        for _ in range(29):
            now[0] += 10
            polls.count()
        now[0] += 10
        polls.count()                                   # the 300 s window ends: one line for 30 polls
        run = FailureRun(out.logger, failed="identity.unavailable", recovered="identity.recovered")
        for attempt in range(5):
            run.failed(attempt=attempt)
        run.succeeded()
    summary, failed, recovered = out.lines
    assert summary["event"] == "events.summarized" and summary["attrs"]["count"] == 30
    assert failed["event"] == "identity.unavailable" and failed["attrs"]["attempt"] == 0
    assert recovered["event"] == "identity.recovered" and recovered["attrs"]["failures"] == 5


def test_a_catalogue_that_breaks_the_contract_is_refused() -> None:
    for bad in (lambda: Event("NoDots", "info", "x", "per-request"),
                lambda: Event("a.b", "fatal", "x", "per-request"),
                lambda: Event("a.b", "info", "", "per-request"),
                lambda: Event("a.b", "info", "x", "sometimes"),
                lambda: Event("a.b", "info", "x", "per-request", {"requestId": Attr("identifier")}),
                lambda: Attr("secret")):
        with pytest.raises(CatalogueError):
            bad()


def test_the_conformance_check_finds_what_a_hand_written_line_gets_wrong() -> None:
    text = "\n".join([
        "access {\"path\": \"/x\"}",
        json.dumps({"ts": "2026-10-01T00:00:00.000Z", "level": "fatal", "service": "plane-writer",
                    "release": "r", "event": "made.up", "msg": "x"}),
        json.dumps({"ts": "2026-10-01T00:00:00.000Z", "level": "info", "service": "plane-writer",
                    "release": "r", "event": "http.request.served", "msg": "GET /approve/callback?code=abc"}),
    ])
    problems = violations(text, CATALOGUE)
    assert any("not one JSON object" in p for p in problems)
    assert any("bad level" in p for p in problems) and any("undeclared event" in p for p in problems)
    assert any("secret-shaped" in p for p in problems)


def test_the_schema_requires_what_the_library_writes() -> None:
    schema = json.loads((Path(__file__).resolve().parents[1] / "schema/log-line.v1.json").read_text())
    from archway_logging.contract import CONTEXT_FIELDS, REQUIRED_FIELDS
    assert schema["required"] == list(REQUIRED_FIELDS)
    assert set(schema["properties"]) == {*REQUIRED_FIELDS, *CONTEXT_FIELDS, "attrs", "error"}

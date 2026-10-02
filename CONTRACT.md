# The Archway logging contract

Version 1. Ratified by Ben, 2026-10-01: the contract lives here, in its own repository, with one library every
service uses to keep it (D1); field names follow OpenTelemetry's log data model (D2); every event is declared in
its service's catalogue and tests enforce it (D3); high-frequency successes are summarized, not logged one by one
(D4).

Changing a field, a level's meaning or a content rule is a contract change: it needs Ben's review and a new
version. The machine-readable form of section 3 is `schema/log-line.v1.json`.

## Why

Ben, 2026-10-01: enterprise services struggle "due to a complete lack of disciplined and consistent design to
their logging"; the logging contract is the most important part of observability.

What we have today (inventory, 2026-10-01, across the six service processes):

- **Five incompatible line formats** (`access {json}` without a timestamp; `<ts> INFO {json}`; `<ts> node LEVEL
  text`; `LEVEL text`; Rich columns plus uvicorn's format in the MCP), plus bare text from loggers nobody
  configured. No shared setup anywhere.
- **Errors swallowed:** the engine service logs nothing at all, including internal errors; identity drops 500s;
  the router's identity retries are silent; the node reports activation, removal and fence events only to the
  plane.
- **Errors split:** multi-line tracebacks arrive as one journald entry per line, without the request they belong to.
- **Secrets in logs:** OAuth codes in the plane's access path (fixed, #74) and in the MCP's uvicorn access log;
  the node echoes up to 500 characters of the plane's error bodies.
- **Uneven correlation:** request IDs only in the plane and identity access lines; none in the router, engine or
  MCP, nor on the plane's own error and lock lines.
- **Noise:** an access line per node long poll (every 10 s), a `poll failed` line about every second during an
  outage, a startup banner printing business text (bet titles) and paths.


### 1. What logs are for, and what they are not

A log line records **what one service process did or observed while running**, for operating it: what failed,
what was slow, what changed state. Logs are **never the system of record**. Execution evidence (runs, operations,
provider invocations, assessments) belongs to the harness telemetry contracts (`TELEMETRY-ARCHITECTURE.md`);
business facts belong to their services' databases. A log may *point at* durable evidence by ID; it never
substitutes for it, and losing a log never loses a fact.

### 2. One line, one event, one JSON object

Every line a service writes to stdout is a single JSON object describing exactly one event. No prefixes, no
multi-line output, no free text outside the object. stderr is reserved for the process failing to start (before
logging is set up) and for the runtime's own last-resort output, which the library also routes to JSON.

### 3. The fields

Aligned with the OpenTelemetry Log Data Model, so export to CloudWatch, Datadog or any OTel backend is a mapping,
not a rewrite.

| Field | Required | Meaning |
| --- | --- | --- |
| `ts` | yes | RFC 3339 UTC with milliseconds, set by the library |
| `level` | yes | `debug` / `info` / `warn` / `error` (section 5) |
| `service` | yes | `plane-writer`, `plane-front-door`, `identity`, `engine-router`, `engine`, `mcp`, `execution-node` |
| `release` | yes | the running release ID |
| `event` | yes | a stable dotted name from the service's event catalogue (section 4) |
| `msg` | yes | one human sentence, no variable secrets |
| `requestId`, `traceId`, `spanId` | when serving a request | from request correlation, attached automatically |
| `executionId`, `leaseId`, `member`, `workstreamId` | when doing execution work | attached automatically by the runtime's context |
| `principal` | when known | the internal principal ID (never an email, name or token) |
| `attrs` | per event | the event's declared attributes, and nothing else |
| `error` | on failures | `{type, message, stack}`: one object, stack bounded (section 6) |

### 4. Every event is declared

Each service keeps an **event catalogue** in code: for every event name, its level, a one-line description, and
its allowed attributes with each attribute's classification (`public`, `internal`, `identifier`). Code emits
events only by catalogue name; an undeclared event or attribute fails the service's tests. Queries, metrics and
alarms key on event names, never on message text, so a message can be reworded without breaking an alarm.

Naming: `<area>.<thing>.<what-happened>` in past tense or state: `http.request.served`, `lock.hold.slow`,
`node.credential.issued`, `service.started`, `service.stopping`, `identity.unavailable`,
`request.failed.unhandled`.

### 5. Levels mean something

- `error`: a person should look. An invariant was broken, a request failed through our fault, or work was lost.
  Every `error` is something an alarm may page on.
- `warn`: degraded but handled: a retry, a fallback, a slow operation, a dependency briefly unavailable.
- `info`: lifecycle (start, ready, stopping), state changes, and one access line per request.
- `debug`: development detail; off in production.

A failed request caused by the caller (4xx) is `info` on its access line, not `error`.

### 6. Errors

An exception is reported once, where it is handled, as one event carrying `error.type`, `error.message` (bounded,
with secrets redacted by the library) and `error.stack` (the frames as one string, at most ~30 frames or 8 KB),
plus the request and execution context. Swallowing an error without an event is a contract violation, and so is
logging the same exception at every layer it passes through.

### 7. What never goes in a log

Tokens, credentials, secrets, cookies, authorization headers; query strings; request and response bodies;
prompts, provider output, source code, file contents, collection values; email addresses and names; raw error
bodies from another service. Identifiers (`principal`, `requestId`, record IDs) are allowed. The library enforces
this structurally: only declared attributes are written, values are length-bounded, and known secret shapes are
redacted as a backstop. The raw-content rules of telemetry policy R1 and `hosted-raw-v1` apply unchanged: nothing
raw goes to a log.

### 8. Volume

A log line costs money and attention once it is shipped. High-frequency successes are summarized, not logged one
by one: a node's successful long polls are counted and reported every few minutes, not logged per poll; a
dependency failing every second logs its first failure, then a summary of repeats, then recovery. Every event in
the catalogue declares whether it is per-request, per-state-change or periodic.

### 9. Lifecycle

Every service emits `service.started` (release, configuration identity, not values), `service.ready`,
`service.stopping` and, where it can, `service.stopped` with the reason. Configuration is described by names and
hashes, never values, and never business content.

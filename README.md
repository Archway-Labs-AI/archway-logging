# archway-logging

Archway's logging contract and the library every Archway service uses to keep it.

- `CONTRACT.md` is the contract: one JSON event per line, declared event catalogues, request and
  execution context, levels with meaning, errors once, nothing secret.
- `src/archway_logging/` is the library: `setup`, catalogues, events, context, redaction, summaries.
- `archway_logging.testing` checks a service's output against its catalogue.

Logs are for operating services. They are never a system of record: execution evidence belongs to the
harness's telemetry contracts and business facts to their services' databases.

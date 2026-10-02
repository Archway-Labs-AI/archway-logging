# AGENTS.md — archway-logging

The contract (`CONTRACT.md`) is the source of truth; the library implements it and nothing else.
Changing a field, a level's meaning or a content rule is a contract change: it needs Ben's review and a
contract version bump. Tests: `hatch run test`. Commit identity: `Archway Labs <ben@archway-labs.com>`.

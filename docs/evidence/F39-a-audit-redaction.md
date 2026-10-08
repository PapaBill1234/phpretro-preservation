# F39a audit redaction evidence

Source fixture: `docs/evidence/F35-audit-transaction.md`.

F35 records that the concrete audit schema and actor fields are UNKNOWN and
that the owner/security/schema gate remains open. This unit therefore uses a
synthetic allow-list of actor ID, actor role, action, target and target ID.
Values containing secrets or control characters are rejected by `RedactRecord`
before it returns an audit record. No production schema, credential, row or
database is used.

`RedactRecord` is a standalone policy helper in this unit. It does not alter
F35 dispatch or transaction behavior; dispatch integration and the atomic
fail-closed guarantee for redaction failures remain blocked on the open
owner/security/schema gate.

fidelity: guessed
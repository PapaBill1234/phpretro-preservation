# F39a audit redaction evidence

Source fixture: `docs/evidence/F35-audit-transaction.md`.

F35 records that the concrete audit schema and actor fields are UNKNOWN and
that the owner/security/schema gate remains open. This unit therefore uses a
synthetic allow-list of actor ID, actor role, action, target and target ID.
Values containing secrets or control characters are rejected by `RedactRecord`
before it returns an audit record. No production schema, credential, row or
database is used.

Coordinator repair decision (2026-10-08): integrate this bounded synthetic
policy in Dispatch and both injected stores. Redaction runs before any store
call or transaction. Identifiers are restricted to 1-64 ASCII letters, digits,
underscore, dot, colon and hyphen; control characters and credential-like
labels (secret, token, password, sk-, bearer) are rejected. Mutation values are
never included in audit records. An UPDATE affecting anything except exactly
one row rolls back without committing an audit record. This is a new
website-owned development policy, not a claim about captured legacy behavior.

`internal/audit/redact_integration_test.go` exercises the actual Dispatch and
direct store entry points: rejected audit values never call an external
store, never begin a SQL transaction and never commit either record. The
zero-row UPDATE regression checks that an absent mutation cannot commit an
audit. Existing injected audit/write failure tests still require rollback.
The approved repair scope includes audit.go, audit_test.go and the integration
test in addition to the original F39a helper, tests and delivery/evidence docs.
No production schema, credentials or activation are authorized by this repair.

fidelity: guessed

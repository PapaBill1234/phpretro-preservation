# F35 atomic website-owned mutation with audit — evidence

Source: `docs/roadmap/F31-F45-candidate-design.md`, F35 candidate row (line 53).
The row requires a website-owned mutation and its audit record to commit
atomically, with negative cases for unauthorized, invalid, SQL failure, audit
failure, partial commit and replay, using prepared SQL and a synthetic store
with no production enablement. It also states the coordinator chooses the
mutation, schema, actor fields and transaction boundary, and that an
independent security review is required.

Gate status (from the row and `docs/units/F35.md`): owner/security/schema gate
is **open**. The concrete mutation, audit schema, actor fields and audit
retention are UNKNOWN. No production database, credential, real row, migration
or runner change is used. This unit therefore records synthetic evidence only.

What the synthetic evidence establishes:

- `Selection` must be complete before dispatch: mutation, schema, actor fields,
  transaction boundary and required role are recorded by `Prepare`, and an
  incomplete selection is rejected with `ErrSelectionUnset`
  (`internal/audit/audit_test.go`, `TestPrepareRejectsIncompleteSelection`).
- The recorded selection is available for evidence before any store call
  (`TestPlanRecordsSelectionBeforeDispatch`, `TestCanonicalRecordIsStable`).
- An authorized valid mutation and its audit record commit together
  (`TestAuthorizedMutationCommitsAtomically`).
- Unauthorized (wrong role, missing actor) and invalid (empty target/ID/value,
  control characters) input cause no write and no audit row, because denial
  returns before the store is touched
  (`TestUnauthorizedOrInvalidCausesNoWriteNoAudit`).
- An injected audit failure rolls the mutation back with no partial commit, and
  an injected write failure symmetrically rolls back the audit
  (`TestInjectedAuditFailureRollsBackMutation`, `TestWriteFailureRollsBackAudit`).
- The SQL store uses one transaction, prepared statements, and bound arguments
  with no interpolated values
  (`TestSQLStoreUsesPreparedBoundTransaction`); an audit insert failure rolls
  back the transaction with nothing committed
  (`TestSQLStoreAuditFailureRollsBack`).

Limits: replay protection, rate limiting, redaction policy, real audit
retention, HTTP/session binding and the production schema are **not**
established here and remain behind the open gate.

External (black-box) coverage lives in `tests/audit/audit_external_test.go`.

# QA3 audit findings

## Dispositions

- No QA3 finding text was supplied or present at the authorized input path when RF2b ran; therefore there are no findings that can be responsibly marked fixed or ruled out. This is an input gap, not a claim that all findings were resolved.
- No behavior changes were made. The required checks passed, but cannot establish finding-by-finding resolution without the findings and their evidence.
- Required follow-up: provide the QA3 findings and evidence so each can receive a disposition citing the resolving file and line.

## 2026-10-08 coordinator repair disposition

The missing-input note above is historical. Codex inspected the actual tests.
Positive validation, identity and timing cases now use fixed RFC 4226/6238
vectors recorded in docs/evidence/QA3-totp-vectors.md, not SyntheticCode output.
Alice/Bob have distinct fixtures; both adjacent steps explicitly return
ErrExpiredCode and the outside step returns ErrWrongCode. Nil stores now
return ErrStore rather than panic. No session binding or escalation claim is
made. The circular-expectation findings are resolved at this boundary.
Run: go test ./internal/staff/... ./tests/staff/... and scripts/check.sh.
fidelity: guessed (zero-skew policy and synthetic identities).

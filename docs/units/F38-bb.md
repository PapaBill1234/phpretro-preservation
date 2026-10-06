# F38-bb — TOTP step staff scoping

fidelity: guessed

What works: synthetic accepted steps are keyed by staff identity and step, so accepting a step for one identity does not consume it for another. Duplicate acceptance remains rejected for the same identity. Existing guessed window and expiry behavior are unchanged.

What is guessed: ±1-step skew, the 30-second interval, and strict expiry boundary. The design fixture leaves these decisions behind an owner/security/schema gate. The in-memory map is not durable replay protection and is not production-ready; no real secrets or credentials are used.

Security: independent security review is required. Durable, atomic replay persistence remains unresolved and outside this unit's guarantee.

How to run: `go test ./internal/staff/...`; merge gate: `bash scripts/check.sh`.

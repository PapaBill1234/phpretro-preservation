# Rewrite readiness

This checklist is the entry gate for implementation.

- [x] Repository identity, owner, visibility, default branch, integration branch, and protected-main policy are recorded.
- [x] The recovered fresh-start plan is reviewed with the Jev/cost revision in section 1.
- [x] `DECISIONS.md` records the foundation and per-unit token caps, A6API monitoring policy, dependency pins, asset provenance rules, and unresolved decisions.
- [x] CI runs Go formatting/build/tests, `go test -race`, pinned `govulncheck ./...`, and direct/transitive license inventory; the first run passed on GitHub.
- [x] A dependency-free Go F0 module, pinned toolchain file, and executable baseline test exist.
- [x] Original PHPRetro source, disposable fixture, immutable image digest, and golden-capture hash process are pinned.
- [x] Sol has written the initial F0-F5 bounded batch with exact paths, tests, stop conditions, and caps.
- [x] Jev availability and the enabled `jev_gate` PreToolUse safety hook are documented from observed configuration; the hook does not replace ordinary Codex permissions or Jev cost measurement.
- [x] A6API raw JSONL export, backup policy, rates, and summary command are available; no secrets are committed.
- [x] Production registration, payments, emulator writes, client handoff, staff operations, Pixel63, Atom, Redis/nginx/metrics/fuzzing, and SWF work remain gated.

The user has authorized completion of the setup and the F0-F5 scope is recorded. Readiness now advances through the supervised foundation evidence: F0 CI is accepted; F1-F5 remain sequential implementation gates.

The clean Stage 3 rerun and immutable image digest are recorded in `docs/golden-capture-evidence.md`. A live balance check is not an entry condition; A6API monitoring remains active and work stops on an actual provider payment, quota, or authentication failure.

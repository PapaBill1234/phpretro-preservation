# Rewrite readiness

This checklist is the entry gate for implementation.

- [ ] Repository identity, owner, visibility, default branch, integration branch, and protected-main policy are recorded.
- [ ] The recovered fresh-start plan is reviewed with the Jev/cost revision in section 1.
- [ ] `DECISIONS.md` records the foundation and per-unit token caps, A6API balance floor, dependency pins, asset provenance rules, and unresolved decisions.
- [ ] CI runs Go formatting/build/tests, `go test -race`, `govulncheck ./...`, and direct/transitive license inventory.
- [x] A dependency-free Go F0 module, pinned toolchain file, and executable baseline test exist; CI execution remains pending because Go is not installed in the current Windows shell.
- [ ] Original PHPRetro source, disposable fixture, immutable image digest, and golden-capture hash process are pinned.
- [ ] Sol has written one approved batch of 5-10 bounded work units with exact paths, tests, stop conditions, and caps.
- [ ] Jev availability is checked only when the MCP tool is exposed; `jev_gate` and hooks are documented by observed configuration, not assumed from prose.
- [ ] A6API raw JSONL export, backup policy, rates, and summary command are available; no secrets are committed.
- [ ] Production registration, payments, emulator writes, client handoff, staff operations, Pixel63, Atom, Redis/nginx/metrics/fuzzing, and SWF work remain gated.

Readiness is incomplete until the user approves the batch scope and the supervised foundation unit produces measured evidence.

---
name: phpretro-go-contracts
description: Implement source-backed PHP-Retro Go contracts.
version: 0.1.0
author: Karim, Hermes Agent
license: GPL-3.0-only
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [phpretro, backend, go, adapters]
---

# PHP-Retro Go contracts

Implement an approved Go slice against source-backed ownership and behavior. Use `phpretro-worker-handoff` for card intake, file scope, commit, and lifecycle reporting. This skill covers the Go-specific decisions and checks.

## When to use

- A `backend` card changes `internal/account`, `session`, `profile`, `content`, `polaris`, `cache`, `localization`, or `tests/golden`.
- A Go regression or adapter test must prove a bounded contract from existing source and evidence.

## Do not use for

- Inferring PolarIS columns, production rows, migrations, credentials, live Redis topology, or new route/security behavior.
- Coordinator-owned schema, security, production, or runner decisions; frontend/visual implementation.

## Procedure

1. Read `go.mod`, `.go-version`, the assigned package, its tests, and cited `docs/evidence/**` with `read_file`/`search_files`. For legacy behavior, inspect the pinned original source or disposable golden evidence identified by the card. Check: each proposed field, enum, query, and failure contract has a source citation or remains `UNKNOWN`; a planning draft alone is insufficient.
2. Preserve package boundaries: services consume narrow `Store`/`RedisLike` interfaces; `internal/polaris` receives injected `*sql.DB`, uses explicit columns and bound arguments, and stays read-only unless a separate coordinator decision authorizes writes. The cache is support state, not authoritative identity/session/audit state. Check: dependency direction and ownership match current code and evidence, with no new external connection or secret.
3. Add a focused synthetic test that observes the assigned contract and its relevant negative case: missing row, malformed enum/locale, cache expiry/outage, bound SQL arguments, or golden mismatch. Check: the test fails for the defect or contract gap before the fix when feasible, and the fixture contains no production row or credential.
4. Make the smallest implementation change inside card scope. For database work, verify exact query text, explicit column list, parameter values, error mapping, and absence of writes against the fixture. For cache/localization, verify deterministic fallback, locale-separated keys, and outage behavior. Check: no behavior depends on guessed schema or a real service.
5. With Go 1.25.13 from `.go-version` or the card-approved pinned runner, use the focused command for the changed package (for example `terminal(command="go test ./internal/polaris/...")` for the adapter), then `terminal(command="go test ./...")`, `terminal(command="go test -race ./...")` where concurrency is relevant, `terminal(command="go vet ./...")`, and `terminal(command="git diff --check")`. Check: exact commands, toolchain, exits, and failing package names are in the handoff; run CI's module/license/vulnerability gates when dependencies change. If the pinned toolchain is unavailable, mark the check unverified rather than pass.

## Pitfalls

- `go.mod` has an older toolchain directive while `.go-version` pins the CI toolchain; verify the effective toolchain before reporting results.
- A synthetic fixture proves contract mapping, not deployed PolarIS row characteristics.
- `tests/golden` compares measured responses; do not normalize away an unexplained status, redirect, cookie, or body difference.
- Adding a new dependency requires the recorded decision and license/security evidence in `DECISIONS.md`.

## Verification

Use `terminal(command="gofmt -l <changed-go-files>")` with actual file paths and inspect any output before handoff. Re-read the exact diff and tests. Report focused/full/race/vet outcomes separately, with `UNKNOWN` values preserved in evidence.

# Changelog

## Unreleased

### Project operations

- Migrated repository guidance to the durable Hermes Kanban board `phpretro-preservation`.
- Documented the five-profile operating model: `coordinator` and `reviewer` on Sol (`gpt-6.1-sol`), plus `backend`, `frontend`, and `visual` on Luna (`gpt-6-luna`), all through A6API.
- Documented Hermes Nerve supervision, Jev's evidence-backed and ROI-gated role, isolated worktrees, reviewer separation, and the continuation invariant for coordinator cards.
- Updated the run state, queue, decisions, README, and agent-operation guidance to reflect the current F0-F8 direction.

### F8 localization boundary

- Added synthetic Go and TypeScript localization contracts.
- Added supported locale and catalog-version validation.
- Added deterministic exact-locale, language-locale, and default fallback behavior.
- Added explicit missing-key results and typed localized React view models.
- Added locale-varying cache keys that reject unsupported locales and cannot collide with non-locale keys.
- Added synthetic frontend, backend, cache, and evidence coverage.

### Verification

- Coordinator integration reported passing Go formatting, `go test ./...`, `go test -race ./...`, `go vet ./...`, frontend typecheck, seven frontend tests, and `git diff --check`.
- The repository host does not have Go installed; Go verification uses Docker where available.
- Production data, credentials, CMS writes, Redis deployment, and production enablement remain out of scope.

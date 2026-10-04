# Changelog

## Unreleased

### Project operations

- Migrated repository guidance to the durable Hermes Kanban board `phpretro-preservation`.
- Documented the five-profile operating model: `coordinator` and `reviewer` on Sol (`gpt-6.1-sol`), plus `backend`, `frontend`, and `visual` on Luna (`gpt-6-luna`), all through A6API.
- Recorded the owner's 2026-10-04 standing instruction: development-only project status with authentication, sessions, cookies, CSRF, audit design, schema and migrations open for development use; scope approval delegated to `approver`; Option A content-digest-bound approval for prose-only candidates; F18-F30 eligible in dependency order; a fixed problem-escalation order; three standing limits; evidence and fidelity rules; a 3,000,000-token per-unit cap; and queue-file reporting instead of owner messages.
- Added a sixth live profile, `approver` (`gpt-6.1-sol` through A6API), to decide the bounded development-scope and routine technical gates the owner delegated, recording one evidence-backed APPROVE, REJECT, or NEEDS_EVIDENCE verdict on the board and the relevant PR. Merge, schema, authentication/session, security, production, runner, credential, real-data, and irreversible-change authority remain coordinator-owned and owner-gated, and the approver never authors, reviews, or merges a change it approves.
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

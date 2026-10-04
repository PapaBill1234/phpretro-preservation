# Changelog

## Unreleased

### Project operations

- Migrated repository guidance to the durable Hermes Kanban board `phpretro-preservation`.
- Documented the five-profile operating model: `coordinator` and `reviewer` on Sol (`gpt-6.1-sol`), plus `backend`, `frontend`, and `visual` on Luna (`gpt-6-luna`), all through A6API.
- Recorded the owner's 2026-10-04 standing instruction: development-only project status with authentication, sessions, cookies, CSRF, audit design, schema and migrations open for development use; scope approval delegated to `approver`; Option A content-digest-bound approval for prose-only candidates; F18-F30 eligible in dependency order; a fixed problem-escalation order; three standing limits; evidence and fidelity rules; a 3,000,000-token per-unit cap; and queue-file reporting instead of owner messages.
- Added a sixth live profile, `approver` (`gpt-6.1-sol` through A6API), to decide the bounded development-scope and routine technical gates the owner delegated, recording one evidence-backed APPROVE, REJECT, or NEEDS_EVIDENCE verdict on the board and the relevant PR. Coordinator technical ownership of schema, authentication/session, security, runner and merge decisions is retained, not an owner gate on the now-open development scope. There is no production environment and no production gate. Real credentials/key material, real user data and live outside systems remain closed. The approver never authors, reviews, or merges a change it approves; its verdict grants no merge or runner/ruleset authority.
- Documented Hermes Nerve supervision, Jev's evidence-backed and ROI-gated role, isolated worktrees, reviewer separation, and the continuation invariant for coordinator cards.
- Moved routine model traffic to `deepseek-v4.1-flash` (coordinator, backend, frontend, visual, watchdog, digests, CI and diff checks, brief-writing, F31-F60 design synthesis, first-pass review) and reserved `gpt-6.1-sol` for escalated review, a single escalation after two failures on the cheaper model, and design synthesis for unclear units; a reviewer must never share the model family of the candidate's author. Shortened the card chain so a routine unit is one worker card with the first-pass review inside it, CI auto-merge on green, and a worker-created successor; the approver is used only for scope changes.
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
- Historical F8 verification did not cover CMS writes or Redis deployment; separately bounded development units remain subject to their own gates. Real credentials/key material, real user data and live outside systems remain out of scope.

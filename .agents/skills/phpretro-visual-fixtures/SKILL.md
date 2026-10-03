---
name: phpretro-visual-fixtures
description: Verify PHP-Retro presentation fixtures and limits.
version: 0.1.0
author: Karim, Hermes Agent
license: GPL-3.0-only
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [phpretro, visual, fixtures, presentation]
---

# PHP-Retro visual fixtures

Keep assigned presentation work grounded in the current React shell, theme manifest, and synthetic fixtures. Use `phpretro-worker-handoff` for card intake, scope, commit, and lifecycle reporting.

## When to use

- A `visual` card explicitly owns presentation fixtures, theme rendering checks, or visual evidence.
- A theme-capability or locale-display change needs presentation-only regression coverage.

## Do not use for

- Backend contracts, API data shape, authorization, route/security/schema behavior, or a speculative redesign.
- Screenshot or visual-regression claims when no runner or comparison fixture is configured in the card/repository.

## Procedure

1. Read the assigned card, `frontend/src/StarterShell.tsx`, `themeManifest.ts`, `viewModel.ts`, existing `frontend/tests/**`, and relevant `docs/evidence/**`. Check: identify the current presentation convention, exact visual-owned paths, synthetic fixture inputs, and the expected output before changing anything.
2. Separate display variation from functional contract behavior. Keep theme capabilities restricted to the existing manifest and consume only validated view-model fields. Check: the proposed change cannot alter routing, identity, permissions, CSRF, audit, cache authority, or backend schema.
3. Add or update the smallest synthetic presentation/fixture test authorized by the card. Include a negative capability-boundary assertion when the manifest or locale display is involved. Check: the test demonstrates a user-visible presentation requirement or forbidden capability, not a duplicate of implementation syntax.
4. If rendered UI is in scope and an approved preview is available, inspect relevant viewport sizes and keyboard/accessible names; record the viewport, method, and concrete observations. If no render/screenshot harness exists, record that limit without claiming visual regression coverage. Check: evidence says exactly what was inspected and what remains unverified.
5. From `frontend`, run `terminal(command="npm ci --include=dev --ignore-scripts")`, `terminal(command="npm run typecheck")`, `terminal(command="npm test")`, and `terminal(command="npm run build")`; use `terminal(command="git diff --check")` at the repo root. Check: outputs and counts match the exact candidate; changed paths stay within the visual card and do not overlap an active functional frontend card.

## Pitfalls

- The repository currently has a starter shell and contract tests, not a configured screenshot baseline. Do not create an image-heavy workflow unless a card establishes fixtures, runner, and acceptance method.
- An evidence document must cite the actual candidate and command output; green tests do not justify stale counts or a source file outside visual scope.

## Verification

Read back the exact changed-file list, test output, and any rendered inspection evidence. State separately whether type/contract tests passed and whether a visual preview was actually inspected.

---
name: phpretro-react-boundary
description: Build typed PHP-Retro React and locale contracts.
version: 0.1.0
author: Karim, Hermes Agent
license: GPL-3.0-only
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [phpretro, frontend, react, localization]
---

# PHP-Retro React boundary

Implement an approved functional React/TypeScript slice while preserving the typed API and localization boundary. Use `phpretro-worker-handoff` for card intake, scope, commit, and lifecycle reporting.

## When to use

- A `frontend` card changes `frontend/src/viewModel.ts`, `themeManifest.ts`, `localization/**`, functional components, or related contract tests.
- A localization regression must verify catalog shape, fallback, missing-key behavior, or locale-specific view-model output.

## Do not use for

- Visual redesign, unassigned assets/fixtures, backend routing, authorization, session, CSRF, audit, or schema changes.
- Claiming browser/screenshot/lint coverage from this repository's current scripts; those harnesses are not configured here.

## Procedure

1. Read `frontend/package.json`, `tsconfig.json`, relevant `frontend/src/**`, `frontend/tests/**`, and the card's source/evidence references. Check: the proposed change is within exact allowed paths and fits existing `theme.v1`, `home.v1`, and `catalog.v1` contracts or has explicit coordinator-approved version scope.
2. Trace data from the typed view model into React presentation. Themes may consume validated display data and presentation capabilities, not decide identity, permissions, route behavior, CSRF, audit, or database ownership. Check: no new component or manifest capability crosses those boundaries.
3. Add a focused synthetic test for the assigned behavior. For localization, cover supported/unsupported locale input, exact-language-default fallback order, missing-key visibility, and stable view-model shape as relevant. For manifests, cover unsupported versions and capability expansion. Check: the test rejects an invalid state and does not require production catalogs or credentials.
4. Implement the smallest functional change, leaving visual-only work to an explicitly scoped visual card. Check: `git diff --name-only` contains only allowed frontend paths and any evidence file authorized by the card.
5. Verify Node meets `frontend/package.json`'s `>=26.7.0` engine. From `frontend`, run `terminal(command="npm ci --include=dev --ignore-scripts")`, `terminal(command="npm run typecheck")`, `terminal(command="npm test")`, and `terminal(command="npm run build")`; from the repo root run `terminal(command="git diff --check")`. Check: record actual exit statuses and test counts for each command; a partial test or missing `tsc` is unverified, not a pass.

## Pitfalls

- The current package has no `lint` script or browser test command. Do not invent one for a handoff.
- React themes receive presentation data; they do not grant permissions by hiding controls.
- A full test count changes as cases are added. Recompute it from the exact candidate, as stale counts caused F13/F14 review RETRY verdicts.

## Verification

Read the generated test output and the exact `frontend` diff. Confirm the typed contract and negative tests pass on the same commit reported to the coordinator. Keep functional frontend and visual fixture scopes distinct.

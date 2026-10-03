---
name: phpretro-integration-acceptance
description: Integrate and accept reviewed PHP-Retro work.
version: 0.1.0
author: Karim, Hermes Agent
license: GPL-3.0-only
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [phpretro, coordinator, integration, evidence]
---

# PHP-Retro integration and acceptance

Build one authoritative candidate from bounded worker commits, obtain independent review, and state exactly what was delivered. The coordinator retains final source, test, security, schema, production, and runner authority under `AGENTS.md`.

## When to use

- Worker cards have handed off commits for a coordinator-owned integration unit.
- An independent review returned ACCEPTED or RETRY and final delivery state must be reconciled.
- A coordinator card is approaching its continuation checkpoint.

## Do not use for

- Issuing the independent reviewer verdict, approving the coordinator's own changes as reviewer, or treating an accepted candidate as merged/delivered.
- Bypassing an operator-owned gate or claiming cost savings without a matched comparison.

## Procedure

1. Use `kanban_show` on every worker and parent card. Record accepted base SHA, authoritative worker commits, exact changed paths, test results, and unresolved blockers. Check: every input commit resolves with `terminal(command="git cat-file -e <commit>^{commit}")` and belongs to the intended card; worktree-only changes are named as such and are not counted as integrated.
2. Assemble the candidate on the accepted integration base without pulling in unrelated work. Inspect source and exact diff with `terminal(command="git diff --name-only <base>..<candidate>")`, `terminal(command="git diff --check <base>..<candidate>")`, and `search_files` for changed contracts and evidence. Check: every path is within an authorized card scope and no conflict marker or unexplained behavior is present.
3. Run the applicable repository checks at the candidate SHA: pinned Go 1.25.13 (`go test ./...`, `go test -race ./...`, `go vet ./...`, `gofmt` check) and/or frontend (`npm ci --include=dev --ignore-scripts`, `npm run typecheck`, `npm test`, `npm run build` from `frontend`). Use the approved pinned runner if host Go is absent. Check: record exact command, environment/toolchain, exit status, and counts; mark unavailable checks unverified, never passed.
4. Reconcile each `docs/evidence/**` claim with the actual candidate, source citation, command output, base SHA, toolchain, and test counts. Preserve `UNKNOWN` where source does not prove a value. Check: a second reader can reproduce every numerical and identifier claim; F13/F14 stale evidence is a known rejection class.
5. Create or update the parent-gated independent `reviewer` card with the candidate SHA and checkout target before releasing it from integration gating; when creating it, pin `phpretro-independent-review` in `kanban_create.skills`. Read its findings-first verdict and fix/re-review RETRY results. Check: reviewer checkout HEAD equals the candidate and the verdict addresses exact scope, tests, security/compatibility, and evidence; no self-review substitutes for it.
6. After an ACCEPTED verdict, verify whether the candidate actually reached the recorded integration or delivery ref. Record separate states for worker commit, reviewed candidate, accepted candidate, integration commit, and delivered ref. Recheck board health and successor/stop requirement before `kanban_complete`. Check: the completion text never says “delivered” for an unmerged accepted candidate.
7. Record A6API model IDs, reasoning, input/cached-input/output tokens, retries, wall time, Jev calls/cost, result, and acceptance status for this unit. Check: missing telemetry is marked unavailable; any savings statement uses matched Sol-only and Jev/Luna cases with the same question and main model.

## Pitfalls

- Passing tests does not waive card scope or an inaccurate evidence document.
- `origin/main` may lag an accepted local integration head; record and verify the actual authority instead of assuming a branch name.
- `kanban_complete` is a board transition, not proof of an external Git delivery.

## Verification

Use `terminal(command="git rev-parse HEAD")` and `terminal(command="git merge-base --is-ancestor <accepted-base> <candidate>")` with exact SHAs; check exit status. Read back the reviewer result and final Git ref, then use `kanban_list`/`kanban_show` to confirm successor or stop. The final handoff names the candidate and delivered refs separately.

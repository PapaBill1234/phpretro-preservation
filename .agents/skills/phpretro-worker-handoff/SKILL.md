---
name: phpretro-worker-handoff
description: Implement scoped PHP-Retro cards with evidence.
version: 0.1.0
author: Karim, Hermes Agent
license: GPL-3.0-only
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [phpretro, worker, scope, handoff]
---

# PHP-Retro worker handoff

Execute an assigned card within its recorded boundary and give the coordinator a reproducible commit-level handoff. Use the backend, frontend, or visual domain skill for surface-specific checks. `AGENTS.md` remains the authority for profile and stop rules.

## When to use

- A dispatcher-assigned `backend`, `frontend`, or `visual` card requests implementation, regression tests, fixtures, or evidence.
- A worker retries a card and must inspect prior attempts before editing.

## Do not use for

- Expanding allowed paths, inventing APIs/schema, changing board dependencies, accepting one's own result, pushing `main`, or touching production data.
- A coordinator-owned security, production, schema ownership, or runner decision.

## Procedure

1. Call `kanban_show` for the assigned card and read `AGENTS.md` plus named parent results. Use `terminal(command="git rev-parse HEAD")` and `terminal(command="git status --short")`. Check: profile, accepted base, exact allowed paths, test/evidence obligations, stop conditions, and prior retry outcome are known before any edit. If the checkout or scope is wrong, use `kanban_block` with the exact reason.
2. Use `search_files`/`read_file` on the assigned source, tests, and `docs/evidence/**`; retain unknown schema, ownership, and runtime values as `UNKNOWN`. Check: the proposed change is supported by source or the card's explicit new contract, and any file needed outside scope has been escalated rather than silently edited.
3. Establish a focused regression or contract test for the assigned behavior when a testable defect or interface change is involved, then implement the smallest scoped change. Check: the test observes behavior, including the relevant negative case, rather than merely mirroring code structure.
4. Run the domain skill's focused checks, then the applicable full repository checks. Use `terminal(command="git diff --check")`, `terminal(command="git diff --name-only")`, and `terminal(command="git status --short")`. Check: every changed file is allowed, every command's actual exit status and environment are recorded, and failures are preserved instead of described as passes.
5. Produce the card's requested commit when possible; record `terminal(command="git rev-parse HEAD")` and the exact changed-file list for that commit. If only uncommitted work exists, report it as worktree state, not an authoritative commit. Check: base SHA, commit SHA, changed paths, test evidence, remaining risk, assumptions, blockers, and retry count are all in the handoff.
6. Use the card's native Kanban completion or review handoff (`kanban_complete` or `kanban_request_review`) with concise summary and structured metadata. If a separate reviewer card is already linked, complete the worker handoff without creating a duplicate review route; use `kanban_request_review` only when the card specifies that native transition. Check: report local implementation, commit, independent review, integration, and verified delivery as distinct states; claim only the states actually evidenced. Never self-approve.

## Pitfalls

- A successful local test is not an integrated or reviewed result.
- A reviewer may receive a base-only worktree; the coordinator must make the exact candidate reachable before independent review.
- If a toolchain is missing, stop the unsupported check and mark it unverified; do not infer a pass from another package or an old run.

## Verification

Read back `kanban_show` after the handoff. Confirm the commit exists, `git diff --check` passes, and the recorded changed-file list matches the card scope. Leave explicit `UNKNOWN` and blocked checks for the coordinator instead of filling gaps from memory.

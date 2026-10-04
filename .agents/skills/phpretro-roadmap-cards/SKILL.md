---
name: phpretro-roadmap-cards
description: Plan bounded PHP-Retro roadmap cards and successors.
version: 0.1.0
author: Karim, Hermes Agent
license: GPL-3.0-only
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [phpretro, kanban, coordinator, planning]
---

# PHP-Retro roadmap cards

Turn an authorized roadmap unit into the smallest executable Kanban graph. `AGENTS.md` governs model, role, authority, dispatch, and continuation rules; this skill supplies the card-writing procedure.

## When to use

- A `coordinator` card must choose the next source-backed unit or create implementation, review, and successor cards.
- A completed unit changes the next authorized dependency or file scope.

## Do not use for

- An exact lookup or tiny edit that needs no card.
- Treating a planning draft, completed worker branch, or Jev verdict as authorization for deferred security, schema, production, or runner work.
- Dispatch preflight or failed-card repair; use `phpretro-dispatch-recovery` for those states.

## Procedure

1. Use `read_file` on `AGENTS.md`, `DECISIONS.md`, `tasks/queue.md`, and `docs/ai-run-state.md`; use `kanban_list`/`kanban_show` for the live board and `terminal(command="git rev-parse HEAD")` for this checkout. Check: record the accepted integration head, current authorization, active successors, and any disagreement among the queue, board, and Git. Reconcile a disagreement before issuing implementation cards.
2. Use `search_files` and `read_file` to inspect the exact source, relevant `docs/evidence/**`, task brief, and tests. Select the smallest unit with a named behavior and source authority. Check: cite the files that prove the behavior and list every `UNKNOWN` or operator-owned gate; do not silently promote a draft roadmap item to approved work.
3. Draft each card with assignee profile, exact allowed paths, accepted base SHA, prerequisite card IDs and accepted results, evidence to produce, focused and full checks, done criteria, stop conditions, token cap, and isolated `worktree` boundary. Before `kanban_create`, use `terminal(command="git merge-base --is-ancestor <recorded-base> <accepted-head>")` with real SHAs and compare active file scopes. Pin relevant installed role skills in `kanban_create.skills`: `phpretro-worker-handoff` plus the matching Go, React, or visual skill for workers; `phpretro-independent-review` for reviewer cards. Use returned IDs in `parents`/`kanban_link`, never invented IDs. Check: ancestry exits zero, scopes do not conflict, every named skill exists on the assignee profile, every card can be judged without expansion, and the graph has no cycle or coordinator-waits-on-own-child edge.
   Leave per-card model and provider overrides unset so the assignee's tested profile default is used. Set an override only after an exact model/provider smoke test succeeds; a similar-looking model name is not evidence that the provider accepts it. A provider HTTP 400 before the first answer is a configuration stop, not a reason to retry the same card unchanged.
4. Put implementation before authoritative integration, independent review against the integration candidate, and final coordinator verification. A precreated review card must depend on integration and state that its exact candidate SHA must be filled from the integration result before it can run; an unknown target is not dispatch-ready. Link a successor coordinator card to the result it must inspect. Check: the reviewer will receive an exact candidate commit rather than a base-only worktree, and the successor cannot run before its required accepted parent.
5. Re-read new cards with `kanban_show` and inspect the board with `kanban_list`. Check: there is no overlapping active edit scope, no satisfied-but-blocked prerequisite, and at least one ready/running successor or an explicit stop reason allowed by `AGENTS.md`. Only then complete the current coordinator card, listing actual created IDs in `kanban_complete.created_cards`.

## Pitfalls

- A card marked `done` can still contain a RETRY review verdict; inspect its result, not status alone.
- A worker commit in a sibling worktree is not an accepted integration base.
- `kanban_create` may parent a child to the current card. Never do that when the current card must wait for that child; F10's dependency cycle archived a whole descendant chain.

## Verification

Use `kanban_show` to confirm every created card's body, owner, returned ID, and dependency edges. Use `terminal(command="git merge-base --is-ancestor <recorded-base> <accepted-head>")` with the actual recorded SHAs; exit status must be zero before the card is considered dispatch-ready. Record a stop reason if no authorized successor exists.

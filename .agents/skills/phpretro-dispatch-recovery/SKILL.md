---
name: phpretro-dispatch-recovery
description: Preflight and recover PHP-Retro Kanban cards.
version: 0.1.0
author: Karim, Hermes Agent
license: GPL-3.0-only
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [phpretro, kanban, coordinator, recovery]
---

# PHP-Retro dispatch and recovery

Check readiness at the last responsible moment and repair failed cards without hiding their history. The gateway dispatcher owns claims, retries, worktrees, and terminal transitions; `AGENTS.md` supplies the mandatory ancestry and accepted-parent rules.

## When to use

- Before a `coordinator` unblocks or allows dispatch of a PHP-Retro card.
- A card is blocked, crashed, stale, archived for recovery, or pointed at a missing worktree/candidate.
- A board-health checkpoint finds an empty queue, satisfied blocked card, or invalid dependency chain.

## Do not use for

- Worker edits, reviewer acceptance, or changing gateway/runner policy.
- Unblocking a stale card as a shortcut, retrying an A6API credential/model failure as source work, or erasing the failed card.

## Procedure

1. Use `kanban_show` on the card and each parent; use `kanban_list` for active and blocked siblings. Record status, result/verdict, profile, exact file scope, base SHA, parent IDs, target commit, run error, and worktree. Check: the first observable blocker and the card's intended deliverable are identified from board evidence, not guessed from its title.
2. Obtain the accepted integration head from the coordinator's recorded result and verify it with Git. Use `terminal(command="git cat-file -e <recorded-base>^{commit}")` and `terminal(command="git merge-base --is-ancestor <recorded-base> <accepted-head>")` after substituting real SHAs. For a review card, compare checkout `git rev-parse HEAD` with its exact candidate SHA. Check: all identifiers resolve and ancestry/target checks exit zero; a worktree-only or deleted ref fails preflight.
3. Verify every required parent is terminal **and accepted** by reading its result, not just its status. Compare allowed paths of ready/running cards before activating another editor; inspect dependency edges for cycles or a coordinator waiting on its own descendant. Check: no unsatisfied parent, overlapping active file scope, or cycle remains.
4. Classify the failure as scope, stale base/target, dependency, test/evidence, implementation, or environment/provider/runner. Preserve the original event, run summary, commit, and test evidence in a linked recovery card or durable comment. Check: the recovery names a specific root cause and exact gate that would prevent recurrence.
5. For a stale base or worktree-only candidate, archive the invalid card through the supported coordinator board operation and create a replacement from the accepted integration head; link it to the failed card and accepted parents. For a provider/runner error, stop dispatch retries and route the configuration decision to the coordinator. Use `kanban_unblock` only after steps 2–3 pass. Check: the replacement is independently reviewable and the old failure remains discoverable.
6. Re-list the board. Check: no blocked card has satisfied prerequisites, no active card points only to a stale/deleted worktree, and a ready/running successor or explicit authorized stop record exists.

## Pitfalls

- `done` means a run completed; a review result can still be RETRY.
- A reviewer worktree at the accepted base is not the implementation candidate, even when all worker parent cards are done.
- A terminal provider exit is infrastructure evidence. Cloning sibling cards before configuration repair repeated the F12 failure.

## Verification

Read back replacement card body, dependency IDs, base, status, and recovery link with `kanban_show`. Confirm candidate ancestry and exact HEAD with `terminal`; do not infer success from a green worker summary. From the repository root, `docs/phpretro-card-failure-atlas.md` has representative stale-base, dependency-cycle, and provider cases.

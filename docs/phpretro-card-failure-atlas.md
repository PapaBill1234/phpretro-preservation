# PHP-Retro Kanban card failure atlas

Read-only snapshot, 2026-10-03 UTC. Source: `HERMES_HOME/kanban/boards/phpretro-preservation/kanban.db` (`tasks`, `task_runs`, `task_links`, `task_events`), card logs in that board directory, and this repository's Git refs/history. This is an operational diagnosis, not a board edit. All 29 rows below are **archived** cards. `—` in the base column means no literal 40-character base SHA was recorded in the card body; it does not assert that the worker had no checkout. Short SHAs are identifiers, not ancestry proof by themselves.

Board totals: 79 cards, 50 done, 29 archived; 78 run records including 14 blocked, nine crashed, three reclaimed, one changes requested, and one review requested. The board currently has no ready/running card and has an explicit roadmap stop record. The board begins at F8, so earlier F0–F7 failures cannot be inferred from this database. Git/task/evidence history for those units was inspected separately in the [program design](phpretro-skill-program-design.md).

One batched advisory Jev call classified five failure-pattern questions from compact card facts (475 ms, 1,101 input tokens, 330 output tokens; estimated cost unavailable). Its answers agreed with the board run summaries and Git checks reported below. This was not a matched cost comparison or an acceptance decision.

## Archived-card inventory and first observable cause

| Card and title | Profile | Base; parent(s) | Worktree/branch | First observable cause |
| --- | --- | --- | --- | --- |
| `t_9ace1363` F8 independent review | reviewer | —; none | `wt/f8-reviewer` | First run found no implementation commits; second found failing `TestLocalizedKeyVariesByLocale` for unsupported `xx-XX`. |
| `t_3c826b59` F9 backend localized view model | backend | `0fd95a4`; none | `wt/t_3c826b59` | Base lacked F8 localization source, task contract, and evidence. |
| `t_b9b200c8` F9 independent review | reviewer | `0fd95a4`; none | `wt/t_b9b200c8` | Same missing F8 predecessor; F9 backend sibling was blocked. |
| `t_8d9530f2` continuation after F10 | coordinator | —; none | `wt/autonomous-after-f10` | Blocked waiting for integration `t_d87451a2`, which was created as its own child. |
| `t_d87451a2` F10 integration | coordinator | `f9273a1`; `t_8d9530f2` | assigned repository workspace | Never ran; parent was blocked waiting on this child. |
| `t_a13d8fbe` F10 acceptance review | reviewer | —; `t_d87451a2` | assigned repository workspace | Never ran; integration parent never completed. |
| `t_0bf0a06a` continuation after F10 acceptance | coordinator | —; `t_a13d8fbe` | assigned repository workspace | Never ran; review parent never completed. |
| `t_f9e4f87d` F11 backend continuation | backend | —; `t_d87451a2` | `wt/f11-backend` | Never ran; inherited the blocked F10 integration dependency. |
| `t_480d15ee` F11 frontend continuation | frontend | —; `t_d87451a2` | `wt/f11-frontend` | Never ran; same inherited dependency. |
| `t_6ab91911` F11 visual continuation | visual | —; `t_d87451a2` | `wt/f11-visual` | Never ran; same inherited dependency. |
| `t_2ba5fead` F11 backend follow-up | backend | —; `t_a13d8fbe` | assigned repository workspace | Never ran; inherited uncompleted F10 review. |
| `t_4d3ae32d` F11 frontend follow-up | frontend | —; `t_a13d8fbe` | assigned repository workspace | Never ran; same inherited dependency. |
| `t_57b00e48` F11 visual follow-up | visual | —; `t_a13d8fbe` | assigned repository workspace | Never ran; same inherited dependency. |
| `t_b8237a67` F10/F11 release review | reviewer | —; `t_d87451a2` | assigned repository workspace | Never ran; inherited uncompleted integration. |
| `t_de200c71` F11 regression review | reviewer | `f9273a1`; `t_e411243e`, `t_385047d4`, `t_338f5300` | `wt/t_de200c71` | Review checkout was only the old base; three completed sibling artifacts were not integrated. |
| `t_52daa7ff` F11 integration planner | coordinator | —; `t_de200c71` | assigned worktree | Never ran; reviewer parent blocked. |
| `t_f51d46b7` F12 continuation | coordinator | `031a336`; none | `wt/f12-coordinator` | Two runs crashed with terminal provider credential/model error, exit 78. |
| `t_cad2daed` F12 backend | backend | `031a336`; none | `wt/f12-backend` | Two runs crashed with the same provider error. |
| `t_9eaf8759` F12 frontend | frontend | `031a336`; none | `wt/f12-frontend` | Two runs crashed with the same provider error. |
| `t_9d3cb038` F12 visual | visual | `031a336`; none | `wt/f12-visual` | Run crashed with the same provider error. |
| `t_29710316` F12 visual v2 | visual | `031a336`; none | `wt/f12-visual-v2` | Replacement also crashed with the same provider error. |
| `t_131a1dd1` F12 regression review | reviewer | `031a336`; `t_c9e63ed3`, `t_f278ce93`, `t_0c9abc52` | `wt/t_131a1dd1` | Checkout HEAD was `f9273a1`, not an integrated F12 result. |
| `t_5161b271` F13 regression review | reviewer | `8239973`; `t_c9f82237`, `t_b7838452`, `t_e4ce2b5c` | `wt/t_5161b271` | Checkout HEAD equalled F12 base `8239973`; no F13 source/evidence was present. |
| `t_6efb0e86` F13 integration continuation | coordinator | `8239973`; `t_5161b271` | `wt/t_6efb0e86` | Re-review required because F13 evidence test counts were stale; candidate commit absent from this checkout. |
| `t_b6593b32` F14 acceptance review | reviewer | `b1722a9`; `t_71bb5409`, `t_b682c523`, `t_6653e2be` | `wt/t_b6593b32` | After a manual reclaim, required F13 base `b1722a9` was not an ancestor of review HEAD `8239973`. |
| `t_75c6867f` F14 continuation | coordinator | —; `t_b6593b32` | assigned repository workspace | Never ran; reviewer parent blocked and was archived. |
| `t_007e829b` F13 evidence correction | coordinator | `b1722a9`, `031a336`; `t_91db0bf4` | `wt/t_007e829b` | Correction commit `aba5617` existed, but the accepted-base/integration precondition was unresolved; worker blocked rather than treating worktree-only evidence as delivered. |
| `t_5a91844f` F13/F14 recovery review | reviewer | `031a336`; `t_502abfab` | `wt/t_5a91844f` | Reclaimed at preflight: review HEAD `8239973` did not equal named candidate `ef970ee`. |
| `t_1cfa07a6` post-F14 stop record | coordinator | —; `t_43e78c42`, `t_dee7877c` | `wt/t_1cfa07a6` | Reviewer parent returned RETRY for stale evidence; final acceptance/stop could not yet be recorded. |

All titles, owners, status, bases, dependency IDs, branch names, and outcomes above are from board rows. For never-run descendants, the cause is the `dependency_wait` event (`parent_not_done`) and the preceding parent run; those rows are not counted as code failures. `assigned repository workspace` reflects a board path without a unique branch, another reason an exact target checkout must be established before dispatch.

## Root causes, recoveries, and reusable gates

1. **Prerequisite and test defect, F8–F9 (three archived cards).** F9 cards were drafted against accepted F7 commit `0fd95a4` while the F8 source was still in separate worktrees. The F8 reviewer also found an actual unsupported-locale cache-key regression. Later F8 follow-up cards corrected the implementation, and integrated F9 review `t_937b2edc` ran against `f9273a1`. Prevention: author each card from an accepted, source-containing base and require a focused negative locale test before review. A terminal worker status is not proof that its source is present at the review target.
2. **Self-blocking dependency graph, F10–F11 (11 archived cards).** `t_8d9530f2` blocked waiting for `t_d87451a2`, but the latter's parent was `t_8d9530f2`. Nine further F10/F11 descendants waited on that chain. Fresh F11 cards `t_e411243e`, `t_385047d4`, and `t_338f5300` were created outside it. Prevention: graph cycle/ancestor check when authoring and before `ready`; a coordinator successor can depend on integration, while the integration card cannot depend on the coordinator that is waiting for it. The gate must check every parent is terminal and accepted, not merely marked done.
3. **Review-before-integration, F11 and F12–F13 (review cards plus descendants).** F11 `t_de200c71`, F12 `t_131a1dd1`, and F13 `t_5161b271` received base-only checkouts while worker commits lived in sibling worktrees. F12 recovery integrated at `8239973` and used `t_857498ba` for integrated review; F13 recovery `t_0381275a` built `b1722a9` and created `t_91db0bf4`. Prevention: coordinator first records a reachable candidate commit; reviewer preflight verifies exact HEAD, base ancestry, all three parent results, and diff scope. The test gate is the applicable pinned Go/frontend matrix on that exact candidate.
4. **Provider/runner failure, initial F12 (five archived cards).** Eight crash runs across coordinator/backend/frontend/visual show terminal provider credential/model exit 78, including a replacement visual card that repeated it. Later retry cards `t_06416fec`, `t_3461d494`, `t_2576b46a`, and `t_7891fd7f` completed. Prevention: coordinator-owned A6API/profile preflight before dispatching a batch; on terminal auth/model/quota errors, preserve the error and stop retrying or cloning cards until configuration is verified. This is not a worker code or test failure.
5. **Stale ancestry and evidence, F13–F14.** F13 reviewer `t_91db0bf4` returned RETRY because frontend full/focused test counts were 11/8 rather than claimed 10/7. F14 backend card `t_71bb5409` had a changes-requested run because `b1722a9` was not an ancestor of its review worktree; F14 reviewer `t_b6593b32` later blocked on the same ancestry class. The F13 correction commit `aba5617` was not enough to claim integrated delivery. Coordinator recovery `t_502abfab` rebuilt candidate `ef970ee` from accepted `origin/main` `031a336` and created a fresh reviewer. Prevention: distinguish a worktree commit from accepted integration; recreate stale cards from accepted head, link old IDs, verify exact diff and ancestry, and reconcile evidence counts from actual commands before acceptance.
6. **Scope and evidence rejection after recovery.** Recreated reviewer `t_d1406d3d` returned RETRY because `ef970ee` touched production `frontend/src/localization/index.ts` outside the synthetic-only scope, despite green tests. Correction `t_43e78c42` produced `719762c`; reviewer `t_dee7877c` returned RETRY because F14 evidence still named stale base/toolchain/test counts. The stop-record card `t_1cfa07a6` correctly blocked on that RETRY. Final correction `t_894a4fa8` produced `c2d0ef3`, independently accepted by `t_125fd193`; `t_6ba711ba` recorded an authorized stop. Prevention: compare every changed path and claim against the actual candidate and test output; a green test suite does not waive card scope or evidence accuracy. Re-review every recovered candidate independently.

The accepted F14 candidate `c2d0ef3` changes exactly seven test/evidence paths and is a descendant of `origin/main` `031a336`. Git confirms it is **not** an ancestor of current checkout `8239973` or `origin/main`; the board's final stop record also says it did not integrate or deliver F14 to main. The design therefore uses distinct `implemented`, `reviewed`, `accepted candidate`, `integrated`, and `delivered` states.

## Non-archived runs that still required correction

| Card | Observable issue and result |
| --- | --- |
| `t_f5f7d0ca` F8 coordinator integration | An initial blocked run found all F8 branches still at base with no localization commits; a later run completed after follow-up work. |
| `t_71bb5409` F14 backend | Implementation requested review, then received changes requested because required base `b1722a9` was not an ancestor of the review checkout. Its eventual done status does not erase that dispatch defect. |
| `t_91db0bf4` F13 reviewer | Done run returned RETRY on stale frontend test counts (11 full, eight focused versus claims of 10 and seven). |
| `t_502abfab` F13/F14 recovery | One manual reclaim occurred during Nerve parser repair; a subsequent run built `ef970ee`. Treat parser/runner repair as infrastructure evidence, not source acceptance. |
| `t_d1406d3d` F13/F14 recovery reviewer | Done run returned RETRY on out-of-scope production localization source in `ef970ee`. |
| `t_43e78c42` F14 scope correction | First run crashed when its worker process was no longer alive; second run completed candidate `719762c`. Preserve both run outcomes. |
| `t_dee7877c` F14 corrected-candidate reviewer | Done run returned RETRY on stale base/toolchain/test-count claims in F14 evidence. |
| `t_6ba711ba` final coordinator stop | First run blocked while review `t_125fd193` was still running; second completed only after an ACCEPTED review verdict. |

## Cross-roadmap findings

The durable board is concentrated on F8–F14 localization. The broader repository still contains recurring, different work: F1 password-scheme and F3/F5 schema evidence, F2 account/session contracts, F4 golden comparator, F6 PolarIS read adapter, F7 React/theme and Redis-like cache, later website-owned mutations and audit, staff TOTP, guestbook privacy, housekeeping/locales, and possible client integration. `docs/fresh-start-rewrite-plan-draft.md` is a proposed roadmap, not authorization for those later gates; `tasks/queue.md` and `DECISIONS.md` defer F9+ production/CMS/security work. The skill program's evaluation cases cover these source and test surfaces without inventing a new live card.

## Required metrics before claiming improvement

Use this atlas as the frozen baseline, with denominator and category recorded: archived cards per created card; blocked/crashed runs per dispatched run; stale-base dispatches; base-only reviewer checkouts; cyclic dependency descendants; provider retries; scope/evidence rejections; time and cost per accepted unit. Compare the same task/state and A6API model with and without selected skills. For any Jev-assisted case, report main-model input, cached-input, output tokens, time, Jev count and estimated cost, and answer correctness for both matched variants. A Jev verdict alone is not a measured saving.

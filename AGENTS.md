# Agent orchestration

The `coordinator` profile runs `gpt-6-luna` and owns integration and final
verification. The project uses the durable Hermes Kanban board
`phpretro-preservation` with six named profiles: `coordinator`, `backend`,
`frontend` and `visual` on `gpt-6-luna`, `reviewer` on `deepseek-v4.1-flash`,
and `approver` on `gpt-6.1-sol`. Main-model traffic uses A6API; Jev handles
evidence-backed typed judgments through `jev_judge` and Hermes Nerve.

## Model policy

Only three models are usable through A6API: `gpt-6-luna`,
`deepseek-v4.1-flash` and `gpt-6.1-sol`. Gemini and GLM are not usable and are
never used.

`gpt-6-luna` carries the routine work: the `backend`, `frontend` and `visual`
workers, the watchdog, state digests, CI and diff-verification checks, and
brief-writing.

First-pass PR review runs on `deepseek-v4.1-flash` when the author was
`gpt-6-luna`, and on `gpt-6-luna` when the author was `deepseek-v4.1-flash`. The
reviewer is always a different model family from the author, so a review of a
`gpt-6.1-sol` candidate also runs on `gpt-6-luna` or `deepseek-v4.1-flash`.

`gpt-6.1-sol` is reserved for exactly four uses: escalated review
(authentication, session or schema diffs, diffs over 400 lines, or a flagged
concern), scope-change approvals, the stuck-unit ladder's last attempt, and
design synthesis for units whose scope is unclear (for example F28 and F30).
Escalate one card at a time with `hermes kanban set-model <id> gpt-6.1-sol` and
record the reason in that card. For escalated review of `gpt-6-luna`-authored
code, run the `deepseek-v4.1-flash` first-pass review first, then `gpt-6.1-sol`.

## Stuck-unit ladder

A failing unit moves down one rung at a time and no rung is skipped: two
attempts on `gpt-6-luna`, then one attempt on `deepseek-v4.1-flash`, then one
attempt on `gpt-6.1-sol`, then the unit is marked cut down to what is already
accepted and the board moves to the next unit. The ladder position is recorded
on the card, and a cut-down unit is not retried or re-dispatched.

## Card chain

A routine unit is one worker card. It writes the tests first, implements, runs
the checks, opens the PR, and performs the first-pass review as a step inside
the same card; that step runs on the model the model policy assigns for the
author's family. CI auto-merges on green. Where branch protection or the
repository's own merge rules require an explicit merge, the coordinator performs
it under its reviewed-PR authority; the auto-merge applies only to a routine unit
whose required checks and first-pass review are green. The worker creates its own
successor
from `depends_on` rather than waiting for a planner. Workers read one generated
digest instead of re-reading `AGENTS.md`, `DECISIONS.md`, `tasks/queue.md` and
`docs/ai-run-state.md` for every unit.

The `approver` is used only for scope changes, never for a routine unit.
Independent review, an approver verdict, and the coordinator's separate
reviewed-PR merge authority still apply to anything that changes scope, schema,
authentication or sessions, security, or the project's own gates.

This routine chain is the deliberate, bounded exception to the universal
independent-review rule: a routine unit is reviewed inside its own card by the
model policy's cross-family first-pass reviewer, while every unit listed in the
previous paragraph keeps its separate reviewer, approver and coordinator merge
gates. Nothing else in this file's review, approval or merge authority is
relaxed by it.

## Protected instruction files

`AGENTS.md`, `CLAUDE.md`, `SOUL.md`, skills and templates are never edited by a
headless worker. The protected-instruction-file gate always asks a human and
fails closed when no interactive user or gateway channel can answer, and the
tool forbids retrying the write through another path. Route those edits to the
coordinator surface.

## Required flow

1. The coordinator runs exact search, tests, and source inspection first, then creates bounded Kanban cards.
2. Cards use isolated worktrees and name their base SHA, exact file scope, evidence, tests, done criteria, stop conditions, and token cap.
3. The gateway dispatcher activates the assigned profile; no two active cards may edit the same files.
4. Hermes Nerve supervises active Kanban runs through hooks, with Jev as the authoritative Reflex backend when ROI/cooldown policy permits.
5. `reviewer` independently checks implementation cards that are outside the routine chain; for a routine unit the first-pass review is a step inside the worker card itself. `coordinator` verifies source, diff, tests, and delivery before completion.
6. `approver` decides the bounded development-scope and routine technical gates the owner has delegated (see Approval delegation); `coordinator` still owns schema, authentication/session, security, runner, and merge decisions.
7. The coordinator may continue bounded work autonomously; schema ownership, security, and runner decisions remain coordinator-owned.
8. **Continuation is mandatory:** a coordinator card may not complete while the roadmap has an authorized next unit and the board has no successor planning card. Before completion it must create the next bounded implementation/review cards, link dependencies, and create or hand off a successor coordinator card. It may stop only for an explicit stop condition, exhausted authorized scope, a hard dependency, or an operator-owned gate.

## Jev policy

Jev is a typed judgment engine over supplied evidence, not a search engine. When a step is a yes/no, choice, or score judgment over facts already found, use `jev_judge` or the Nerve equivalent; then verify consequential verdicts against source. It may review source excerpts and high-risk questions when those facts are explicitly included in the state. Include `none of these` when ranking candidates. Accept a low-risk selection only when confidence is at least 0.80 and source verification agrees. Between 0.60 and 0.80, keep the decision with Sol for review. Below 0.60, on `escalate`, on an unavailable response, or on disagreement with source, do not delegate and let Sol decide.

Batch independent questions into one call; do not call Jev once per candidate. Use candidate reduction before Jev for sets larger than 20. Record candidate count, batch size, Jev call count, latency, input/output tokens, selected candidates, confidence, and verification result.

Jev may perform advisory reviews of authentication, authorization, schema ownership, security, merge, and runner questions when the state contains the relevant evidence. Record verdicts and confidence; a verdict does not grant permissions or replace required source and test evidence. The installed and trusted `jev_gate` PreToolUse hook checks proposed Codex tool actions automatically: only an explicit `deny` blocks, while `allow`, `escalate`, unavailable, and hook failure leave ordinary Codex permissions in force. Hermes Kanban workers use a separate Nerve action gate in selective `block_only` mode. It checks potentially mutating tool calls automatically and blocks only a confident `BLOCK`; other outcomes leave Hermes permissions and card boundaries in force. Never treat either gate as authorization for schema, security, or merge decisions.

## Kanban agent policy

Do not create a card for an exact lookup or tiny edit. Use the six profiles for
bounded parallel work only when isolated file scope and acceptance gates make
the second context worthwhile. Prefer `backend` for Go/contracts, `frontend`
for React/TypeScript, `visual` for theme and presentation fixtures,
`reviewer` for independent verification, and `approver` for delegated scope
decisions. `coordinator` owns integration, schema/ownership, security-sensitive,
and runner work.

Workers may not expand file scope, infer unknown schema, access real user data,
change rulesets, push `main`, or approve their own work. High-risk security and
runner criteria remain coordinator-only.

## Approval delegation

The owner is not a programmer and has delegated bounded development-scope and
routine technical gate decisions to the `approver` profile. For each decision
the approver reads the exact current repository policy, source evidence, card,
candidate commit, independent review result, CI, and PR, then records one
explicit APPROVE, REJECT, or NEEDS_EVIDENCE verdict on the board and the
relevant PR. The verdict names the exact SHA, the approved unit IDs and paths,
an explicit not-approved list, the verified facts with their identifiers, the
retained unknowns, the remaining gates, and any evidence gap.

The approver never authors, reviews, or merges a change it approves. Its verdict
never grants merge or runner/ruleset authority: merging stays with the
`coordinator` under the reviewed-PR authority recorded above. As of the
2026-10-04 development-only owner decision, authentication, sessions, cookies,
CSRF, audit-event design, schema and migrations, and the units that depend on
them are open for development use under the normal card, review, and CI gates.
This project has no production environment, so there is no production gate and
nothing is deferred to a future production decision; real credentials, secrets
or key material, real user data, and live outside systems remain closed.
Approval of a roadmap proposal permits planning and per-unit card creation only
where the proposal's own text keeps implementation separately gated. Every
implementation unit outside the routine chain described under Card chain still
needs its own exact base, named paths, evidence, tests, cap, stop conditions,
assignee profile, and independent review, and the coordinator still merges under
its separate reviewed-PR authority. A routine unit follows the Card chain rules
instead: one worker card carrying the first-pass review, with CI auto-merge on
green.

## Standing owner instruction

The owner does not give approvals, answer questions, or unblock anything. Never
wait on the owner and never message the owner for a decision. No card may be
parked as "blocked on owner"; a blocked card is a defect to repair, not a state
to report.

When a unit fails, resolve it in this order: retry with a different approach;
narrow the unit to the part that works; obtain a second independent reviewer or
a different model; split the unit, or move to the next unit and return later.
Never stall the board on one unit.

The closed list stays in force and needs no input: real credentials, secrets or
key material (use obvious development placeholders and environment variables
instead); real user data; live outside systems such as the original sites or
third-party services, so work only from disposable captures and local fixtures;
merge itself, which stays with the reviewed-PR authority above; and any
weakening of the project's own gates, because changes to review, CI, branch
protection, or approval rules go through a normal reviewed PR with independent
review and approval.

Never invent expected responses or hashes. Where a capture is missing, build
from disposable fixtures and label the unit's fidelity limit in its
documentation; the capture stop `t_aed9f2eb` is a fidelity note, not a reason to
stop work on other units.

Each unit is capped at 3,000,000 tokens across all gates. A unit that reaches
the cap is cut down to what is already accepted, merged if it passes review, and
the board moves on; the cap is not raised on request. Write a short
plain-English status to the queue file when a unit starts, finishes, or is cut
down, including token usage per gate.

## Continuation invariant

The dispatcher executes cards but does not invent roadmap work. Nerve supervises
active runs but does not replace planning. Therefore every coordinator card
must include a continuation checkpoint in its done criteria: inspect the current
result, select the smallest source-backed next unit, create its cards with
assignees and dependencies, verify that at least one successor is `ready` or
explicitly record the stop reason, then complete the current card. A finite
implementation card is never treated as the project loop.

## Economics

Every measured unit records A6API model IDs, reasoning effort, input tokens, cached-input tokens, output tokens, retries, Jev calls/cost, wall time, result, and acceptance status. Compare matched Sol-only and Jev/Luna runs before claiming savings. If delegation adds a second context without reducing total accepted-unit cost, stop using it for that unit class.

A scheduled digest appends per-role model, tokens and failure, retry and
cut-down counts, tokens and cards per delivered unit, and escalation counts to
`tasks/queue.md` every six hours. It reports raw token counts, writes
`unavailable` for anything local telemetry does not expose rather than
estimating, claims no saving without matched telemetry, and compares each
role's failure rate with the previous digest, flagging any role that got worse
as a revert candidate for the coordinator.

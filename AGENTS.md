# Agent orchestration

The `coordinator` profile runs `gpt-6-luna` and owns integration and final
verification. The project uses the durable Hermes Kanban board
`phpretro-preservation` with six named profiles: `coordinator`, `backend`,
`frontend` and `visual` on `gpt-6-luna`, `reviewer` on `deepseek-v4.1-flash`,
and `approver` on `gpt-6.1-sol`. Main-model traffic uses A6API; Jev handles
evidence-backed typed judgments through `jev_judge` and Hermes Nerve.

## Operating mode: owner-authorized fast mode (2026-10-05)

The owner has explicitly authorized unrestricted agent operation for this
development-only project and asked for maximum speed. The approval, review and
merge gates that previously serialized work are lifted:

- **Approvals are off.** `approvals.mode` is `off`, and
  `approvals.single_query_mode`, `cron_mode` and `unattended_mode` are
  `approve`, so no agent waits on a dangerous-command prompt. Every Kanban card
  runs as a single-query session, so the single-query setting is the one that
  governs workers.
- **No mandatory review chain.** Independent review and an approver verdict are
  no longer required before merge. A worker reviews its own diff as a step
  inside its own card.
- **Agents merge their own work.** A worker that opens a PR merges it once the
  required checks are green. The coordinator merges anything left open. Merging
  is not reserved to any single profile.
- **Scope may expand.** A worker may touch whatever files the unit genuinely
  needs to deliver a working result, and may add dependencies, build wiring and
  manifests. Announce the widened scope in the card and the PR body.
- **Instruction files are editable.** `security.protected_instruction_files` is
  off, so agents may edit `AGENTS.md`, `CLAUDE.md`, `SOUL.md`, skills and
  templates directly.
- **Branch protection** on `main` requires only the `foundation` check; the
  "branches must be up to date" rule is off, so merges no longer serialize.

## What still holds

These are not workflow gates and are not relaxed:

- **No real credentials, secrets or key material.** Use obvious development
  placeholders and environment variables.
- **No real user data.**
- **No live outside systems** - never touch the original sites, third-party
  services or any deployed instance. Work only from disposable captures and
  local fixtures. Never invent expected responses, captures or hashes; where a
  capture is missing, build from fixtures and label the fidelity limit.

## Model policy

Only three models are usable through A6API: `gpt-6-luna`,
`deepseek-v4.1-flash` and `gpt-6.1-sol`. Gemini and GLM are not usable and are
never used.

`gpt-6-luna` carries the routine work: the `backend`, `frontend` and `visual`
workers, the watchdog, state digests, CI and diff-verification checks, and
brief-writing.

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

## Deliver runnable work

The failure mode this project already suffered: units delivered tested library
code that nothing could run. A unit is only complete when its result can
actually be exercised - a server that starts and answers, a page that mounts, a
command that runs. A card must show real command output in its PR body, not
just a passing test count. Prefer one unit that makes something runnable over
three that add isolated packages.

## Required flow

1. The coordinator runs exact search, tests, and source inspection first, then creates bounded Kanban cards.
2. Cards use isolated worktrees and name their base SHA, exact file scope, evidence, tests, done criteria, stop conditions, and token cap.
3. The gateway dispatcher activates the assigned profile; no two active cards may edit the same files.
4. Hermes Nerve supervises active Kanban runs through hooks, with Jev as the authoritative Reflex backend when ROI/cooldown policy permits.
5. A worker verifies its own source, diff, tests and delivery before completing its card. `reviewer` and `approver` are optional aids, not gates.
6. `coordinator` owns schema, authentication/session and security-sensitive work, and integration.
7. The coordinator continues bounded work autonomously.
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

Workers may expand file scope to whatever the unit genuinely needs, and may
merge their own PR. They may not access real user data, real credentials, or
live outside systems.

## Scope

Authentication, sessions, cookies, CSRF, audit-event design, schema and
migrations are open for development use. There is no production environment and
no production gate. Real credentials, secrets or key material, real user data,
and live outside systems remain closed - that is the whole of the closed list.

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
instead); real user data; and live outside systems such as the original sites or
third-party services, so work only from disposable captures and local fixtures.
Merging and the project's own gate settings are no longer restricted.

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

Record A6API model IDs, input tokens, cached-input tokens, output tokens,
retries, wall time, result and acceptance status where telemetry exposes them,
and write `unavailable` rather than estimating. The A6API balance is small and
time-boxed, so prefer fewer, larger, runnable units over many small ones, and
stop a unit that is burning budget without producing something runnable.

A scheduled digest appends per-role model, tokens and failure, retry and
cut-down counts, tokens and cards per delivered unit, and escalation counts to
`tasks/queue.md` every six hours. It reports raw token counts, writes
`unavailable` for anything local telemetry does not expose rather than
estimating, claims no saving without matched telemetry, and compares each
role's failure rate with the previous digest, flagging any role that got worse
as a revert candidate for the coordinator.

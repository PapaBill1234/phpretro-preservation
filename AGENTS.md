# Agent orchestration

Sol (`gpt-6.1-sol`) is the coordinator and final verifier. The project uses the
durable Hermes Kanban board `phpretro-preservation` with six named profiles:
`coordinator` (Sol), `backend` (Luna), `frontend` (Luna), `reviewer` (Sol),
`visual` (Luna), and `approver` (Sol). Main-model traffic uses A6API; Jev handles
evidence-backed typed judgments through `jev_judge` and Hermes Nerve.

## Required flow

1. Sol runs exact search, tests, and source inspection first, then creates bounded Kanban cards.
2. Cards use isolated worktrees and name their base SHA, exact file scope, evidence, tests, done criteria, stop conditions, and token cap.
3. The gateway dispatcher activates the assigned profile; no two active cards may edit the same files.
4. Hermes Nerve supervises active Kanban runs through hooks, with Jev as the authoritative Reflex backend when ROI/cooldown policy permits.
5. `reviewer` independently checks implementation cards; `coordinator` verifies source, diff, tests, and delivery before completion.
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
implementation unit still needs its own exact base, named paths, evidence,
tests, cap, stop conditions, assignee profile, and independent review, and the
coordinator still merges under its separate reviewed-PR authority.

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

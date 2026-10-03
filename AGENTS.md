# Agent orchestration

Sol (`gpt-6.1-sol`) is the coordinator and final verifier. The project uses the
durable Hermes Kanban board `phpretro-preservation` with five named profiles:
`coordinator` (Sol), `backend` (Luna), `frontend` (Luna), `reviewer` (Sol),
and `visual` (Luna). All model traffic uses A6API; Jev is reserved for
evidence-backed typed judgments through Hermes Nerve.

## Required flow

1. Sol runs exact search, tests, and source inspection first, then creates bounded Kanban cards.
2. Cards use isolated worktrees and name their base SHA, exact file scope, evidence, tests, done criteria, stop conditions, and token cap.
3. The gateway dispatcher activates the assigned profile; no two active cards may edit the same files.
4. Hermes Nerve supervises active Kanban runs through hooks, with Jev as the authoritative Reflex backend when ROI/cooldown policy permits.
5. `reviewer` independently checks implementation cards; `coordinator` verifies source, diff, tests, and delivery before completion.
6. The coordinator may continue bounded work autonomously; production, schema ownership, security, and runner decisions remain coordinator-owned.
7. **Continuation is mandatory:** a coordinator card may not complete while the roadmap has an authorized next unit and the board has no successor planning card. Before completion it must create the next bounded implementation/review cards, link dependencies, and create or hand off a successor coordinator card. It may stop only for an explicit stop condition, exhausted authorized scope, a hard dependency, or an operator-owned gate.

## Jev policy

Jev is a typed judgment engine over supplied evidence, not a search engine. It may review source excerpts and high-risk questions when those facts are explicitly included in the state. Include `none of these` when ranking candidates. Accept a low-risk selection only when confidence is at least 0.80 and source verification agrees. Between 0.60 and 0.80, keep the decision with Sol for review. Below 0.60, on `escalate`, on an unavailable response, or on disagreement with source, do not delegate and let Sol decide.

Batch independent questions into one call; do not call Jev once per candidate. Use candidate reduction before Jev for sets larger than 20. Record candidate count, batch size, Jev call count, latency, input/output tokens, selected candidates, confidence, and verification result.

Jev may perform advisory reviews of authentication, authorization, schema ownership, production enablement, security, merge, and runner questions when the state contains the relevant evidence. Verdicts and confidence must be recorded; a verdict does not grant permissions or replace required source and test evidence. The installed `jev_gate` PreToolUse hook is enabled as a safety check for tool actions; `allow`, `escalate`, unavailable, or hook-failure results leave ordinary Codex permissions in force, and only an explicit `deny` blocks the proposed action.

## Kanban agent policy

Do not create a card for an exact lookup or tiny edit. Use the five profiles for
bounded parallel work only when isolated file scope and acceptance gates make
the second context worthwhile. Prefer `backend` for Go/contracts, `frontend`
for React/TypeScript, `visual` for theme and presentation fixtures, and
`reviewer` for independent verification. `coordinator` owns integration,
schema/ownership, security-sensitive, production, and runner work.

Workers may not expand file scope, infer unknown schema, access production
data, change rulesets, push `main`, or approve their own work. High-risk
security and runner criteria remain coordinator-only.

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

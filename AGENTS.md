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
6. `approver` decides the bounded development-scope and routine technical gates the owner has delegated (see Approval delegation); `coordinator` still owns schema, authentication/session, security, production, runner, and merge decisions.
7. The coordinator may continue bounded work autonomously; production, schema ownership, security, and runner decisions remain coordinator-owned.
8. **Continuation is mandatory:** a coordinator card may not complete while the roadmap has an authorized next unit and the board has no successor planning card. Before completion it must create the next bounded implementation/review cards, link dependencies, and create or hand off a successor coordinator card. It may stop only for an explicit stop condition, exhausted authorized scope, a hard dependency, or an operator-owned gate.

## Jev policy

Jev is a typed judgment engine over supplied evidence, not a search engine. When a step is a yes/no, choice, or score judgment over facts already found, use `jev_judge` or the Nerve equivalent; then verify consequential verdicts against source. It may review source excerpts and high-risk questions when those facts are explicitly included in the state. Include `none of these` when ranking candidates. Accept a low-risk selection only when confidence is at least 0.80 and source verification agrees. Between 0.60 and 0.80, keep the decision with Sol for review. Below 0.60, on `escalate`, on an unavailable response, or on disagreement with source, do not delegate and let Sol decide.

Batch independent questions into one call; do not call Jev once per candidate. Use candidate reduction before Jev for sets larger than 20. Record candidate count, batch size, Jev call count, latency, input/output tokens, selected candidates, confidence, and verification result.

Jev may perform advisory reviews of authentication, authorization, schema ownership, production enablement, security, merge, and runner questions when the state contains the relevant evidence. Record verdicts and confidence; a verdict does not grant permissions or replace required source and test evidence. The installed and trusted `jev_gate` PreToolUse hook checks proposed Codex tool actions automatically: only an explicit `deny` blocks, while `allow`, `escalate`, unavailable, and hook failure leave ordinary Codex permissions in force. Hermes Kanban workers use a separate Nerve action gate in selective `block_only` mode. It checks potentially mutating tool calls automatically and blocks only a confident `BLOCK`; other outcomes leave Hermes permissions and card boundaries in force. Never treat either gate as authorization for production, schema, security, or merge decisions.

## Kanban agent policy

Do not create a card for an exact lookup or tiny edit. Use the six profiles for
bounded parallel work only when isolated file scope and acceptance gates make
the second context worthwhile. Prefer `backend` for Go/contracts, `frontend`
for React/TypeScript, `visual` for theme and presentation fixtures,
`reviewer` for independent verification, and `approver` for delegated scope
decisions. `coordinator` owns integration, schema/ownership, security-sensitive,
production, and runner work.

Workers may not expand file scope, infer unknown schema, access production
data, change rulesets, push `main`, or approve their own work. High-risk
security and runner criteria remain coordinator-only.

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
never grants merge, schema, authentication/session, security, production,
runner, credential, real-data, or irreversible-change authority; those stay
coordinator-owned and owner-gated, as do payments, emulator writes, client
handoff, staff operations, rule changes, and branch-protection policy.
Approval of a roadmap proposal permits planning and per-unit card creation only
where the proposal's own text keeps implementation separately gated. Every
implementation unit still needs its own exact base, named paths, evidence,
tests, cap, stop conditions, assignee profile, and independent review, and the
coordinator still merges under its separate reviewed-PR authority.

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

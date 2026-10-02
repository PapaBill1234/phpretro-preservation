# Workflow readiness and delegation draft

Status: saved planning draft. Coding remains supervised and gated; this document does not authorize implementation, merging, or production enablement.

## Confidence

Planning and operating model readiness is approximately 70%. The repository still needs `go.mod`, pinned Go tooling, executable CI, protected branch policy, an approved work-unit batch, and a verified original-source/golden-capture harness. Jev and cost tooling are documented and locally configured, but matched Sol-only versus Jev/Luna efficiency has not yet been measured.

## Phase plan

1. **F0: operational baseline, Sol-owned.** Create `go.mod`, pin Go, establish CI, `govulncheck`, license scanning, tests, and decision caps. Sol writes and reviews the brief because this establishes runner and dependency policy.
2. **F1: evidence extraction, Luna A.** Extract original login behavior, PolarIS schema, password hashes, and capture evidence. Produce cited evidence and explicit `UNKNOWN` values. Luna B independently checks the packet against source.
3. **F2: account/session foundation, Luna A.** Implement only the bounded account/session files. Run focused unit, integration, race, and negative security tests. Luna B independently tests and reviews.
4. **F3: profile read, Luna B.** Implement the schema-proven profile read from a fresh brief. Luna A independently checks behavior and authorization boundaries.
5. **F4: golden-capture harness, Sol plus Luna A.** Sol owns capture semantics and hash rules. Luna A implements the mechanical harness and fixtures. Luna B verifies route coverage, normalization, and hash stability.
6. **F5: one content read, Luna A.** Implement one article/archive read with source evidence, template output, and negative cases. Luna B reviews parity and tests.
7. **F6: one audited mutation, Luna B.** Implement one website-owned write with same-transaction audit behavior and injected audit-failure tests. Sol reviews transaction and authorization design.
8. **F7: staff TOTP, Sol criteria plus Luna implementation.** Sol defines the security contract and replay/expiry cases. Luna A implements; Luna B performs independent negative testing. Production staff operations remain disabled until review passes.
9. **F8: guestbook privacy, Luna B.** Cover owner/friend privacy, direct-ID access, unauthenticated access, and authorization failures.
10. **Release gates.** Fresh install, complete golden suite, vulnerability/license scans, provenance review, independent security review, and measured cost report. Only afterward consider client handoff, registration, payments, emulator writes, or broader feature families.

## Delegation rules

- Sol owns discovery, exact source inspection, schema and ownership decisions, security criteria, work-unit briefs, integration, and final acceptance.
- Luna A implements bounded mechanical or feature units.
- Luna B independently validates, tests, extracts evidence, or implements the next independent unit.
- No two agents edit the same files concurrently.
- Every Luna brief names the base SHA, exact paths, evidence, tests, done criteria, stop conditions, and token cap.
- Jev ranks or classifies facts already gathered. It does not search, design schemas, approve security, or replace review.
- Use one batched Jev call for related questions, include `none of these`, and verify its answer against source.
- Keep tiny lookups and ambiguous or security-sensitive work with Sol. Delegate only when the second context is likely to reduce accepted-unit cost.

## Measurement and stop conditions

For each unit record model IDs, reasoning effort, input/cached/output tokens, retries, Jev calls and latency, wall time, test result, review result, and accepted/parked status. The metric is cost per accepted unit, not raw token count. After ten accepted units, compare matched Sol-only and Jev/Luna units. Stop delegating a unit class if the second context adds cost without lowering accepted-unit cost or improving correctness.

The workflow design is ready for review. Unattended coding is not ready to begin. The first action is F0, followed by an approved batch of F1-F5; feature implementation waits for that baseline and scope approval.

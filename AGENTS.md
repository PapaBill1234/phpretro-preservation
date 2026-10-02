# Agent orchestration

Sol (`gpt-6.1-sol`) is the coordinator and final verifier. Luna subagents use `gpt-6-luna` only for bounded units explicitly approved by Sol.

## Required flow

1. Sol runs exact search, tests, and source inspection first.
2. For broad multi-file or noisy-log work, Sol reduces candidates deterministically and prepares short cited excerpts before asking Jev anything.
3. Sol makes one batched Jev call for related typed rankings/classifications where practical. Jev sees only sanitized candidate IDs and the minimum excerpts needed for the question.
4. Sol verifies every Jev result against source and records the evidence.
5. Sol writes a bounded brief with exact file scope, evidence, tests, done criteria, stop conditions, and an approved token cap.
6. A Luna subagent receives only that approved brief and works within the named scope.
7. Sol reviews the diff and tests before accepting the unit.

## Jev policy

Jev is a typed judgment engine over supplied evidence, not a search engine. It may review source excerpts and high-risk questions when those facts are explicitly included in the state. Include `none of these` when ranking candidates. Accept a low-risk selection only when confidence is at least 0.80 and source verification agrees. Between 0.60 and 0.80, keep the decision with Sol for review. Below 0.60, on `escalate`, on an unavailable response, or on disagreement with source, do not delegate and let Sol decide.

Batch independent questions into one call; do not call Jev once per candidate. Use candidate reduction before Jev for sets larger than 20. Record candidate count, batch size, Jev call count, latency, input/output tokens, selected candidates, confidence, and verification result.

Jev may perform advisory reviews of authentication, authorization, schema ownership, production enablement, security, merge, and runner questions when the state contains the relevant evidence. Verdicts and confidence must be recorded; a verdict does not grant permissions or replace required source and test evidence. The installed `jev_gate` PreToolUse hook is enabled as a safety check for tool actions; `allow`, `escalate`, unavailable, or hook-failure results leave ordinary Codex permissions in force, and only an explicit `deny` blocks the proposed action.

## Delegation policy

Do not create a Luna session for an exact lookup, tiny edit, one-file read, or a task whose expected work cannot repay a second context. Prefer Luna for bounded extraction, mechanical implementation, focused tests, or multi-file work with an explicit acceptance contract. Sol owns ambiguous, security-sensitive, schema/ownership, production, and runner work.

Luna may not expand file scope, infer unknown schema, access production data, change rulesets, push `main`, or approve its own work. High-risk security and runner criteria remain Sol-only.

## Economics

Every measured unit records A6API model IDs, reasoning effort, input tokens, cached-input tokens, output tokens, retries, Jev calls/cost, wall time, result, and acceptance status. Compare matched Sol-only and Jev/Luna runs before claiming savings. If delegation adds a second context without reducing total accepted-unit cost, stop using it for that unit class.

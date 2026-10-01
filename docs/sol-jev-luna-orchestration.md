# Sol, Jev, and Luna orchestration

This repository uses a coordinator-first workflow:

```text
Sol
  -> exact search / tests / source evidence
  -> Jev for a typed ranking or classification
  -> Sol verifies the result
  -> Luna receives only a bounded, approved unit
```

## Model roles

- Sol: `gpt-6.1-sol`, coordinator, evidence reconciler, acceptance-criteria author, diff/test reviewer, and integrator.
- Luna: `gpt-6-luna`, bounded implementation worker in a separate worktree or `auto/*` branch.
- Jev: typed judgment aid through the existing `jev_judge` MCP tool. It ranks or classifies facts already gathered; it does not replace source inspection.

## Delegation gate

Sol delegates only when the unit has a fixed file scope, source evidence, tests, done criteria, stop conditions, and an approved token cap. Ambiguous, security-sensitive, schema/ownership, production, or runner work stays with Sol.

A Jev answer is accepted only after Sol checks it against the relevant source. Low confidence, `escalate`, unavailable Jev, or disagreement with source means Sol decides and records the reason.

## Evidence pattern

For file ranking, run `git grep` or an equivalent exact search first. Send Jev only sanitized candidate IDs and short excerpts needed for the typed question. Include `none of these` where appropriate. Record candidate count, Jev call count, latency, input/output tokens, selected candidates, and the source verification result.

## Cost measurement

Compare matched runs using A6API merchant prices and record input, cached-input, output, retries, wall time, and accepted units. Do not claim savings from a Jev call or model choice without a matched comparison.
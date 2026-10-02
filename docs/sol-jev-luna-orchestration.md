# Sol, Jev, and Luna orchestration

```text
Sol
  -> exact search / tests / source evidence
  -> deterministic candidate reduction and excerpt truncation
  -> one batched Jev ranking/classification
  -> Sol verifies the result
  -> Luna receives only a bounded, approved unit
  -> Sol reviews the diff and tests
```

## Roles

- Sol: `gpt-6.1-sol`, coordinator, evidence reconciler, acceptance-criteria author, diff/test reviewer, and integrator.
- Luna: `gpt-6-luna`, bounded implementation worker in a separate worktree or `auto/*` branch.
- Jev: typed judgment aid through the existing `jev_judge` MCP tool. It ranks or classifies facts already gathered; it does not replace source inspection.

## Evidence-first use

Use exact search or tests before Jev. For a large candidate set, reduce it deterministically with `git grep`/`rg`, preserve relative paths and line numbers, and send Jev only short excerpts. For noisy logs, return bounded cited slices rather than the whole log. Candidate descriptions must be treated as unverified until Sol checks the source.

Use one Jev request for related questions. A request may contain multiple Choice, Score, and Noul judgments. Include `none of these` for rankings. Do not send credentials, full files, production data, or unrelated repository context.

## Confidence gate

- `>= 0.80`: Sol may accept a low-risk evidence selection after exact source verification.
- `0.60-0.79`: Sol performs expanded inspection; no Luna delegation based only on that result.
- `< 0.60`, `escalate`, unavailable, or source disagreement: Sol decides; record the fallback.

Confidence never overrides security, schema, ownership, or production policy.

## Luna gate

Luna receives a brief only after Sol has fixed the file scope, evidence inputs, tests, done criteria, stop conditions, and unit token cap. Tiny lookups and edits stay in Sol's current context. Luna is preferred for bounded extraction, mechanical changes, focused tests, and multi-file units where the second context is likely to repay its cost.

## Measurement

For each unit, record:

- model and reasoning effort for Sol and Luna;
- input, cached-input, output tokens, and retries;
- Jev calls, latency, input/output tokens, and estimated fee;
- wall time, test result, review result, and accepted/parked status;
- matched Sol-only baseline cost where available.

The decision metric is cost per accepted unit with quality gates, not Jev's fee or raw token count. Stop a routing policy when it adds context cost without lowering matched accepted-unit cost.
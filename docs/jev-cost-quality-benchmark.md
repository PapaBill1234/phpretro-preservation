# Jev cost and quality benchmark

Run this before treating routing as a saving. Keep the task set fixed and use the same A6API account, workspace, prompt, model configuration, and acceptance tests.

## Arms

1. Sol-only: exact search, source inspection, and implementation in one coordinator session.
2. Sol + Jev: deterministic candidate reduction, one batched Jev call, Sol verification, no Luna.
3. Sol + Jev + Luna: the same evidence flow, with Luna only for units that pass the delegation gate.

Use at least 20 representative units: exact lookup, bounded extraction, multi-file read, focused test, mechanical edit, and one higher-risk unit that must remain Sol-only. Run each eligible arm at least twice; randomize arm order when practical.

## Record

For every run record model IDs, reasoning effort, input tokens, cached-input tokens, output tokens, retries, Jev call count, Jev latency and estimated fee, wall time, tests, review result, and accepted/parked status. Keep the merchant price sheet or dashboard reading used for the calculation with the run record, without storing credentials.

## Decisions

Compute cost per accepted unit and quality pass rate. Keep Jev for a task class only if it lowers matched accepted-unit cost without lowering the required quality gate. Keep Luna only if the second context is repaid by reduced coordinator work. Do not generalize from one code fix or from public benchmark prices.
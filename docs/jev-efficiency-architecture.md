# Jev efficiency architecture

This is the recommended Jev operating model for the rewrite. It is an optimization plan, not permission to bypass Sol's review or the repository's security and ownership gates.

## What the current setup already does well

- Jev is available through the MCP judge with typed `Choice`, `Score`, and `Noul` questions.
- The installed `jev-use` PreToolUse hook provides a fast risk check for tool actions without an LLM supervisor call. It is a safety layer, not a permission system or a demonstrated cost-saving mechanism.
- The project policy supplies exact search results and source excerpts to Jev for evidence and high-risk review; verdicts are recorded with confidence and risk tier.
- Luna receives bounded briefs and cannot expand scope or approve its own work.
- Cost and quality fields are defined for each accepted work unit.

## Highest-value operating loop

1. Run deterministic search, tests, and parsing first. Reduce large candidate sets and logs to short excerpts with paths and line references.
2. Build one small JSON state for the unit. Ask related typed questions together: candidate or failure ranking, evidence sufficiency, risk class, and whether the unit is eligible for Luna.
3. Route by both confidence and risk. A low-risk selection needs confidence at least `0.80` and source agreement. Results from `0.60` to `0.79` require expanded Sol review. Lower confidence, escalation, unavailable output, or source disagreement stays with Sol.
4. Preserve provenance. Every selected candidate keeps its source path, line or test reference, and the evidence used to verify it.
5. Send Luna only an approved bounded brief. The brief contains the base SHA, exact paths, evidence, tests, done criteria, stop conditions, and token cap.
6. Sol reviews the diff, tests, and scope, then records accepted or parked status.

## Additional Jev uses worth adding

- Triage changed files into implementation, test, documentation, security, or review categories before preparing a brief.
- Rank likely causes from a bounded test-failure excerpt before Sol investigates.
- Select the smallest relevant evidence packet for a work unit, then verify the selected citations against source.
- Score review completeness and classify likely scope violations after Luna reports.
- Use hierarchical classification for large inventories: deterministic grouping first, then Jev within each group.
- Cache a judgment only when the source excerpts, policy version, candidate set, and unit state are unchanged. Invalidate on any of those changes.

These uses reduce context and triage work. High-risk packets are marked and routed as `jev_high_risk_review`; low-confidence or escalated results still return to Sol. Jev reviews only the evidence supplied in the packet and cannot discover omitted facts.

## Efficiency test before expansion

Run matched work units in three arms: Sol-only, Sol plus one batched Jev call, and Sol plus Jev plus bounded Luna. Use the same model configuration, task class, acceptance tests, and A6API account. Measure input, cached-input, output, retries, Jev calls and latency, estimated Jev fee, wall time, correctness, review effort, and cost per accepted unit. Keep a pattern only when its accepted-unit economics improve without reducing quality. Public Jev benchmarks and a Jev call by itself are not evidence of savings for this repository.

## Runner

Use `scripts/jev-work-unit.mjs` with a sanitized packet containing `unit_id`, short cited `state`, typed questions, and optional `source_refs`. The runner hashes the policy, state, and questions; reuses an exact cached verdict; otherwise makes one batched CLI call and appends a JSONL record. Any low-confidence or escalated answer routes to `sol_review`; the runner never authorizes delegation by itself.

## Current assessment

The installed judge capability is sound but not maximally exploited. The largest unmeasured opportunities are prefiltering and reranking before Sol reads context, batched multi-question triage, provenance-aware review packets, and reuse of unchanged judgments. The next concrete step is a small matched benchmark; enabling the safety hook does not replace that measurement.

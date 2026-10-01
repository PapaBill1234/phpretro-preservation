# Jev, cost, and agent operations

## Jev boundary

Use `mcp__jev__jev_judge` only for typed judgments over facts already gathered: candidate ranking, log classification, delegation routing, diff triage, plausible-cause ranking, and claim checks. Sol performs exact search and source inspection first, batches related questions, supplies short sanitized excerpts, includes `none of these`, and verifies every result against source. Jev must not decide authentication, authorization, schema ownership, production enablement, security approval, merge approval, or runner permissions.

Accept a low-risk Jev selection only at confidence `>= 0.80` when source verification agrees. Between `0.60` and `0.80`, Sol reviews. Below `0.60`, on `escalate`, unavailable output, or disagreement, Sol decides and delegation stops. Keep credentials, personal data, full files, and unrelated context out of calls.

## Sol and Luna handoff

Sol (`gpt-6.1-sol`) owns discovery, ambiguous decisions, security-sensitive criteria, schema/ownership, runner configuration, acceptance briefs, and final verification. Luna A and Luna B (`gpt-6-luna`) receive only a bounded brief naming base SHA, exact file scope, evidence, tests, done criteria, stop conditions, and token cap. They work in separate worktrees, make no scope expansion, and report commit, diffstat, tests, and unresolved questions. Sol reviews before acceptance; a child never approves its own work.

## Cost evidence

The repository-side collector is `scripts/a6api-dashboard-auto.user.js`; PowerShell collection and summaries are `scripts/collect-a6api-dashboard.ps1`, `scripts/record-a6api-export.ps1`, `scripts/a6api-cost-report.ps1`, and `scripts/summarize-a6api-archive.ps1` in the preservation tooling checkout. Copy the scripts into this repository only when their paths and tests are reviewed. The authoritative raw export is JSONL; backups are retained. Record model ID, reasoning effort, input, cached-input, output, retries, Jev calls/cost, wall time, result, and acceptance status per unit.

Do not claim savings from a Jev call or cache-hit percentage alone. After ten accepted units, compare matched Sol-only and Jev/Luna cohorts using the same task class and report cost per accepted unit, tokens, time, retries, and correctness.

## Go security scan

Every Go CI job must run `govulncheck ./...` against the pinned toolchain and module graph, fail on an actionable vulnerability, and retain the scan output as an artifact. Run dependency/license inventory separately; a clean vulnerability scan does not establish license compatibility. Dependabot or equivalent update alerts may supplement `govulncheck`, but neither replaces source review and the plan's decision gates.

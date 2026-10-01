# Decisions

- **Coordinator:** `gpt-6.1-sol` through A6API. Verify the active Codex profile before cost comparisons; a configuration showing `gpt-6-sol` is a mismatch requiring correction.
- **Subagents:** `gpt-6-luna` through A6API for bounded, Sol-approved units only.
- **Jev:** use the existing `jev_judge` MCP tool for typed rankings/classifications over facts already found; batch related questions; `jev_gate` remains disabled.
- **Evidence:** deterministic search/reduction precedes Jev for broad multi-file and noisy-log tasks. Jev receives sanitized candidate IDs and bounded excerpts only.
- **Confidence:** 0.80 permits a verified low-risk selection; 0.60-0.79 requires expanded Sol review; below 0.60, escalation, unavailable Jev, or source disagreement falls back to Sol.
- **Delegation:** no Luna for exact lookups or tiny edits; delegate only bounded units whose expected work can repay a second context.
- **Authority:** Sol verifies every Jev result against source before delegation or acceptance. Jev and Luna never make final authentication, authorization, schema ownership, production enablement, merge, or runner-security decisions.
- **Economics:** record A6API usage and compare matched Sol-only versus Jev/Luna runs by cost per accepted unit before claiming savings.
- **Foundation status:** supervised only until repository policy, queue, token caps, and evidence transfer are approved.
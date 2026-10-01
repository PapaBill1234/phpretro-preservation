# Decisions

- **Coordinator:** `gpt-6.1-sol` through A6API.
- **Subagents:** `gpt-6-luna` through A6API for bounded, Sol-approved units only.
- **Jev:** use the existing `jev_judge` MCP tool for typed rankings/classifications over facts already found; `jev_gate` remains disabled.
- **Authority:** Sol verifies every Jev result against source before delegation or acceptance.
- **Security boundary:** Jev and Luna never make final authentication, authorization, schema ownership, production enablement, merge, or runner-security decisions.
- **Foundation status:** supervised only until repository policy, queue, token caps, and evidence transfer are approved.
- **Cost evidence:** merchant prices and matched token measurements are required before claiming savings.
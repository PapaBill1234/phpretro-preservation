# Agent orchestration

Sol (`gpt-6.1-sol`) is the coordinator and final verifier. Luna subagents use `gpt-6-luna` only for bounded units explicitly approved by Sol.

## Required flow

1. Sol gathers exact search, test, and source evidence.
2. Sol may call Jev for a typed ranking or classification over already-found facts. Jev is not a source of undiscovered facts.
3. Sol verifies Jev's result against the source and records the evidence.
4. Sol writes a bounded brief with exact file scope, evidence, tests, done criteria, and stop conditions.
5. A Luna subagent receives only that approved brief and works within the named scope.
6. Sol reviews the diff and tests before accepting the unit.

Jev must not decide authentication, authorization, schema ownership, production enablement, security approval, or merge approval. A Jev error, low-confidence result, or unverifiable result returns control to Sol.

Luna may not expand file scope, infer unknown schema, access production data, change rulesets, push `main`, or approve its own work. High-risk security and runner criteria remain Sol-only.
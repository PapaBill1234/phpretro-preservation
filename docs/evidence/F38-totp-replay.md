# F38 TOTP replay evidence

Evidence source: docs/roadmap/F31-F45-candidate-design.md, F38 row (synthetic-only).

The source states that a previously accepted TOTP time step must not be accepted
again for the same staff identity, including concurrent submissions, and that
replay state must be durable rather than cache-only. It also names adjacent
allowed steps, expiry, wrong staff, outage, and atomic compare/update as
negative or boundary concerns.

No production staff schema, replay table, lock model, or retained TOTP capture
was supplied. The implementation and tests therefore use a synthetic,
file-backed store and mark fidelity as guessed. Independent security review is
required before any production use.

# Current AI run state

This is the active state for the Go PHPRetro preservation rewrite. The old C++/Drogon plan-v4 continuation note is archived at [`docs/archive/cpp-modular-cms-history.md`](archive/cpp-modular-cms-history.md) and is not permission to resume.

- **active unit:** none; F1 is parked pending source-pin resolution
- **status:** F1 evidence extracted and merged; implementation stopped
- **allowed scope:** no active implementation scope; F1 evidence is in `docs/evidence/F1-password-scheme.md`
- **blocked:** F2 account/session, F3 profile, F4 golden harness, and F5 content read until the exact original source pin and PolarIS verifier evidence are accepted
- **deferred:** production registration, payments, emulator writes, client handoff, staff operations, Pixel63, Atom, Redis/nginx/metrics/fuzzing, and SWF; these require later owner decisions
- **delegation:** Sol inspects source and schema first; Luna is considered only for a bounded extraction after deterministic evidence reduction; Jev sees sanitized supplied evidence only and never grants permission
- **stop conditions:** guessed schema/hash scheme, missing source evidence, real user data, secret detection, payment/quota/auth failure, or a second failed attempt
- **last boundary:** F1 evidence merged in PR #5 at `ff714ca2e2c2e9bc3a00a1dc9602b84dd36a8f2f`; no Luna delegation; Jev escalated unavailable backend and its result was not used

No implementation unit may start until the F1 source-pin UNKNOWN is resolved and Sol accepts the evidence gate.

# Supervised work queue

No implementation unit is currently ready. F1 and F2 are accepted; F3 requires its own bounded evidence and scope approval. No production scope is approved.

| ID | Status | Unit | Exact scope | Reason |
| --- | --- | --- | --- | --- |
| F0 | accepted | Repository and CI baseline | Historical F0 foundation files | CI baseline passed and was accepted before this queue. |
| F1 | accepted | PolarIS password-scheme evidence | `docs/evidence/**`, `tasks/F1.md` | Pinned original source and PolarIS emulator verifier evidence are recorded; runtime row contents remain an explicit follow-up UNKNOWN. |
| F2 | accepted | Account/session contract | `internal/account/**`, `internal/session/**`, `tests/**`, `docs/evidence/**` | Contract implementation and tests merged; PolarIS BCrypt/$2y verifier is source-backed. Runtime row contents remain UNKNOWN and are tracked as follow-up evidence. |
| F3 | ready | Profile read | `internal/profile/**`, `docs/evidence/F3-profile-schema.md`, `tasks/F3.md` | Source-backed profile schema and read contract are recorded; implementation awaits scope-boundary commit. |
| F4 | ready | Golden harness | `tests/golden/**`, `docs/evidence/F4-golden-harness.md`, `tasks/F4.md` | F1-F3 evidence and profile contract are accepted; capture hashes and runtime digests are recorded. |
| F5 | blocked | Content read | No files approved | Requires prior accepted foundation units. |
| F6+ | deferred | Later features and production gates | No files approved | Later owner decisions; deferred gates remain closed. |

Every unit brief must state its base SHA, exact allowed paths, evidence, tests, acceptance criteria, stop conditions, and token cap. Any security, schema, production, or runner decision stays with Sol.

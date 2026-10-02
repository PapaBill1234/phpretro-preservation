# Supervised work queue

F0-F5 are accepted foundation units. No production scope is approved.

| ID | Status | Unit | Exact scope | Reason |
| --- | --- | --- | --- | --- |
| F0 | accepted | Repository and CI baseline | Historical F0 foundation files | CI baseline passed and was accepted before this queue. |
| F1 | accepted | PolarIS password-scheme evidence | `docs/evidence/**`, `tasks/F1.md` | Pinned original source and PolarIS emulator verifier evidence are recorded; runtime row contents remain an explicit follow-up UNKNOWN. |
| F2 | accepted | Account/session contract | `internal/account/**`, `internal/session/**`, `tests/**`, `docs/evidence/**` | Contract implementation and tests merged; PolarIS BCrypt/$2y verifier is source-backed. Runtime row contents remain UNKNOWN and are tracked as follow-up evidence. |
| F3 | accepted | Profile read | `internal/profile/**`, `docs/evidence/F3-profile-schema.md`, `tasks/F3.md` | Source-backed schema, bounded read contract, synthetic tests, and PR #14 merge at `fc4949c` are accepted. |
| F4 | accepted | Golden harness | `tests/golden/**`, `docs/evidence/F4-golden-harness.md`, `tasks/F4.md` | Capture hashes/digests, deterministic comparator, synthetic mismatch tests, and PR #16 merge at `294dfd1` are accepted. |
| F5 | accepted | Content read | `internal/content/**`, `docs/evidence/F5-content-schema.md`, `tasks/F5.md` | Source-backed hotelview_news contract, synthetic enum/cap tests, and PR #18 merge at `42aa39b` are accepted. |
| F6+ | deferred | Later features and production gates | No files approved | Later owner decisions; deferred gates remain closed. |

Every unit brief must state its base SHA, exact allowed paths, evidence, tests, acceptance criteria, stop conditions, and token cap. Any security, schema, production, or runner decision stays with Sol.

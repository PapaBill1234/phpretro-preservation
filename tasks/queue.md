# Supervised work queue

F0-F7 are accepted foundation units. F8 is active through the durable Hermes
Kanban board `phpretro-preservation`; no production scope is approved.

| ID | Status | Unit | Exact scope | Reason |
| --- | --- | --- | --- | --- |
| F0 | accepted | Repository and CI baseline | Historical F0 foundation files | CI baseline passed and was accepted before this queue. |
| F1 | accepted | PolarIS password-scheme evidence | `docs/evidence/**`, `tasks/F1.md` | Pinned original source and PolarIS emulator verifier evidence are recorded; runtime row contents remain an explicit follow-up UNKNOWN. |
| F2 | accepted | Account/session contract | `internal/account/**`, `internal/session/**`, `tests/**`, `docs/evidence/**` | Contract implementation and tests merged; PolarIS BCrypt/$2y verifier is source-backed. Runtime row contents remain UNKNOWN and are tracked as follow-up evidence. |
| F3 | accepted | Profile read | `internal/profile/**`, `docs/evidence/F3-profile-schema.md`, `tasks/F3.md` | Source-backed schema, bounded read contract, synthetic tests, and PR #14 merge at `fc4949c` are accepted. |
| F4 | accepted | Golden harness | `tests/golden/**`, `docs/evidence/F4-golden-harness.md`, `tasks/F4.md` | Capture hashes/digests, deterministic comparator, synthetic mismatch tests, and PR #16 merge at `294dfd1` are accepted. |
| F5 | accepted | Content read | `internal/content/**`, `docs/evidence/F5-content-schema.md`, `tasks/F5.md` | Source-backed hotelview_news contract, synthetic enum/cap tests, and PR #18 merge at `42aa39b` are accepted. |
| F6 | accepted | PolarIS adapter boundary | `internal/polaris/**`, evidence, tests | Synthetic/read-only adapter boundary is merged on `main`. |
| F7 | accepted | React and Redis boundary | `frontend/**`, `internal/cache/**`, evidence, tests | Synthetic React/theme and injected cache support are merged on `main`. |
| F8 | active | Localization contract | `frontend/src/localization/**`, `frontend/tests/localization.test.ts`, `internal/localization/**`, locale-varying `internal/cache/**`, evidence, `tasks/F8.md` | Kanban-dispatched synthetic-only slice; no production CMS or credentials. |
| F9+ | deferred | Later features and production gates | No files approved | Later owner decisions; deferred gates remain closed. |

Every unit brief must state its accepted integration base SHA, exact allowed paths, evidence, tests, acceptance criteria, stop conditions, token cap, assignee profile, and worktree boundary. A card may not be dispatched from a worktree-only or stale base. Any security, schema, production, or runner decision stays with the coordinator. Coordinator cards must leave successor cards queued before completion or document why the authorized queue is stopped.

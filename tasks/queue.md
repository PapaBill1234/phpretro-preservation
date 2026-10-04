# Supervised work queue

F0-F7 are accepted foundation units. The F8 localization boundary, F14
evidence/test candidate, and F15 public-route evidence/test slice are on `main`
through PR #26. The user authorized successive source-backed first-release
route evidence and synthetic tests, with no production behavior or schema
changes. The durable Hermes Kanban board is `phpretro-preservation`.

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
| F8 | merged boundary | Localization contract | `frontend/src/localization/**`, `frontend/tests/localization.test.ts`, `internal/localization/**`, locale-varying `internal/cache/**`, evidence, `tasks/F8.md` | Synthetic boundary is on `main` at `031a336`; F14 evidence/tests were later delivered. |
| F14 | delivered | Localization evidence and tests | The seven exact evidence/test paths in PR #24 | Candidate `cdab34c` passed independent retry `t_0f7c80e0`, pinned Go matrix, and foundation CI; PR #24 merged at `c522930`. No production changes. |
| F15 | delivered | First-release public `GET /` route evidence and synthetic tests | `tasks/F15.md`, `docs/evidence/F15-public-route.md`, `tests/golden/public_route_test.go` | Independently accepted candidate `650ba41` was delivered by PR #26 at `f60470b`; unavailable response metadata remains explicit in the F15 record. |
| F16 | authorized next | Public `GET /login_popup.php` route evidence and synthetic tests | `tasks/F16.md`, `docs/evidence/F16-public-login.md`, `tests/golden/login_route_test.go` | The retained disposable capture's 7,940-byte body matches accepted F4 login hash `500ebc4`; retained headers show final 200, no Location/Set-Cookie, and `text/html; charset=UTF-8`. Original `login_popup.php` matches the source manifest. Verify local raw files and hashes before assertions; no auth/session implementation, production behavior, schema, real data, or credential changes. |
| F17+ route evidence | conditionally authorized | Successive source-backed first-release route evidence and synthetic tests | Each new brief must name exact evidence/test paths and an accepted base SHA before dispatch | Continue only while fresh exact source and capture evidence support a bounded unit; create a reviewer and successor coordinator card or record the hard dependency. |
| F9+ implementation | deferred | Later features and production gates | No product or schema files approved by this queue | Feature, CMS mutation, production, security, and runner gates remain closed. |

Every unit brief must state its base SHA, exact allowed paths, evidence, tests, acceptance criteria, stop conditions, token cap, assignee profile, and worktree boundary. Any security, schema, production, or runner decision stays with the coordinator. Coordinator cards must leave successor cards queued before completion or document why the authorized queue is stopped.

F16 and its successors are evidence/test-only authorization. Do not turn the
historical F9-F14 identifiers into permission for their deferred implementation
work. Stop and record the missing source or capture when a route cannot be
specified without guessing.

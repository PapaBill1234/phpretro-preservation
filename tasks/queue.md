# Supervised work queue

F0-F7 are accepted foundation units. The F8 localization boundary, F14
evidence/tests, and F15-F17 public-route evidence/synthetic-test slices are on
`main` through PR #30 at `b398da5aa65e7835689e1e9166bff3b7173d06f3`.
The user authorized successive source-backed first-release
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
| F16 | delivered | Public `GET /login_popup.php` route evidence and synthetic tests | `tasks/F16.md`, `docs/evidence/F16-public-login.md`, `tests/golden/login_route_test.go` | Reviewed candidate `8fb3b10a2153cbd9198de533a04fb82b5ea76242` was delivered by PR #29 at `0e3721c857e5d2e069c7b2c9ed07eb84e88f170b`. The retained disposable capture's 7,940-byte body matches accepted F4 login hash `500ebc4`; retained headers show final 200, no Location/Set-Cookie, and `text/html; charset=UTF-8`. Original `login_popup.php` matches the source manifest. No auth/session implementation, production behavior, schema, real data, or credential changes. |
| F17 | delivered | Public `GET /articles/archive` route evidence and synthetic tests | `tasks/F17.md`, `docs/evidence/F17-public-archive.md`, `tests/golden/archive_route_test.go` | Exact candidate `9cf13c75dae8028d53096493e619e91625034c48` received explicit independent ACCEPTED review from `t_510fc369`; PR #30 delivered it at `b398da5aa65e7835689e1e9166bff3b7173d06f3` after exact-head foundation run `37220609598` succeeded. Evidence/synthetic tests only; all recorded UNKNOWNs remain. |
| Successive route evidence | authorized boundary; hard stop | Further distinct source-backed first-release route evidence and synthetic tests | Each new brief must name exact evidence/test paths and an accepted base SHA before dispatch; no next F number selected | Existing checkpoint `t_aed9f2eb` found no distinct retained response authority for the inspected help/tag/groups/discussions routes. Exact source alone cannot establish response method/status/headers/cookies/markers; dispatch no next unit until both exact source and retained response authority support it. |
| F18-F30 proposal | owner approval pending; no implementation authorization | Separate scope-approval lane | `docs/roadmap/F18-F30-feature-approval.md` under `t_a0d1b1de` / `t_d77c8293` | Proposal correctness review is not owner scope approval. Explicit owner approval on the scope PR and required delivery gates remain prerequisites; no Batch A implementation dispatch. |
| F31-F60 design | provisional design only | Separate design-document delivery lane | Three roadmap documents under `t_ed119ebc` | Design review/delivery does not approve feature scope or implementation and does not override the F18-F30 owner gate. |
| F9+ implementation | deferred | Later features and production gates | No product or schema files approved by this queue | Feature, CMS mutation, production, security, and runner gates remain closed. |

Every unit brief must state its base SHA, exact allowed paths, evidence, tests, acceptance criteria, stop conditions, token cap, assignee profile, and worktree boundary. Any security, schema, production, or runner decision stays with the coordinator. Coordinator cards must leave successor cards queued before completion or document why the authorized queue is stopped.

F16 and its successors are evidence/test-only authorization. Do not turn the
historical F9-F14 identifiers into permission for their deferred implementation
work. Stop and record the missing source or capture when a route cannot be
specified without guessing.

The evidence lane's missing-capture stop is separate from the proposal lane's
owner gate. Reuse `t_aed9f2eb`; do not duplicate the planner/proposal, acquire
new captures, or select another F number as part of this reconciliation.
F17's CMS `news` schema, row provenance/content, runtime/database semantics
beyond the captured response, request-cookie/session provenance, and uncited
or unobserved behavior remain UNKNOWN. Raw captures remain local. Neither
lane grants product, schema, authentication/session, security, runner,
production, credential, or real-data approval.

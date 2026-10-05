# Supervised work queue

F0-F7 are accepted foundation units. The F8 localization boundary, F14
evidence/tests, and F15-F17 public-route evidence/synthetic-test slices are on
`main` through PR #30 at `b398da5aa65e7835689e1e9166bff3b7173d06f3`.
The historical route-evidence authorization covered successive source-backed
first-release evidence and synthetic tests, not schema or product changes.
The development-only F18-F30 authorization below is a separate bounded lane.
The durable Hermes Kanban board is `phpretro-preservation`.

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
| F14 | delivered | Localization evidence and tests | The seven exact evidence/test paths in PR #24 | Candidate `cdab34c` passed independent retry `t_0f7c80e0`, pinned Go matrix, and foundation CI; PR #24 merged at `c522930`. Evidence and tests only. |
| F15 | delivered | First-release public `GET /` route evidence and synthetic tests | `tasks/F15.md`, `docs/evidence/F15-public-route.md`, `tests/golden/public_route_test.go` | Independently accepted candidate `650ba41` was delivered by PR #26 at `f60470b`; unavailable response metadata remains explicit in the F15 record. |
| F16 | delivered | Public `GET /login_popup.php` route evidence and synthetic tests | `tasks/F16.md`, `docs/evidence/F16-public-login.md`, `tests/golden/login_route_test.go` | Reviewed candidate `8fb3b10a2153cbd9198de533a04fb82b5ea76242` was delivered by PR #29 at `0e3721c857e5d2e069c7b2c9ed07eb84e88f170b`. The retained disposable capture's 7,940-byte body matches accepted F4 login hash `500ebc4`; retained headers show final 200, no Location/Set-Cookie, and `text/html; charset=UTF-8`. Original `login_popup.php` matches the source manifest. No auth/session implementation, schema, real data, or credential changes. |
| F17 | delivered | Public `GET /articles/archive` route evidence and synthetic tests | `tasks/F17.md`, `docs/evidence/F17-public-archive.md`, `tests/golden/archive_route_test.go` | Exact candidate `9cf13c75dae8028d53096493e619e91625034c48` received explicit independent ACCEPTED review from `t_510fc369`; PR #30 delivered it at `b398da5aa65e7835689e1e9166bff3b7173d06f3` after exact-head foundation run `37220609598` succeeded. Evidence/synthetic tests only; all recorded UNKNOWNs remain. |
| Successive route evidence | retained-capture fidelity limit | Further distinct source-backed first-release route evidence and synthetic tests | Each new brief names exact evidence/test paths and an accepted base SHA; capture claims require retained authority | Checkpoint `t_aed9f2eb` found no distinct retained response authority for inspected help/tag/groups/discussions routes. Exact source alone cannot establish response method/status/headers/cookies/markers. These remain UNKNOWN; independent bounded fixture units may proceed with labelled fidelity limits, not invented capture claims. |
| F18-F30 development | eligible; exact-unit gates required | Separate bounded development lane | Proposal history: `docs/roadmap/F18-F30-feature-approval.md` under `t_a0d1b1de` / `t_d77c8293`; each implementation card declares its own exact paths | The 2026-10-04 owner decision opens planning and implementation in dependency order, one unit at a time, including Batch B without separate owner expansion. Delegated scope decisions, independent review, CI and coordinator delivery gates remain required; no owner approval or capture-stop prerequisite for independent fixture units. |
| F31-F60 design | provisional design only | Separate design-document delivery lane | Three roadmap documents under `t_ed119ebc` | Design review/delivery does not approve feature scope or implementation. F18-F30 eligibility does not promote F31-F60. |
| Historical F9+ implementation | no blanket authorization | Older deferred implementations and remaining technical gates | Historical evidence/test identifiers grant no arbitrary product or schema path scope | F18-F30 development eligibility is separate and requires exact-unit briefs. Real credentials/key material, real user data and live outside systems remain closed, and there is no production gate; security, schema ownership and runner decisions remain coordinator-owned. |

Every unit brief must state its base SHA, exact allowed paths, evidence, tests, acceptance criteria, stop conditions, token cap, assignee profile, and worktree boundary. Any security, schema, or runner decision stays with the coordinator. Coordinator cards must leave successor cards queued before completion or document why the authorized queue is stopped.

## Owner standing instruction, 2026-10-04

This is a development-only project: no production deployment, no real user
data, no payments, all work against synthetic or disposable data. The former
closed list (authentication, sessions, cookies, CSRF, audit-event design,
schema and migrations, and the units that depend on them) is open for
development use. There is no production environment and no production gate, and
nothing here defers to a future production decision.

F18-F30 are all eligible and are built in dependency order, one unit at a time,
each with exact paths, tests, a cost cap, and an independent reviewer. Batch B
needs no separate owner expansion. Each unit is capped at 3,000,000 tokens
across all gates.

Report here, not to the owner: on every unit start, finish, or cut-down, write
one short plain-English line naming the unit, its outcome, and token usage per
gate. Never wait on the owner; repair blocked cards instead of reporting them.

The historical F16 route-evidence grant and its successors authorize evidence
and tests only. Do not turn the
historical F9-F14 identifiers into permission for their deferred implementation
work. Record missing source or captures as UNKNOWN; build only separately
bounded disposable fixtures with labelled fidelity limits where authorized.

The retained-capture checkpoint is a fidelity note, not a development dispatch
stop or owner gate. Reuse `t_aed9f2eb`; do not duplicate the planner/proposal or
acquire new captures as part of this reconciliation. Independent fixture-based
F18-F30 units remain eligible under their own exact briefs and normal gates.
F17's CMS `news` schema, row provenance/content, runtime/database semantics
beyond the captured response, request-cookie/session provenance, and uncited
or unobserved behavior remain UNKNOWN. Raw captures remain local. Historical
evidence authorization grants no product implementation scope. The separate
development-only decision opens authentication/session and schema work under
exact-unit gates, not real credentials, real data or live systems;
coordinator security, schema ownership, runner and merge authority is retained.

PR35 correction finished: production removed as a closed item and as a gate from
AGENTS.md, DECISIONS.md, CHANGELOG.md and this queue; the closed list is now
exactly real credentials/secrets/key material, real user data, live outside
systems, merge itself, and any weakening of review, CI, branch-protection or
approval rules. Correction, review, approval and CI token usage per gate
unavailable (not measured).

F18 profile read/presentation model (t_25ca3e24) started on base
2df409465458fbd6df273d6ba535b79209149eaf: new read-only
internal/profile/view.go and view_test.go implement Tab 1-5 selection with
absent or invalid input falling back to 1, preserving the six-field F3
Profile; token usage per gate unavailable (not measured) in this worker
session.

F18 profile read/presentation model (t_25ca3e24) finished: focused
go test/vet ./internal/profile/... and gofmt -l internal/profile clean under
Go 1.25.13, full go test ./... green, changed paths exactly
internal/profile/view.go, internal/profile/view_test.go and this status
line; go test -race ./... unverified locally (no C compiler for cgo) and left
to CI; token usage per gate unavailable (not measured).

F18 profile read/presentation model delivered: PR #39 merged normally at
7b3f47cb4bb31a0a20d8c4c1dc32778ce9889b97 from reviewed head dd2e33c; exact-head
foundation CI passed including race and govulncheck; token usage per gate
unavailable (not measured).

F19 personal-home read/presentation model finished locally at f8cc6364caf9133993c1028a3342a46d2b484ae1: synthetic guest ID/name lookup and explicit hidden-home boundary, with unknown private fields omitted; token usage per gate unavailable (not measured). Go and frontend focused/full gates are unavailable locally (gofmt/go/npm dependencies missing); exact-head CI and independent review remain required.

F19-F24 code-wave reconciliation (2026-10-05): PR #45 F20 account read model merged normally at 75d8a3e76d0acc893cc086631e937b88816ce284 from exact head a2ace870d3bd42c13c3a34b0ed631686a6317d5f; focused Go test, vet, and gofmt passed locally under Go 1.25.13 and foundation CI passed. PRs #46, #47, and #48 remained open after PR #45 advanced main and made their exact heads behind; their prior foundation CI was green and focused local Go/frontend checks passed, but current-head CI was not rerun and normal merge was correctly refused. PR #44 and #49 remained open: exact-head foundation CI failed gofmt, and both also changed out-of-envelope frontend profile paths; no merge attempted. Token usage per gate unavailable (not measured).

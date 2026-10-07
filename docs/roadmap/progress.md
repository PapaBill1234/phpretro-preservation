# Progress against the approved roadmap

Snapshot: 2026-10-07T00:53:09Z.

Git delivery and runtime status are reported separately from implementation. Product scaffolds remain scaffolds even when their synthetic acceptance tests pass. Infrastructure utility completion does not count as a completed product feature.

Counts include canonical roadmap cards only. Split, quality and refactor units appear below but do not inflate the roadmap denominator. Platform obligations are overlapping summaries, not additional cards.

| Area | Not started | Designed | Scaffold | Implemented | Verified |
|---|---:|---:|---:|---:|---:|
| legacy preserved behavior | 0 | 5 | 14 | 0 | 0 |
| Redis | 0 | 1 | 0 | 0 | 0 |
| Go backend | 0 | 8 | 2 | 0 | 0 |
| React frontend | 0 | 8 | 1 | 0 | 0 |
| themes: Habbo | 0 | 0 | 0 | 0 | 0 |
| themes: Atom CMS | 0 | 0 | 0 | 0 | 0 |
| themes: theme system | 0 | 3 | 2 | 0 | 0 |
| Polaris integration | 0 | 0 | 1 | 0 | 0 |
| staff | 0 | 3 | 3 | 0 | 0 |
| infrastructure | 0 | 3 | 0 | 2 | 0 |

## Approved platform obligations

| Area | Classification | Written authority | Observed boundary |
|---|---|---|---|
| Go backend | scaffold | AGENTS.md:3 | Go HTTP server exists but its feature handlers use synthetic data. |
| React frontend | scaffold | DECISIONS.md:23 | React renders fixed DemoUser models; no intended backend API wiring. |
| Redis | designed | DECISIONS.md:23 | Required supporting service is specified; only RedisLike/Memory boundary exists. |
| Polaris integration | scaffold | docs/evidence/F6-polaris-read-adapter.md:7 | SQL read adapters are tested with a fake driver but not connected to server.New. |
| themes: theme system | scaffold | DECISIONS.md:23 | theme.v1 validates presentation capability; versioned installed theme packages are incomplete. |
| themes: Habbo | not started | docs/decisions/2026-10-07-maintenance-B.md:3 | Approved theme remains in scope; concrete named-theme asset/render acceptance is unwritten. |
| themes: Atom CMS | not started | docs/decisions/2026-10-07-maintenance-B.md:3 | Approved Atom theme remains in scope; no Atom package or written visual acceptance exists. |

## Unit delivery and assessment

| Unit | Area | Canonical / runtime / Git | Classification | Evidence / limitation |
|---|---|---|---|---|
| F0 | infrastructure | merged / merged / merged | implemented | Executable Go/CI foundation exists; infrastructure utility, not product completion. `go.mod:1`, `cmd/phpretro/main.go:1` |
| F1 | infrastructure | merged / merged / merged | designed | Evidence document delivery; no product implementation claim. `docs/evidence/F1-password-scheme.md:1` |
| F2 | Go backend | merged / merged / merged | scaffold | Contract helper and synthetic tests exist; intended backend/HTTP integration is incomplete. `internal/account/account.go:1`, `internal/account/account_test.go:1`, `internal/session/session.go:1`, `internal/server/server.go:1` |
| F3 | legacy preserved behavior | merged / merged / merged | scaffold | Contract helper and synthetic tests exist; intended backend/HTTP integration is incomplete. `internal/profile/profile.go:1`, `internal/profile/profile_test.go:1`, `internal/server/fixtures.go:1` |
| F4 | infrastructure | merged / merged / merged | implemented | Deterministic comparator utility uses its real implementation; synthetic inputs are its intended contract, not a product datastore. `tests/golden/golden_test.go:1`, `tests/golden/golden.go:1` |
| F5 | legacy preserved behavior | merged / merged / merged | scaffold | Contract helper and synthetic tests exist; intended backend/HTTP integration is incomplete. `internal/content/content.go:1`, `internal/content/content_test.go:1`, `internal/polaris/store.go:1` |
| F6 | Polaris integration | merged / merged / merged | scaffold | Bound SQL read adapters exist but server.New does not wire them to the intended MariaDB backend. `internal/polaris/store.go:1`, `internal/polaris/store_test.go:1`, `internal/server/server.go:1` |
| F7 | themes: theme system | merged / merged / merged | scaffold | Typed presentation and RedisLike boundaries exist; only StarterShell and memory cache double, not backend integration. `frontend/src/themeManifest.ts:1`, `frontend/src/StarterShell.tsx:1`, `internal/cache/cache.go:1` |
| F8 | React frontend | merged / merged / merged | scaffold | Data-only localization helpers exist with synthetic catalogs and a cache double. `internal/localization/localization.go:1`, `frontend/src/localization/index.ts:1`, `internal/cache/cache.go:1` |
| F14 | React frontend | merged / merged / merged | designed | Evidence/test-only delivery; no product change. `docs/evidence/F14-visual-localization.md:1`, `frontend/tests/visual-localization.test.ts:1` |
| F15 | legacy preserved behavior | merged / merged / merged | designed | Synthetic route evidence tests do not implement a preserved route. `tests/golden/public_route_test.go:1`, `docs/evidence/F15-public-route.md:1` |
| F16 | legacy preserved behavior | merged / merged / merged | designed | Evidence and synthetic route tests; explicitly no authentication implementation. `tests/golden/login_route_test.go:1`, `docs/evidence/F16-public-login.md:1` |
| F17 | legacy preserved behavior | merged / merged / merged | designed | Archive evidence and synthetic tests; no preserved archive handler. `tests/golden/archive_route_test.go:1`, `docs/evidence/F17-public-archive.md:1` |
| F18 | legacy preserved behavior | todo / merged / merged | scaffold | Profile helpers/views are tested, but server and React entrypoint use fixed demo identity and synthetic fixtures. `internal/profile/view.go:1`, `internal/profile/view_test.go:1`, `frontend/src/main.tsx:1`, `internal/server/server.go:1` |
| F19 | legacy preserved behavior | todo / merged / merged | scaffold | Privacy/read helper is tested with synthetic stores; the HTTP handler uses a fixed demo owner. `internal/home/home.go:1`, `internal/home/home_test.go:1`, `internal/server/fixtures.go:1` |
| F20 | legacy preserved behavior | todo / merged / merged | scaffold | Principal boundary helper is tested; /account constructs principal 1 and fixture data. `internal/accountview/accountview.go:1`, `internal/accountview/accountview_test.go:1`, `internal/server/server.go:1` |
| F21 | legacy preserved behavior | todo / merged / merged | scaffold | ReadSettings validates read state; the approved mutation workflow is absent. `internal/profile/settings.go:1`, `internal/profile/settings_test.go:1` |
| F22 | legacy preserved behavior | todo / merged / merged | scaffold | Response contract values are tested; API result endpoints do not implement a credential/session flow. `internal/authflow/authflow.go:1`, `internal/authflow/authflow_test.go:1`, `internal/server/server.go:1` |
| F23 | legacy preserved behavior | todo / merged / merged | scaffold | In-memory session transitions exist; the public endpoint constructs an empty manager rather than a real session backend. `internal/session/session.go:1`, `internal/session/session_test.go:1`, `internal/server/server.go:1` |
| F24 | legacy preserved behavior | todo / merged / merged | scaffold | Bounded projection over in-memory slices; HTTP and frontend consume demo community data. `internal/community/community.go:1`, `internal/community/community_test.go:1`, `internal/server/fixtures.go:1` |
| F25 | legacy preserved behavior | todo / merged / merged | scaffold | Atomic/audited MemoryStore exists; no intended persistent adapter or route wiring. `internal/registration/registration.go:1`, `internal/registration/registration_test.go:1` |
| F26 | legacy preserved behavior | todo / merged / merged | scaffold | Reset behavior uses memory token state and fake identity/mailer dependencies; persistent wiring absent. `internal/recovery/recovery.go:1`, `internal/recovery/recovery_test.go:1` |
| F27 | legacy preserved behavior | todo / merged / merged | scaffold | Replay/expiry behavior uses an in-memory RememberTokenStore; no required supporting-backend wiring. `internal/session/token.go:1`, `internal/session/token_test.go:1` |
| F28 | legacy preserved behavior | todo / merged / merged | scaffold | Guestbook privacy/mutation behavior exists only in map-backed Store; route and real schema wiring absent. `internal/guestbook/guestbook.go:1`, `internal/guestbook/guestbook_test.go:1` |
| F29 | legacy preserved behavior | todo / merged / merged | scaffold | Escaping/allowlisting helper exists; /articles serves community fixtures rather than this implementation. `internal/articles/articles.go:1`, `internal/articles/articles_test.go:1`, `internal/server/server.go:1` |
| F30 | themes: theme system | todo / merged / merged | scaffold | Manifest/localization validation extends scaffold contracts; no complete installed theme system. `frontend/src/themeManifest.ts:1`, `internal/localization/localization.go:1`, `docs/units/F30.md:1` |
| F31 | Go backend | design / promoted / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F31-F45-candidate-design.md:1` |
| F32 | Go backend | design / promoted / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F31-F45-candidate-design.md:1` |
| F33 | Go backend | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F31-F45-candidate-design.md:1` |
| F34 | Go backend | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F31-F45-candidate-design.md:1` |
| F35 | Go backend | design / merged / merged | scaffold | Synthetic MemoryStore and synthetic SQL schema exercise transactions; selected real mutation/schema remains unspecified. `internal/audit/audit.go:172`, `internal/audit/audit_test.go:1`, `docs/evidence/F35-audit-transaction.md:1` |
| F36 | staff | design / todo / merged | scaffold | EnrollmentStore holds enrollment/audit records in memory; real staff identity/secret-protection adapter is absent. `internal/staff/enrollment.go:1`, `internal/staff/enrollment_test.go:1` |
| F37 | staff | design / merged / merged | scaffold | Library-backed per-staff TOTP and session binding exist; staff records and sessions remain in memory. `internal/staff/totp.go:1`, `internal/session/session.go:1`, `internal/session/stepup_test.go:1` |
| F38 | staff | design / todo / not found | scaffold | ReplayStoreGuard delegates to an interface; file persistence lives in test-local fake and StepWindow is memory-only. `internal/staff/replay.go:1`, `internal/staff/replay_test.go:82`, `internal/staff/window.go:1` |
| F38-a | staff | n/a / merged / merged | scaffold | ReplayStoreGuard delegates to an interface; file persistence lives in test-local fake and StepWindow is memory-only. `internal/staff/replay.go:1`, `internal/staff/replay_test.go:82`, `internal/staff/window.go:1`, `docs/units/F38-a.md:1` |
| F38-b | staff | n/a / parked-final / not found | scaffold | ReplayStoreGuard delegates to an interface; file persistence lives in test-local fake and StepWindow is memory-only. `internal/staff/replay.go:1`, `internal/staff/replay_test.go:82`, `internal/staff/window.go:1`, `docs/units/F38-b.md:1` |
| F38-ba | staff | n/a / merged / merged | scaffold | ReplayStoreGuard delegates to an interface; file persistence lives in test-local fake and StepWindow is memory-only. `internal/staff/replay.go:1`, `internal/staff/replay_test.go:82`, `internal/staff/window.go:1` |
| F38-bb | staff | n/a / merged / merged | designed | Test/evidence-only delivery asserts staff scoping on the memory StepWindow; no production adapter delivered. `internal/staff/replay.go:1`, `internal/staff/replay_test.go:82`, `internal/staff/window.go:1`, `docs/units/F38-bb.md:1` |
| F39 | Go backend | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F31-F45-candidate-design.md:1` |
| F40 | legacy preserved behavior | design / todo / merged | designed | Git delivery contains only blocker/evidence documents; no FAQ package or handler exists. `docs/units/F40.md:1`, `docs/evidence/F40-faq-route.md:1` |
| F41 | Go backend | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F31-F45-candidate-design.md:1` |
| F42 | staff | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F31-F45-candidate-design.md:1` |
| F43 | Go backend | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F31-F45-candidate-design.md:1` |
| F44 | Go backend | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F31-F45-candidate-design.md:1` |
| F45 | legacy preserved behavior | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F31-F45-candidate-design.md:1` |
| F46 | React frontend | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F46-F60-candidate-design.md:1` |
| F47 | themes: theme system | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F46-F60-candidate-design.md:1` |
| F48 | themes: theme system | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F46-F60-candidate-design.md:1` |
| F49 | React frontend | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F46-F60-candidate-design.md:1` |
| F50 | Redis | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F46-F60-candidate-design.md:1` |
| F51 | staff | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F46-F60-candidate-design.md:1` |
| F52 | React frontend | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F46-F60-candidate-design.md:1` |
| F53 | React frontend | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F46-F60-candidate-design.md:1` |
| F54 | React frontend | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F46-F60-candidate-design.md:1` |
| F55 | React frontend | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F46-F60-candidate-design.md:1` |
| F56 | React frontend | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F46-F60-candidate-design.md:1` |
| F57 | staff | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F46-F60-candidate-design.md:1` |
| F58 | themes: theme system | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F46-F60-candidate-design.md:1` |
| F59 | infrastructure | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F46-F60-candidate-design.md:1` |
| F60 | infrastructure | design / design / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/roadmap/F46-F60-candidate-design.md:1` |
| QA1 | infrastructure | n/a / merged / merged | scaffold | Staff identity-validation fix calls real TOTP code; staff data still uses MemoryStore and lacks backend integration. `internal/staff/totp.go:1`, `tests/staff/totp_test.go:1`, `docs/units/QA1.md:1` |
| RF1 | infrastructure | n/a / merged / merged | designed | Git delivery is only a consistency document; it does not implement product code. `docs/units/RF1.md:1` |
| QA2 | infrastructure | n/a / merged / merged | scaffold | Library-backed TOTP replaces custom computation, but staff storage/session wiring remains a scaffold. `internal/staff/totp.go:1`, `tests/staff/totp_test.go:1`, `docs/units/QA2.md:1`, `go.mod:1`, `go.sum:1`, `docs/units/F37.md:1` |
| RF2 | infrastructure | n/a / parked-final / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/units/RF2.md:1` |
| RF2a | infrastructure | n/a / merged / merged | designed | Test-finding fixes in a test-only delivery; no product implementation. `tests/staff/totp_test.go:1`, `docs/units/RF2a.md:1` |
| RF2b | infrastructure | n/a / merged / merged | designed | Audit disposition documentation only. `docs/units/QA3.md:1`, `docs/units/RF2b.md:1` |
| RF2c | infrastructure | n/a / merged / merged | designed | Consistency documentation only. `docs/units/RF2.md:1`, `docs/units/RF2c.md:1` |
| QA3 | infrastructure | n/a / todo / not found | designed | Written design only; no corresponding integrated implementation delivery. `docs/units/QA3.md:1` |

## Acceptance criteria as written

### F0

Source: `units.yaml:27` (canonical acceptance).

> acceptance: ["foundation CI green on main"]

### F1

Source: `units.yaml:37` (canonical acceptance).

> acceptance: ["pinned original source hash recorded"]

### F2

Source: `units.yaml:47` (canonical acceptance).

> acceptance: ["PolarIS BCrypt/$2y verifier is source-backed"]

### F3

Source: `units.yaml:57` (canonical acceptance).

> acceptance: ["bounded read contract with synthetic tests"]

### F4

Source: `units.yaml:67` (canonical acceptance).

> acceptance: ["deterministic comparator with synthetic mismatch tests"]

### F5

Source: `units.yaml:77` (canonical acceptance).

> acceptance: ["source-backed hotelview_news contract"]

### F6

Source: `units.yaml:87` (canonical acceptance).

> acceptance: ["synthetic read-only adapter boundary"]

### F7

Source: `units.yaml:97` (canonical acceptance).

> acceptance: ["typed view models; themes cannot select routes or identity"]

### F8

Source: `units.yaml:107` (canonical acceptance).

> acceptance: ["catalogs are data-only; locale is presentation metadata"]

### F14

Source: `units.yaml:117` (canonical acceptance).

> acceptance: ["evidence and tests only; no product change"]

### F15

Source: `units.yaml:127` (canonical acceptance).

> acceptance: ["synthetic route tests with labelled UNKNOWNs"]

### F16

Source: `units.yaml:137` (canonical acceptance).

> acceptance: ["no auth or session implementation"]

### F17

Source: `units.yaml:147` (canonical acceptance).

> acceptance: ["evidence and synthetic tests only"]

### F18

Source: `units.yaml:158` (canonical acceptance).

> acceptance: ["tabs 1-5 render profile state", "an invalid or absent tab falls back to tab 1", "the six-field F3 Profile is preserved", "negative tests cover a missing user and malformed state"]

### F19

Source: `units.yaml:169` (canonical acceptance).

> acceptance: ["name and ID lookup are equivalent", "an unknown owner is handled explicitly", "an owner sees their own hidden home", "an unauthorized viewer receives no private fields"]

### F20

Source: `units.yaml:180` (canonical acceptance).

> acceptance: ["one synthetic principal cannot read another principal's dashboard", "absent optional widgets do not fabricate state", "the field list stays read-only"]

### F21

Source: `units.yaml:191` (canonical acceptance).

> acceptance: ["invalid gender or figure is rejected", "an overlong motto is rejected", "an unauthorized principal cannot write", "a validation failure causes no synthetic write"]

### F22

Source: `units.yaml:202` (canonical acceptance).

> acceptance: ["the failed-login response contract is asserted", "the redirect to security-check is asserted", "wrong method, status and location negatives are covered", "no assertion of identity absent evidence"]

### F23

Source: `units.yaml:213` (canonical acceptance).

> acceptance: ["logout invalidates only the synthetic session", "the post-logout page exposes no private fields", "a retained-cookie negative case is covered"]

### F24

Source: `units.yaml:224` (canonical acceptance).

> acceptance: ["bounded lists and an empty state are asserted", "private or unapproved fields are rejected", "malformed pagination is rejected"]

### F25

Source: `units.yaml:234` (canonical acceptance).

> acceptance: ["validation rejects malformed input", "creation is atomic and audited in the synthetic store", "no real email or credentials are used"]

### F26

Source: `units.yaml:244` (canonical acceptance).

> acceptance: ["anti-enumeration responses are identical", "the reset token is single-use in the synthetic store", "synthetic mail and identity fixtures only"]

### F27

Source: `units.yaml:254` (canonical acceptance).

> acceptance: ["an expired token is rejected", "a replayed token is rejected", "an IP transition is handled explicitly", "synthetic tokens only"]

### F28

Source: `units.yaml:265` (canonical acceptance).

> acceptance: ["the list privacy gate is enforced server-side", "delete requires a widget-owner predicate", "no private field leaks to a non-owner"]

### F29

Source: `units.yaml:275` (canonical acceptance).

> acceptance: ["the archive route reserved by F17 is excluded", "text rendering escapes hostile input", "image URLs are allowlisted", "no CMS mutations"]

### F30

Source: `units.yaml:286` (canonical acceptance).

> acceptance: ["the presentation-only theme.v1/home.v1 boundary is preserved", "capability expansion is rejected", "malformed view models are rejected"]

### F31

Source: `docs/roadmap/F31-F45-candidate-design.md:49` (closest written statement (no canonical acceptance)).

> Account lookup/hash verification is already implemented and evidenced by F1/F2/F6; the F18-F30 proposal owns the public login transition at F22. No additional observable boundary is defensible here.

Source: `docs/roadmap/F31-F45-candidate-design.md:49` (design acceptance/stop statement).

> Retain adapter and verifier tests under their accepted F1/F2/F6 contracts; do not relabel them as a new unit. Reopen only for a distinct account contract with new evidence.

Gap: Reserved ID has no distinct acceptance boundary; retained without scope changes.

### F32

Source: `docs/roadmap/F31-F45-candidate-design.md:50` (closest written statement (no canonical acceptance)).

> Profile/content PolarIS read adapters, explicit columns, bound arguments, limits, and enum handling are already accepted under F3/F5/F6, while F18/F29 own their feature behavior. No additional integration boundary is demonstrated.

Source: `docs/roadmap/F31-F45-candidate-design.md:50` (design acceptance/stop statement).

> Do not duplicate accepted adapter work. Reopen only with a new source-backed adapter contract or ownership decision.

Gap: Reserved ID has no distinct acceptance boundary; retained without scope changes.

### F33

Source: `docs/roadmap/F31-F45-candidate-design.md:51` (closest written statement (no canonical acceptance)).

> CSRF is a required security criterion for F22/F23/F25/F26/F27/F28 mutations, but no distinct F31-F45 contract can be assigned without duplicating those reserved proposals.

Source: `docs/roadmap/F31-F45-candidate-design.md:51` (design acceptance/stop statement).

> Fold the CSRF acceptance criteria into the owning F18-F30 unit; do not create a second numbered security implementation.

Gap: Reserved ID has no distinct acceptance boundary; retained without scope changes.

### F34

Source: `docs/roadmap/F31-F45-candidate-design.md:52` (closest written statement (no canonical acceptance)).

> Return-target validation is part of the reserved F22/F27 auth/session contracts, not a separate observable unit in this lane.

Source: `docs/roadmap/F31-F45-candidate-design.md:52` (design acceptance/stop statement).

> Fold open-redirect negative tests into the owning proposal; reopen only with a distinct source-backed boundary.

Gap: Reserved ID has no distinct acceptance boundary; retained without scope changes.

### F35

Source: `docs/roadmap/F31-F45-candidate-design.md:53` (closest written statement (no canonical acceptance)).

> A website-owned mutation and its audit record commit atomically, including authorization, CSRF, validation, prepared SQL, and injected audit failure. This is a new audit integration, not F21 profile settings or F25 registration.

Source: `docs/roadmap/F31-F45-candidate-design.md:53` (design acceptance/stop statement).

> Coordinator chooses mutation, schema, actor fields, and transaction boundary. Negative: unauthorized, invalid, SQL failure, audit failure, partial commit, replay. Backend after gate; independent security reviewer. 32k / 135m. Stop on schema/audit ambiguity. Accept atomic synthetic store tests and no production enablement.

Runtime-promoted criteria, preserved separately from canonical authority:

> an unauthorized or invalid mutation is rejected and writes nothing
> the website-owned mutation and its audit record commit atomically in a synthetic store
> an injected audit failure rolls the mutation back with no partial commit
> all SQL is prepared and bound, and a replay attempt is rejected
> no production enablement and no real rows

### F36

Source: `docs/roadmap/F31-F45-candidate-design.md:54` (closest written statement (no canonical acceptance)).

> Staff enrollment binds one approved TOTP secret to one staff identity without exposing it, and enrollment is denied to disabled/unauthorized staff. This is separate from F25 registration and F27 public token/session behavior.

Source: `docs/roadmap/F31-F45-candidate-design.md:54` (design acceptance/stop statement).

> Coordinator owns staff identity, secret protection, recovery, authorization, and audit schema. Negative: unauthorized, disabled, duplicate, leaked secret, DB failure. Backend after gate; independent security reviewer. 32k / 135m. Stop on absent staff schema or production credentials. Accept synthetic secrets only, atomic audit, no seeded admin.

Runtime-promoted criteria, preserved separately from canonical authority:

> one approved TOTP secret binds to one staff identity without disclosure
> enrollment is denied to disabled or unauthorized staff
> duplicate enrollment and a DB failure are rejected atomically with no secret leaked
> synthetic secrets only; no seeded admin and no production credentials
> the audit record is written atomically with enrollment

### F37

Source: `docs/roadmap/F31-F45-candidate-design.md:55` (closest written statement (no canonical acceptance)).

> Staff step-up validates a real per-staff TOTP code within an approved time window and binds success to the intended staff session.

Source: `docs/roadmap/F31-F45-candidate-design.md:55` (design acceptance/stop statement).

> Coordinator approves step-up scope, skew, rate limits, and failure response. Negative: missing, disabled, malformed, wrong, expired, wrong-user, and DB-error cases. Backend after F36; independent security reviewer. 32k / 135m. Stop on shape-only validation or absent per-staff secret. Accept library-backed synthetic tests and session binding.

Runtime-promoted criteria, preserved separately from canonical authority:

> a real per-staff TOTP code within the approved time window validates step-up
> success binds to the intended staff session
> missing, disabled, malformed, wrong, expired and wrong-user codes fail explicitly
> rate limits and the failure response follow coordinator-approved scope
> library-backed validation only; a shape-only pass is rejected

### F38

Source: `docs/roadmap/F31-F45-candidate-design.md:56` (closest written statement (no canonical acceptance)).

> A previously accepted TOTP time step cannot be accepted again for the same staff identity, including concurrent submissions; replay state is durable rather than cache-only.

Source: `docs/roadmap/F31-F45-candidate-design.md:56` (design acceptance/stop statement).

> Coordinator owns persistence and compare/update locking. Negative: same-step replay, race, adjacent allowed step, expiry, wrong staff, outage. Backend after F36/F37; independent security reviewer. 28k / 120m. Stop on missing replay schema or non-atomic update. Accept race tests and durable-state proof.

Runtime-promoted criteria, preserved separately from canonical authority:

> a previously accepted time step cannot be accepted again for the same staff identity
> concurrent submissions of one step cannot both succeed
> replay state is durable rather than cache-only
> adjacent allowed step, expiry, wrong-staff and outage cases are handled
> the compare/update is atomic

### F38-a

Source: `docs/roadmap/F31-F45-candidate-design.md:56` (closest written statement (no canonical acceptance)).

> A previously accepted TOTP time step cannot be accepted again for the same staff identity, including concurrent submissions; replay state is durable rather than cache-only.

Source: `docs/roadmap/F31-F45-candidate-design.md:56` (design acceptance/stop statement).

> Coordinator owns persistence and compare/update locking. Negative: same-step replay, race, adjacent allowed step, expiry, wrong staff, outage. Backend after F36/F37; independent security reviewer. 28k / 120m. Stop on missing replay schema or non-atomic update. Accept race tests and durable-state proof.

Runtime-promoted criteria, preserved separately from canonical authority:

> a previously accepted (staff identity, time step) cannot be accepted a second time
> concurrent submissions of one step admit exactly one success under -race
> the compare/update is atomic and a store error fails closed with no accept
> replay state survives a store reopen, so it is durable and not cache-only

### F38-b

Source: `docs/roadmap/F31-F45-candidate-design.md:56` (closest written statement (no canonical acceptance)).

> A previously accepted TOTP time step cannot be accepted again for the same staff identity, including concurrent submissions; replay state is durable rather than cache-only.

Source: `docs/roadmap/F31-F45-candidate-design.md:56` (design acceptance/stop statement).

> Coordinator owns persistence and compare/update locking. Negative: same-step replay, race, adjacent allowed step, expiry, wrong staff, outage. Backend after F36/F37; independent security reviewer. 28k / 120m. Stop on missing replay schema or non-atomic update. Accept race tests and durable-state proof.

Runtime-promoted criteria, preserved separately from canonical authority:

> an adjacent allowed step is accepted once and a duplicate of either adjacent step is rejected
> a step outside the approved window is rejected
> the expiry boundary accepts the last valid instant and rejects the first invalid one
> a step accepted for one staff identity is not accepted for another identity

### F38-ba

Source: `docs/roadmap/F31-F45-candidate-design.md:56` (closest written statement (no canonical acceptance)).

> A previously accepted TOTP time step cannot be accepted again for the same staff identity, including concurrent submissions; replay state is durable rather than cache-only.

Source: `docs/roadmap/F31-F45-candidate-design.md:56` (design acceptance/stop statement).

> Coordinator owns persistence and compare/update locking. Negative: same-step replay, race, adjacent allowed step, expiry, wrong staff, outage. Backend after F36/F37; independent security reviewer. 28k / 120m. Stop on missing replay schema or non-atomic update. Accept race tests and durable-state proof.

Runtime-promoted criteria, preserved separately from canonical authority:

> an adjacent allowed step is accepted once and a duplicate of either adjacent step is rejected
> a step outside the approved window is rejected
> the expiry boundary accepts the last valid instant and rejects the first invalid one

### F38-bb

Source: `docs/roadmap/F31-F45-candidate-design.md:56` (closest written statement (no canonical acceptance)).

> A previously accepted TOTP time step cannot be accepted again for the same staff identity, including concurrent submissions; replay state is durable rather than cache-only.

Source: `docs/roadmap/F31-F45-candidate-design.md:56` (design acceptance/stop statement).

> Coordinator owns persistence and compare/update locking. Negative: same-step replay, race, adjacent allowed step, expiry, wrong staff, outage. Backend after F36/F37; independent security reviewer. 28k / 120m. Stop on missing replay schema or non-atomic update. Accept race tests and durable-state proof.

Runtime-promoted criteria, preserved separately from canonical authority:

> a step accepted for one staff identity is not accepted for another identity
> docs/units/F38-b.md records a literal `fidelity: guessed` line and the required independent security review note

### F39

Source: `docs/roadmap/F31-F45-candidate-design.md:57` (closest written statement (no canonical acceptance)).

> Audit redaction is a criterion of the new F35 mutation contract, while profile read is already reserved by F18; no independent F39 contract is defensible without double-counting.

Source: `docs/roadmap/F31-F45-candidate-design.md:57` (design acceptance/stop statement).

> Keep redaction and audit-event assertions inside F35 or a later owner-approved staff unit; do not duplicate F18.

Gap: Reserved ID has no distinct acceptance boundary; retained without scope changes.

### F40

Source: `docs/roadmap/F31-F45-candidate-design.md:58` (closest written statement (no canonical acceptance)).

> Public legacy FAQ category and query-search read projection: source branches on GET `id` or POST `query`, renders category children or matching item/category labels. `help.php:18-23,26-32,51-73`; `.htaccess:72-73`. This is not F5 `hotelview_news`, F24 community, F29 articles, or F54 website-owned composition. GET `/help/{id}` and POST `/help/faqsearch` are source-indicated request shapes, not captured HTTP contracts.

Source: `docs/roadmap/F31-F45-candidate-design.md:58` (design acceptance/stop statement).

> Prerequisites: retained method/status/headers/cookies/body markers, FAQ field/schema ownership, prepared-query/escaping/limits policy, owner scope approval and independent review. Negative: missing/invalid category, empty search, malformed/overlong query, wrong method, unsafe text, private-field leakage; no writes. Backend/frontend after gates; reviewer independently checks source and response contract. 12k / 45m. Stop on missing capture, inferred schema or auth/write expansion. Accept bounded synthetic read tests only after decisions and exact response evidence. Later optional parity, not first-release accepted or code-ready.

Runtime-promoted criteria, preserved separately from canonical authority:

> GET /help/{id} renders category children for a valid id
> POST /help/faqsearch renders matching item and category labels
> missing or invalid category and empty or overlong query are rejected
> queries are prepared and bounded, no private field leaks and no write occurs
> read-only bounded synthetic tests only, after capture and schema decisions

### F41

Source: `docs/roadmap/F31-F45-candidate-design.md:59` (closest written statement (no canonical acceptance)).

> No distinct source-backed unit remains. Website-owned mutation behavior and its audit-event/redaction criteria are represented together by F35.

Source: `docs/roadmap/F31-F45-candidate-design.md:59` (design acceptance/stop statement).

> Requires new evidence or an owner-approved decision that is not a subdivision of F35.

Gap: Reserved ID has no distinct acceptance boundary; retained without scope changes.

### F42

Source: `docs/roadmap/F31-F45-candidate-design.md:60` (closest written statement (no canonical acceptance)).

> No distinct source-backed unit remains. Staff enrollment/step-up/replay are separately represented by F36-F38.

Source: `docs/roadmap/F31-F45-candidate-design.md:60` (design acceptance/stop statement).

> Do not split one TOTP observation into additional units.

Gap: Reserved ID has no distinct acceptance boundary; retained without scope changes.

### F43

Source: `docs/roadmap/F31-F45-candidate-design.md:61` (closest written statement (no canonical acceptance)).

> No distinct source-backed unit remains. CSRF and redirect-policy criteria belong inside the owning F18-F30 auth/session or mutation proposal, with audited-mutation enforcement in F35 where applicable.

Source: `docs/roadmap/F31-F45-candidate-design.md:61` (design acceptance/stop statement).

> Requires a new observable contract, not another negative case for the reserved F18-F30 units or F35.

Gap: Reserved ID has no distinct acceptance boundary; retained without scope changes.

### F44

Source: `docs/roadmap/F31-F45-candidate-design.md:62` (closest written statement (no canonical acceptance)).

> No retained capture or verified ownership evidence supports another core backend/security contract in this range.

Source: `docs/roadmap/F31-F45-candidate-design.md:62` (design acceptance/stop statement).

> Stop pending fresh source/capture/schema evidence.

Gap: Reserved ID has no distinct acceptance boundary; retained without scope changes.

### F45

Source: `docs/roadmap/F31-F45-candidate-design.md:63` (closest written statement (no canonical acceptance)).

> Guestbook privacy/read/write is reserved by F28; the source-level delete/list authorization concern cannot be safely promoted into a second unit.

Source: `docs/roadmap/F31-F45-candidate-design.md:63` (design acceptance/stop statement).

> Keep the concern as a F28 security gate; do not duplicate it here.

Gap: Reserved ID has no distinct acceptance boundary; retained without scope changes.

### F46

Source: `docs/roadmap/F46-F60-candidate-design.md:19` (closest written statement (unfilled)).

> Accepted F7 already validates `home.v1`, version/malformed values, and presentation capability. The child proposal names no new approved schema, field inventory, or integration distinct from that boundary. Sanitization and unknown-field rejection belong to a later owning feature/API contract, not a duplicate numbered envelope.

Gap: Reserved ID has no distinct acceptance boundary; retained without scope changes.

### F47

Source: `docs/roadmap/F46-F60-candidate-design.md:24` (closest written statement (unfilled)).

> Accepted F7 already supplies `theme.v1`, `StarterShell`, `home.v1`, and presentation-only manifest validation. The child narrows the topic relative to ambiguous F30, but its observable acceptance repeats F7 without a measured new package/install or original-parity contract. F24 is a community read projection, not a theme proposal; it is not the reason for this gap.

Gap: Reserved ID has no distinct acceptance boundary; retained without scope changes.

### F48

Source: `docs/roadmap/F46-F60-candidate-design.md:29` (design acceptance/observable statement).

> Observable contract: an optional modern theme may render only reviewed, provenance-recorded assets through a validated manifest; it cannot execute reference application code or access arbitrary paths.

Source: `docs/roadmap/F46-F60-candidate-design.md:35` (design acceptance/observable statement).

> Acceptance: every selected asset has source, retrieval date, hash, creator/terms and a synthetic render fixture; otherwise leave unfilled. Stop on unresolved rights or Atom/Pixel63/SWF dependency.

### F49

Source: `docs/roadmap/F46-F60-candidate-design.md:39` (design acceptance/observable statement).

> Observable contract: a versioned, data-only catalog package is validated as a complete release artifact before activation, including locale metadata, declared key inventory, fallback declarations, and catalog/content compatibility; this is a package/schema-validation boundary, not F8's already-accepted in-memory lookup and fallback behavior.

Source: `docs/roadmap/F46-F60-candidate-design.md:45` (design acceptance/observable statement).

> Acceptance: synthetic package fixtures prove manifest validation and compatibility checks beyond F8's lookup tests, while preserving fixed `home.v1` keys and explicit missing state. Stop if persistence, signing, or activation requires schema/security decisions.

### F50

Source: `docs/roadmap/F46-F60-candidate-design.md:49` (design acceptance/observable statement).

> Observable contract: an approved locale-aware presentation response is stored and retrieved under a normalized locale-varying cache key, with explicit TTL and invalidation on catalog/package activation; a stale or unavailable cache cannot be reported as an authoritative publication.

Source: `docs/roadmap/F46-F60-candidate-design.md:55` (design acceptance/observable statement).

> Acceptance: synthetic tests prove distinct normalized locale keys, explicit TTL, activation invalidation, and outage-as-miss/failure semantics using the F7 cache double; no production Redis or catalog write. Stop on unspecified TTL, cache authority, or invalidation ordering.

### F51

Source: `docs/roadmap/F46-F60-candidate-design.md:59` (design acceptance/observable statement).

> Observable contract: an authenticated housekeeping React shell displays only server-authorized capabilities, uses a dedicated housekeeping style within the same theme architecture, and cannot grant permissions by UI visibility.

Source: `docs/roadmap/F46-F60-candidate-design.md:65` (design acceptance/observable statement).

> Acceptance: only after an approved capability contract and negative browser tests; no staff implementation or production enablement from this design. Stop on rank-to-permission ambiguity.

### F52

Source: `docs/roadmap/F46-F60-candidate-design.md:69` (design acceptance/observable statement).

> Observable contract: an approved website-owned page model has stable identifiers, validated route-safe slugs, locale variants, draft/published state, and presentation metadata without arbitrary template execution.

Source: `docs/roadmap/F46-F60-candidate-design.md:75` (design acceptance/observable statement).

> Acceptance: explicit website-owned schema and atomic audited mutation contract approved before any implementation card. Stop on PolarIS ownership overlap.

### F53

Source: `docs/roadmap/F46-F60-candidate-design.md:79` (design acceptance/observable statement).

> Observable contract: approved navigation entries render stable labels, destinations, visibility, ordering, locale variants, and theme-compatible metadata while route behavior remains server-owned.

Source: `docs/roadmap/F46-F60-candidate-design.md:85` (design acceptance/observable statement).

> Acceptance: synthetic read fixture may be proposed; writes require approved schema, authorization, CSRF, prepared SQL, same-transaction audit, and browser contract.

### F54

Source: `docs/roadmap/F46-F60-candidate-design.md:89` (design acceptance/observable statement).

> Observable contract: website-owned view models expose only approved escaped fields and stable ordering for FAQ, banner, and landing compositions; this excludes the F24 community projection, F29 article/category projection, and F40 legacy FAQ category/search endpoint and query semantics. A composition may consume an approved FAQ read model later, but cannot duplicate F40's route tests. Public display does not imply editor or publication authority.

Source: `docs/roadmap/F46-F60-candidate-design.md:95` (design acceptance/observable statement).

> Acceptance: no duplicate F17 archive, F24 community, F29 article/category, or F40 FAQ endpoint contract; synthetic fixtures must identify fields and unknowns. Stop on missing response facts or schema inference.

### F55

Source: `docs/roadmap/F46-F60-candidate-design.md:99` (design acceptance/observable statement).

> Observable contract: a future approved publication operation activates one validated version atomically, preserves the prior version for rollback, and never partially activates a locale, page, navigation, theme, or catalog.

Source: `docs/roadmap/F46-F60-candidate-design.md:105` (design acceptance/observable statement).

> Acceptance: only a design review may proceed until atomicity and audit semantics are source-backed or explicitly approved. Stop on any best-effort publication behavior.

### F56

Source: `docs/roadmap/F46-F60-candidate-design.md:109` (design acceptance/observable statement).

> Observable contract: content references media by validated website-owned metadata and allowlisted identifiers, never arbitrary filesystem paths, executable uploads, or unverified external URLs.

Source: `docs/roadmap/F46-F60-candidate-design.md:115` (design acceptance/observable statement).

> Acceptance: metadata-only synthetic fixture can be designed; no upload or storage implementation without explicit safe-upload contract and review.

### F57

Source: `docs/roadmap/F46-F60-candidate-design.md:119` (design acceptance/observable statement).

> Observable contract: an approved housekeeping view displays status/maintenance state, records explicit cache invalidation outcomes, and exposes immutable audit history without treating presentation state as authority.

Source: `docs/roadmap/F46-F60-candidate-design.md:125` (design acceptance/observable statement).

> Acceptance: synthetic read-only fixture may record UNKNOWNs; mutation requires same-transaction audit and explicit cache contract. Stop on arbitrary settings or production operations.

### F58

Source: `docs/roadmap/F46-F60-candidate-design.md:129` (design acceptance/observable statement).

> Observable contract: browser tests verify initial rendering, navigation, locale display, failure states, keyboard/accessible names, and housekeeping authorization without allowing theme or locale selection to change security behavior.

Source: `docs/roadmap/F46-F60-candidate-design.md:135` (design acceptance/observable statement).

> Acceptance: use only configured runner and synthetic fixtures; record exact viewport/method. Stop if no approved runner or capture baseline exists; do not claim visual regression coverage otherwise.

### F59

Source: `docs/roadmap/F46-F60-candidate-design.md:139` (design acceptance/observable statement).

> Observable contract: a release candidate is accepted only when typed view-model, theme manifest, locale, asset provenance, browser, cache, audit, and golden-contract checks report explicit pass/blocked/UNKNOWN states.

Source: `docs/roadmap/F46-F60-candidate-design.md:145` (design acceptance/observable statement).

> Acceptance: list base/head SHA, changed paths, test output, unresolved UNKNOWNs, and no production claims. Stop on unexplained red CI or missing required evidence.

### F60

Source: `docs/roadmap/F46-F60-candidate-design.md:149` (design acceptance/observable statement).

> Observable contract: the first-release decision packet distinguishes synthetic presentation contracts, source-backed public behavior, gated CMS design, and production enablement; no design label silently grants implementation authority.

Source: `docs/roadmap/F46-F60-candidate-design.md:155` (design acceptance/observable statement).

> Acceptance: synthesis must reconcile numbering against F18-F45, count distinct defensible units, preserve missing gates, and create no implementation cards until the owner accepts scope. Stop on unresolved numbering or absent independent review.

### QA1

Source: `docs/units/QA1.md:1` (support delivery note (not product criteria)).

> fidelity: guessed

Runtime-promoted criteria, preserved separately from canonical authority:

> Validation rejects empty or mismatched record identities before accepting a code.
> A synthetic store returning Bob's record for Alice's lookup produces ErrWrongUser even with Bob's valid code.
> Valid test records explicitly declare their staff identities.
> Matching enabled identities continue to validate correctly.

### RF1

Source: `docs/units/RF1.md:1` (support delivery note (not product criteria)).

> RF1 consistency pass

Runtime-promoted criteria, preserved separately from canonical authority:

> the open audit findings are fixed or explicitly ruled out
> package layout and naming follow the neighbours' convention
> no behaviour changes; existing tests still pass

### QA2

Source: `docs/units/QA2.md:1` (support delivery note (not product criteria)).

> QA2 library-backed TOTP validation

Runtime-promoted criteria, preserved separately from canonical authority:

> Validation delegates TOTP computation to a maintained TOTP library rather than handwritten truncation logic.
> Deterministic external vectors verify the configured algorithm, digit count, and period.
> Current-step acceptance and adjacent-step rejection are explicitly tested.
> Comments and documentation identify the timing policy as synthetic and do not claim owner approval.
> Missing, disabled, malformed, wrong-user, and store-error cases remain fail-closed.

### RF2

Source: `docs/units/RF2.md:3` (support delivery note (not product criteria)).

> This record covers the RF2 consistency pass and package alignment attempt in RF2c.

Runtime-promoted criteria, preserved separately from canonical authority:

> the open audit findings are fixed or explicitly ruled out
> package layout and naming follow the neighbours' convention
> no behaviour changes; existing tests still pass

### RF2a

Source: `docs/units/RF2a.md:3` (support delivery note (not product criteria)).

> - Corrected the per-staff isolation assertion: Alice's generated code must not

Runtime-promoted criteria, preserved separately from canonical authority:

> the open QA3 audit findings in tests/staff/totp_test.go are fixed or explicitly ruled out
> the test file's package path and naming follow the neighbours' convention
> no behaviour changes; existing tests still pass

### RF2b

Source: `docs/units/RF2b.md:3` (support delivery note (not product criteria)).

> - QA3 disposition record documents the missing finding input and blocks unsupported fixed/ruled-out claims.

Runtime-promoted criteria, preserved separately from canonical authority:

> each open QA3 finding is marked fixed or explicitly ruled out
> each disposition cites the file and line that resolved it
> no behaviour changes

### RF2c

Source: `docs/units/RF2c.md:3` (support delivery note (not product criteria)).

> fidelity: guessed

Runtime-promoted criteria, preserved separately from canonical authority:

> the record states which findings were fixed and which were ruled out
> the record confirms package layout and naming match the neighbours
> no behaviour changes; existing tests still pass

### QA3

Source: `docs/units/QA3.md:5` (support delivery note (not product criteria)).

> - No QA3 finding text was supplied or present at the authorized input path when RF2b ran; therefore there are no findings that can be responsibly marked fixed or ruled out. This is an input gap, not a claim that all findings were resolved.

Runtime-promoted criteria, preserved separately from canonical authority:

> Positive validation cases use fixed independently sourced vectors rather than production-generated expected codes.
> Alice and Bob have distinct synthetic secrets, and Alice's fixed code is rejected for Bob at the selected test instant.
> Previous-step and next-step codes explicitly exercise ErrExpiredCode under the documented synthetic policy.
> A code outside the adjacent window explicitly exercises ErrWrongCode.
> Tests do not claim session binding or escalation coverage when no session operation is exercised.

## Product stand-ins

| Stand-in | Location | Real replacement written? | Existing roadmap authority |
|---|---|---|---|
| MemoryStore | `internal/registration/registration.go:73` | no | F25 explicitly scopes the current synthetic store; no concrete real replacement unit. |
| MemoryStore | `internal/recovery/recovery.go:66` | no | F26 scopes synthetic identity/mail/token behavior; no concrete replacement unit. |
| Store | `internal/guestbook/guestbook.go:27` | no | F28 has unresolved schema/helper semantics; real replacement not scheduled. |
| MemoryStore | `internal/audit/audit.go:172` | no | F35 leaves chosen mutation/schema unspecified; no concrete real replacement scheduled. |
| SQLStore (synthetic schema) | `internal/audit/audit.go:221` | no | F35 adapter has only synthetic table selection; real mutation contract unspecified. |
| Manager (sessions and step-up counters) | `internal/session/session.go:39` | yes | DECISIONS.md:23 requires Redis supporting cache/session workloads; exact TTL/serialization contract gap retained. |
| RememberTokenStore | `internal/session/token.go:29` | no | F27 leaves token storage coordinator-owned; no named persistent replacement scheduled. |
| EnrollmentStore | `internal/staff/enrollment.go:33` | no | F36 leaves staff schema/secret protection unspecified; no concrete adapter scheduled. |
| MemoryStore | `internal/staff/totp.go:32` | no | F36/F37 specify per-staff identity but no real secret-store replacement contract. |
| StepWindow | `internal/staff/window.go:14` | yes | F38/F38-a already require durable atomic replay; concrete persistence/locking remains a gap. |
| Memory | `internal/cache/cache.go:23` | yes | DECISIONS.md:23 and F50 require Redis supporting cache integration; not authoritative data. |
| Model (slice-backed data) | `internal/community/community.go:61` | no | F24 scopes synthetic lists; no wired source/store replacement card. |
| fixtures | `internal/server/fixtures.go:16` | no | Server fixture assembly lacks an explicitly scheduled real replacement unit. |
| homeFixtures | `internal/server/fixtures.go:37` | no | F19 synthetic helper delivered; intended real home adapter not scheduled. |
| profileFixtures | `internal/server/fixtures.go:53` | no | F6 existing ProfileStore is an unwired read adapter, not a new replacement card. |
| profile/account/home demo models | `frontend/src/main.tsx:1` | no | Required React/Go contracts are broad scope; no API-wiring replacement card identified. |
| communityFixture | `frontend/src/community/viewModel.ts:68` | no | F24 synthetic read model; no real dataset replacement scheduled. |
| emptyCommunityFixture | `frontend/src/community/viewModel.ts:76` | no | Synthetic presentation fixture; no concrete real-data integration scheduled. |
| syntheticCatalogs | `frontend/src/localization/index.ts:16` | yes | F49 package and DECISIONS.md:24 authenticated housekeeping schedule catalog management. |

Legitimate test-local doubles are listed separately in progress.json. They are not unscheduled product replacements.

## Gaps and capture status

- 12 reserved canonical IDs have no distinct acceptance boundary: F31-F34, F39, F41-F47; all retained.
- F35 selected real mutation/schema/actor fields and zero-row adapter semantics are unwritten; no invented persistence fix.
- F38/F38-a real durable replay adapter and compare/update locking contract are unwritten; fake durability is not production proof.
- F21 mutation acceptance exceeds the delivered read/validation helper.
- Habbo and Atom named theme package/assets/visual acceptance inventory is unwritten; both remain approved scope.
- Several real backend and frontend adapter replacements are not scheduled as concrete roadmap cards; inventory reports this without adding/reprioritizing features.

Optional original Docker captures skipped: permission denied connecting to unix:///var/run/docker.sock. No real site or external capture was contacted.

Git/runtime divergences: F36, F40. Git-merged scaffold units: 26. Stand-ins without a scheduled replacement: 15.

# F18 profile read: F3 reconciliation and prerequisites

Status: refreshed local planning candidate; not an implementation brief or approved API.
Accepted integration base: `5dd7b675be617d621fd1c7ec51126368bfb50a37`.
Original planning base: `d125cd6cf98c230e2141cb58f285442a96e85ae7`.
Author card: `t_73cb0639`; refresh card: `t_0d2340ec`;
delivered proposal parent: `t_6039f10e`.
Only authorized edit: this document. No source, tests, evidence, policy, queue,
or run-state change is included.

## Authority and current-state reconciliation

PR #31 delivered the reviewed proposal `3f688f852aeb389a56811b62052c1ddf4c95f6c7`
by normal merge at the original planning base above. Delegated approval `t_ccd5229d`,
also recorded on PR #31 as comment `5983884781`, says APPROVE F18-F24
PLANNING ONLY, with no implementation or merge authority. This document
narrows only F18; it does not dispatch the seven-unit table.

`docs/roadmap/F18-F30-feature-approval.md:25,28,58,64-65` remains the specific
proposal authority: profile reads need F3 reconciliation, field ownership,
response evidence where claimed, and separate per-unit implementation approval.
Path envelopes and proposed test names are estimates, not edit permission.
`AGENTS.md:35-40,42-62,64-72` and `DECISIONS.md:9,22,25,31-36` retain
coordinator ownership, bounded approver delegation and independent review/delivery
gates. Delegation opens no ownership, privacy, authentication or implementation gate.

At author preflight, authenticated PR #31 readback was MERGED at that exact
head/merge; remote main was the original planning base. PR #34 was then OPEN at
`29306ab57b0199e5e847ebba6835d99acbbc3c94`. At refresh preflight, authenticated
readback and fetched/remote main confirmed its delivery at integration base
`5dd7b675be617d621fd1c7ec51126368bfb50a37`. Its five policy/documentation paths
are disjoint from this document; F3/F6, originals and the proposal remain unchanged.
The current policy retains planning-only and closed-list boundaries. Original
candidate `211bbf0e2421d0342e1f160dc648408ae009784a` received exact independent
ACCEPTED from `t_06f22290`, but that review does not transfer to this refresh.
Recheck policy/main and obtain fresh exact-target review and applicable approval/CI
before publication/delivery; no old SHA gate is inherited.

`tasks/queue.md:26` and `docs/ai-run-state.md:42` still describe the proposal
approval/delivery gate as pending. Those snapshots predate the verified PR #31
handoff and fresh planning-only approval. For this one-file planning task,
the exact delivered proposal, approval and parent handoff resolve that lag;
they do not amend those files or open implementation. The evidence lane's
stop in `tasks/queue.md:25,37-44` and `docs/ai-run-state.md:41` remains distinct.
Reuse `t_aed9f2eb`: no duplicate checkpoint, capture acquisition, polling of
capture availability, new route unit or new F number follows from this plan.
F16/F17 remain delivered evidence/test identifiers; F18 remains planning only.

## Bounded desired read behavior, not a retained response contract

The desired future slice is a read-only profile presentation model with a
selected tab in 1-5, absent selection defaulting to 1 and invalid selection
returning to 1, while preserving the accepted six-field F3 projection.
No tab view, HTTP handler, redirect code, serialized response, privacy policy
or additional field is approved here. Tabs are navigation candidates, not
permission to expose the legacy account/contact/password panels.

### Exact original authority

Read-only original inspected:
`C:/Users/Karim/Documents/ChatGPT/New project/hotel-drogon-scope-guard/stage3-original-phpretro/profile.php`.
Its byte SHA-256 is
`69cfd28916e0d905eedc846d088dd0fadf20b1e6afc2cc741a6402801d7f0aa1`,
independently rehashed against `docs/stage3-original-phpretro-sha256.csv:31`
and the proposal's F18 citation. The manifest's historical absolute path
names a different tree location; the matching digest establishes byte identity,
not deployed state. These are original-source citations, not application files.

| Original citation | Observed source behavior | Limit of authority |
| --- | --- | --- |
| `profile.php:18-20` | Includes core/session and constructs `profile_sql`. | Session inclusion is not an approved F18 identity/privacy contract. Helper and runtime semantics are not established here. |
| `profile.php:28-42` | GET tab takes precedence over POST tab; values compared below 1 or above 5 trigger a Location header and exit; absent tab becomes string `1`. | Preserve the range/default intent in planning. PHP coercion, malformed-input parsing, exact response status and Go/React selection rules require a separately approved contract; do not invent them. |
| `profile.php:67-86` | Non-figure-update branch reads `figure` and `sex`; five wardrobe reads select `figure,gender` using slot IDs 1-5 and the current user ID, then conditionally construct avatar URLs. | Source proves these names and reads, not their PolarIS mapping, ownership, availability, privacy or safe rendering semantics. |
| `profile.php:110-115` | Non-motto-update branch reads `mission`, `show_home`, `email_minimail`, `email_friendrequest`, `show_online`. | No approved settings projection, value domain or ownership mapping follows. |
| `profile.php:47-65,91-108` | Adjacent branches perform appearance/motto/preferences updates and emulator notifications. | Explicitly excluded; legacy SQL and filters are not an approved write, audit, CSRF or validation contract. |

### Missing retained response authority (separate prerequisite)

No verifiable retained profile response manifest/hash is established by this
research (`F18-F30-feature-approval.md:25,58`). Method, final status, redirect
chain, headers, cookie/request-session provenance, body markers, rendered
wardrobe/settings and actual tab responses remain UNKNOWN. Source-only
Location calls are not captured response facts. This task reads original
source only, acquires no captures, and introduces no real-data fixture.
Source digests are provenance; never use capture digests as synthetic expected
hashes. Missing response authority need not prevent documenting prerequisites,
but it stops any future claim of observed profile response parity.

## Existing F3/F6 boundary and observed gaps

`tasks/F3.md:13-24` requires read-only ID/normalized-username lookup through
an injected store with synthetic tests. `docs/evidence/F3-profile-schema.md:9-16`
records Polaris schema/Java lookup evidence and limits the first projection to
`id`, `username`, `motto`, `look`, `gender`, `account_created`. Its upstream
citations are the accepted F3 evidence, not new inspection of production rows.
`real_name` remains excluded: schema presence does not prove mapping or exposure.
Passwords, contact details, IP/machine/token data, rank/authorization, currency,
room state and every write remain excluded.

Direct application inspection confirms:

- `internal/profile/profile.go:1,16-28`: the package calls itself a read-only
  public profile boundary; `Profile` has exactly the six fields above and
  `Store` only `FindByID`/`FindByUsername`. There is no wardrobe, settings,
  tab, principal or write field/method.
- `profile.go:32-45`: `Service.ByID` rejects nil store/nonpositive ID with
  `ErrStoreUnavailable`; `ByUsername` trims whitespace and rejects nil
  store/empty input with that same error. Normalization here is trimming,
  not case folding or identity equivalence.
- `profile.go:47-57`: store errors propagate with a zero profile; nonpositive
  returned ID/empty username becomes `ErrNotFound`; only gender `M`/`F` is
  accepted. Look/motto syntax, timestamp semantics, requested-versus-returned
  identity and owner visibility are not validated by this function.
- `internal/profile/profile_test.go:9-49`: synthetic store/profile and four
  tests cover ID read, username read with spaced input, malformed gender and
  propagated not-found. The synthetic store ignores lookup arguments, so the
  trim test does not assert what argument reached the store. There are no tab,
  wardrobe/settings or cross-principal tests here; no new test was run or added.
- `internal/polaris/store.go:19-30,46-74` is the existing `profile.Store`
  adapter. Both reads select exactly the six columns with bound `?` and
  `LIMIT 1`; no rows maps to `profile.ErrNotFound`. This already satisfies the
  query-shape check listed in `F3-profile-schema.md:21`; do not invent another
  F3 SQL implementation or map legacy names onto these columns.
- `internal/polaris/store_test.go:55-61,92-116,119-138` supplies synthetic
  profile rows, asserts the username query/arguments, ID no-row mapping and
  nil database failure. It is not deployed-row evidence. Existing F6 limitations
  are recorded in `docs/evidence/F6-polaris-read-adapter.md:20-22`.

Definition/import/usage searches found the adapter and its tests as application
consumers of the profile contract, not an existing profile route/view. F3's
public-read label does not settle F18's eventual self-service privacy policy.
The proposal's owner-only synthetic fixture is a future planning prerequisite,
not proof that current F3 reads are private or that F18 may add authorization.

## Ownership and decisions still required (not missing captures)

| Prerequisite | Current state | Required decision/evidence before implementation |
| --- | --- | --- |
| Six-field compatibility | Accepted F3 shape exists; no enlargement here. | Explicit per-unit implementation authority preserving F3 behavior or separately approving a change; exact base, paths, tests and independent review. |
| Legacy `figure`/`sex`/`mission` versus F3 `Look`/`Gender`/`Motto` | Mapping and field ownership UNKNOWN. Similar names are not proof. | Source-backed ownership/semantics decision; no guessed alias or new query. |
| Wardrobe and settings | Schema, website/PolarIS ownership, value domains, empty/malformed state and privacy UNKNOWN. | Coordinator/owner-approved field matrix with provenance and explicit exposure limits; otherwise omit from any future concrete contract. |
| Principal/visibility | F18 owner/read/privacy semantics UNKNOWN; F3 has no principal parameter. | Separate explicit privacy/auth boundary decision, including cross-owner expectations; no auth/session implementation under this card. |
| Tab parsing/presentation | Source range/default intent exists; concrete typed view, malformed-state and wire semantics UNKNOWN. | Narrow approved input/output contract and synthetic acceptance matrix, independent of PHP coercion or assumed HTTP status. |
| Response parity | Retained profile response authority missing. | Exact credential-free retained authority where response facts are claimed; no capture acquisition authorized here. |

## Future envelopes and ordering, without edit permission

The only source-justified Go inspection envelope is the existing
`internal/profile/profile.go` plus `internal/profile/profile_test.go` for
six-field/service compatibility. The existing adapter/test pair
`internal/polaris/store.go` and `internal/polaris/store_test.go` is a read-only
inspection dependency, not a granted change scope. A future card must justify
any adapter edit separately after ownership approval.

No tab/read-view symbol or profile frontend module was found in this checkout.
Exact new Go view/tab files and frontend files/tests therefore remain UNKNOWN.
The proposal's `frontend/src/profile/**`, `frontend/tests/profile.test.ts` and
F21 `internal/profile/settings.go` are estimates, not existing symbols or
permission to create them. Do not issue cards with those broad estimates as
executable scope. Narrow only after contract and file ownership are settled.

Future synthetic acceptance planning should preserve existing F3 positive/error
behavior, verify actual lookup arguments, exercise absent/valid/invalid tab
selection under an approved parsing contract, and cover missing/malformed state.
Owner-only/cross-owner negative fixtures require an approved privacy boundary
first. No live rows, cookie values, credentials or raw captures belong in tests.
None of this test planning grants implementation authority.

Serialize F18 and F21 shared profile scope; never run overlapping editors.
Exclude settings writes, emulator notifications and F21 mutations/audit/CSRF.
F22/F23 authentication/session/cookie/security and all Batch B remain owner-closed.
Production, schema/migrations, security, credentials, real data, runner/CI and
protections are not modified or approved. No other F unit is selected here.

## Verification and bounded continuation

Documentation-only: local Go/frontend runtime tests are NOT RUN and are not
required for this one-file planning phase. Historical F3/F6 test claims are not
reported as fresh passes. Author handoff must record exact candidate/base,
ancestry, one-path diff, clean checkout, diff-check, unchanged proposal numbering,
original hash, conflict/high-confidence-secret scan and no raw-capture additions.

Create independent review only after the exact local candidate exists, at that
candidate checkout. The reviewer checks citations, compatibility/UNKNOWNs,
planning authority, scope and scans, not implementation readiness. Complete this
finite author phase to release review; do not wait on its descendant. A separate
coordinator acceptance/planning successor must require explicit exact-target
ACCEPTED, recheck live main/policy, and keep publication behind required exact-head
foundation and normal coordinator gates. A changed candidate needs fresh review
and applicable approval/CI. No self-review, publication or merge by this author.

Continuation remains planning-only. If ownership, privacy or response prerequisites
cannot be satisfied within authorized planning, record the precise owner/evidence
stop; do not create implementation cards or duplicate `t_aed9f2eb`.
Stop on guessed schema/source discrepancy, changed authority, active edit overlap,
secret/real data, auth/provider failure, security expansion or second failure.
Cap: 12,000 tokens / 45 minutes / one retry. Model: A6API coordinator default
`gpt-6.1-sol`; merchant input/cached-input/output tokens, reasoning effort and cost
are unavailable when unexposed. No savings claim or billed-model inference.

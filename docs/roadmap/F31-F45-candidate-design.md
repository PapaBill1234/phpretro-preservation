# F31-F45 Core Backend and Security Candidate Design

Status: provisional planning only. This document does not authorize product, schema, authentication, security, production, credential, real-data, migration, or runner changes.

Base and numbering

- Reviewed base: `473e1206c4dd63bdbb4a9da914bdc43b1a1bdb9b`, equal to current `origin/main` at design time and a descendant of the prior accepted research base `299556af68e940769ca5fcf1b04ad39585047237`.
- F16 and F17 are reserved evidence lanes currently in independent review/integration, not delivered by this card. F18-F30 is a separate planning horizon. The live F18-F30 proposal reserves F18/F19 profile-home behavior, F22 login transition, F23 logout, F25 registration, F26 recovery, F27 token/session, F28 guestbook, and F29 article/content behavior. No F18-F30 identifier is reused here, and this document does not rename those contracts.
- Every identifier below is provisional and requires coordinator scope approval, exact accepted base, and independent review before any implementation card can dispatch.
- Evidence status uses: `proposal-ready` (source-backed boundary suitable for scope review), `evidence-needed`, `owner/security/schema gate`, and `out of current authorization`.
- `code-ready` is intentionally absent: this design alone cannot establish that status.

Evidence register

| Source | SHA-256 | Relevant citations and limit |
| --- | --- | --- |
| `stage3-original-phpretro/.htaccess` | `c714a08718a6e032488bb1a7c10fe253eec12b12c3682adce73e22d5e68684bd` | Account routes 23-28; profile/home routes 43-45. |
| `stage3-original-phpretro/account.php` | `4b9c7bb504fb35d138fc08daa7e32f7cfc0fa1008dcc111b1865228aaa461567` | Login submit, disabled/already-authenticated handling, errors, redirect dispatch: 18-110. |
| `stage3-original-phpretro/security_check.php` | `123e626a2677c71cc9a8160d48afdeb2b0655e123087b01fbdda8e14da4e1b6a` | Remember-token continuation and session gate: 18-61. Direct response capture is absent. |
| `stage3-original-phpretro/logout.php` | `54cf30b4e491997bce3c3bd05ac68e694cf71b44381e795caa631f68d324ac39` | Logout reasons and confirmation response: 18-70. |
| `stage3-original-phpretro/includes/session.php` | `5b70c3a1ddc796d5eb0bcad7bed0a031cc39907a46cd8661c2ef3ff9e30c82b5` | Guest/auth gate, requested URI, rank, IP mismatch, timeout: 18-53. |
| `stage3-original-phpretro/register.php` | `2eee1ae8ca4a7eb8934135e68774eb43058af1dc55ec389a5393b98acf3fa8c0` | Validation and registration writes: 18-278. Schema and transaction behavior remain UNKNOWN. |
| `stage3-original-phpretro/forgot.php` | `3971d1bc4e7888adebc3d4fd162ef31d4373c404391c7d055f18443e218c2da0` | Password reset/account-list behavior: 18-196. No dynamic capture; privacy/mail policy unresolved. |
| `stage3-original-phpretro/profile.php` | `69cfd28916e0d905eedc846d088dd0fadf20b1e6afc2cc741a6402801d7f0aa1` | Profile tabs and updates: 18-21, 28-148, 223-259. |
| `stage3-original-phpretro/home.php` | `46fe9ae0aabd409464854dc03054d3dca8a019dd9ecdb815bfd51a1d8fa0acc6` | Home lookup/visibility/edit state: 18-71. |
| `stage3-original-phpretro/me.php` | `8f890418ef6898b81c899a040b9d65f5d4a9f4dfe094fcd197d79e55f8f07886` | Authenticated personal dashboard: 18-27, 50-84. |
| `stage3-original-phpretro/habblet/myhabbo_guestbook_list.php` | `497f73e15102d2bb2fd7c4b477396cb14cafc127325d475ee011f9272f03cbd9` | List/query/delete affordance: 18-61; visible privacy gate is incomplete. |
| `stage3-original-phpretro/habblet/myhabbo_guestbook_add.php` | `ac19a23d3cd3f660b87fa20a1e39f2e7600fd6036de956853f580ab76003cb0d` | Guestbook add/private friend or group checks: 18-49. |
| `stage3-original-phpretro/habblet/myhabbo_guestbook_configure.php` | `72d29d7ec5c3005fed06833501e1779e8af4f3dace52c8380da89afbfb0e24a6` | Privacy configuration authorization: 18-37. |
| `stage3-original-phpretro/habblet/myhabbo_guestbook_remove.php` | `26b0b8024c913b78ebeee1f172adeb6b051bab49df7af3506e36089b5ae3332b` | Delete authorization and ID-based delete: 18-35; security review required. |

The accepted Go contracts are narrower than legacy source. F1/F2 establish BCrypt-compatible `$2y$` verification and opaque session-token behavior in synthetic tests (`docs/evidence/F1-password-scheme.md`, `docs/evidence/F2-account-session-review.md`). F3/F5/F6 establish explicit-column, bound-argument, read-only PolarIS adapters for the proven profile and `hotelview_news` fields (`docs/evidence/F3-profile-schema.md`, `docs/evidence/F5-content-schema.md`, `docs/evidence/F6-polaris-read-adapter.md`). `docs/rewrite-reference/Polaris-Schema-Reference.md` is a verified schema reference, not permission to select unproven fields or write rows.

Disposable capture facts

- `login_failed`: 200, 745 bytes, body SHA-256 `9d131ddf1c0deb56ecded575bbfcee879a12cf10678c6419195b11866dadc791`, headers SHA-256 `74a0ec5dcd264443c66be6dd17bf997bfbfa6af7de407f329148f7e7c4872a1c`, four deletion-cookie names, no Location.
- `login_submit`: 302, empty body SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, headers SHA-256 `48a929df39e9ad187f5422108cb8f4479cc9e7332334d187f335f045ccc731f6`, Location `http://web/security_check?page=0`, no Set-Cookie.
- `logout`: 200, 4926 bytes, body SHA-256 `0cb90dfb2de5dcbe9607988833dfa3d704793d11e565ca320ae4e6e39a17efec`, headers SHA-256 `75074161543fb6095847765c5ab8ca7cce4ddb29a10eafb964f8d9fd2246ce0e`, five deletion/session-cookie names.
- `post_logout`: 200, 10638 bytes, body SHA-256 `59f4ec34d6f77b0cdabdf589e6e1d92fc1bd336fceeaad7cf5f48bdad288a6f7`, headers SHA-256 `94e71f79bc929ea4799aeeffcce1a71e1d1dcab8127842b22e90c1a856880972`, login markers and one `PHPSESSID` name.
- Profile, registration, forgot, security-check/token-mode, and guestbook captures are missing or not promoted to retained evidence. Cookie values, credentials, rows, and rendered HTML are not copied. Capture facts do not establish PolarIS mapping.

Candidate units

Each row has one primary observable contract. Paths are proposed future paths, not currently authorized edits.

| ID / readiness | Observable contract and evidence | Proposed code/test/doc scope | Gates, negative tests, ownership, review, cap, stop, acceptance |
| --- | --- | --- | --- |
| F31 `unfilled` | Account lookup/hash verification is already implemented and evidenced by F1/F2/F6; the F18-F30 proposal owns the public login transition at F22. No additional observable boundary is defensible here. | Intentionally no paths. | Retain adapter and verifier tests under their accepted F1/F2/F6 contracts; do not relabel them as a new unit. Reopen only for a distinct account contract with new evidence. |
| F32 `unfilled` | Profile/content PolarIS read adapters, explicit columns, bound arguments, limits, and enum handling are already accepted under F3/F5/F6, while F18/F29 own their feature behavior. No additional integration boundary is demonstrated. | Intentionally no paths. | Do not duplicate accepted adapter work. Reopen only with a new source-backed adapter contract or ownership decision. |
| F33 `unfilled` | CSRF is a required security criterion for F22/F23/F25/F26/F27/F28 mutations, but no distinct F31-F45 contract can be assigned without duplicating those reserved proposals. | Intentionally no paths. | Fold the CSRF acceptance criteria into the owning F18-F30 unit; do not create a second numbered security implementation. |
| F34 `unfilled` | Return-target validation is part of the reserved F22/F27 auth/session contracts, not a separate observable unit in this lane. | Intentionally no paths. | Fold open-redirect negative tests into the owning proposal; reopen only with a distinct source-backed boundary. |
| F35 `owner/security/schema gate` | A website-owned mutation and its audit record commit atomically, including authorization, CSRF, validation, prepared SQL, and injected audit failure. This is a new audit integration, not F21 profile settings or F25 registration. | Future `internal/audit/**` plus one explicitly selected website-owned package; `tests/**`; `docs/evidence/F35-audit-transaction.md`. | Coordinator chooses mutation, schema, actor fields, and transaction boundary. Negative: unauthorized, invalid, SQL failure, audit failure, partial commit, replay. Backend after gate; independent security reviewer. 32k / 135m. Stop on schema/audit ambiguity. Accept atomic synthetic store tests and no production enablement. |
| F36 `owner/security/schema gate` | Staff enrollment binds one approved TOTP secret to one staff identity without exposing it, and enrollment is denied to disabled/unauthorized staff. This is separate from F25 registration and F27 public token/session behavior. | Future `internal/staff/**`, `internal/audit/**`; `tests/**`; `docs/evidence/F36-staff-enrollment.md`. | Coordinator owns staff identity, secret protection, recovery, authorization, and audit schema. Negative: unauthorized, disabled, duplicate, leaked secret, DB failure. Backend after gate; independent security reviewer. 32k / 135m. Stop on absent staff schema or production credentials. Accept synthetic secrets only, atomic audit, no seeded admin. |
| F37 `owner/security gate` | Staff step-up validates a real per-staff TOTP code within an approved time window and binds success to the intended staff session. | Future `internal/staff/**`, `internal/session/**`; `tests/**`; `docs/evidence/F37-staff-step-up.md`. | Coordinator approves step-up scope, skew, rate limits, and failure response. Negative: missing, disabled, malformed, wrong, expired, wrong-user, and DB-error cases. Backend after F36; independent security reviewer. 32k / 135m. Stop on shape-only validation or absent per-staff secret. Accept library-backed synthetic tests and session binding. |
| F38 `owner/security/schema gate` | A previously accepted TOTP time step cannot be accepted again for the same staff identity, including concurrent submissions; replay state is durable rather than cache-only. | Future `internal/staff/**`, `internal/session/**`; `tests/**`; `docs/evidence/F38-totp-replay.md`. | Coordinator owns persistence and compare/update locking. Negative: same-step replay, race, adjacent allowed step, expiry, wrong staff, outage. Backend after F36/F37; independent security reviewer. 28k / 120m. Stop on missing replay schema or non-atomic update. Accept race tests and durable-state proof. |
| F39 `unfilled` | Audit redaction is a criterion of the new F35 mutation contract, while profile read is already reserved by F18; no independent F39 contract is defensible without double-counting. | Intentionally no paths. | Keep redaction and audit-event assertions inside F35 or a later owner-approved staff unit; do not duplicate F18. |
| F40 `unfilled` | No distinct source-backed unit remains after excluding F18/F19 profile-home, F22/F23 login/logout, F25/F26 registration/recovery, F27 token/session, F28 guestbook, and F29 content. | Intentionally no paths. | Do not fabricate a renamed auth/profile/content candidate. Reopen only with a new source-backed observation and unique scope. |
| F41 `unfilled` | No distinct source-backed unit remains. Website-owned mutation behavior and its audit-event/redaction criteria are represented together by F35. | Intentionally no paths. | Requires new evidence or an owner-approved decision that is not a subdivision of F35. |
| F42 `unfilled` | No distinct source-backed unit remains. Staff enrollment/step-up/replay are separately represented by F36-F38. | Intentionally no paths. | Do not split one TOTP observation into additional units. |
| F43 `unfilled` | No distinct source-backed unit remains. CSRF and redirect-policy criteria belong inside the owning F18-F30 auth/session or mutation proposal, with audited-mutation enforcement in F35 where applicable. | Intentionally no paths. | Requires a new observable contract, not another negative case for the reserved F18-F30 units or F35. |
| F44 `unfilled` | No retained capture or verified ownership evidence supports another core backend/security contract in this range. | Intentionally no paths. | Stop pending fresh source/capture/schema evidence. |
| F45 `unfilled` | Guestbook privacy/read/write is reserved by F28; the source-level delete/list authorization concern cannot be safely promoted into a second unit. | Intentionally no paths. | Keep the concern as a F28 security gate; do not duplicate it here. |

Shared delivery criteria

- Every implementation proposal must be split from evidence recovery and from production enablement. A passing synthetic test does not establish deployed PolarIS rows, capture parity, or permission to ship.
- Any unit touching authentication, sessions, CSRF, TOTP, audit, privacy, ownership, or staff operations remains coordinator-owned for the decision and requires independent security review. Backend owns only the bounded implementation after the gate.
- Proposed paths above must be reconciled against the live board before dispatch. No raw PHP, rendered HTML, cookie jar, credential, real user row, migration, production handler, or runner change belongs in this lane.
- Each future card must pin the accepted base SHA, exact path scope, evidence inputs, negative tests, cap, and stop conditions; it must run the applicable Go/React checks, `git diff --check`, and a secret scan.
- F31-F45 currently provide candidate designs only. No unit is `code-ready`; F35-F38 additionally require explicit owner/security/schema decisions before proposal acceptance, while F31-F34 and F39-F45 are explicitly unfilled.

Explicitly unfilled or deferred scope

- No additional F31-F45 slot is available for registration writes, password-reset mail/account enumeration, CMS/admin mutations, client handoff, emulator writes, Pixel63, Atom, SWF, production enablement, or runner changes. Those topics are either outside this card's authorization or require separate source-backed proposals.
- The observed legacy guestbook delete-by-entry-ID behavior is not accepted as a desired contract. It is a security finding and a stop condition until owner, widget, and entry authorization are independently specified.
- Runtime database rows, deployed schema variants, session-cookie provenance, direct security-check responses, profile/guestbook captures, staff records, and audit-table ownership remain `UNKNOWN` where not cited above.

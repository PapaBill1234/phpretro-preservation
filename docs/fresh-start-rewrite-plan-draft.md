# Fresh-start rewrite plan draft

> Superseding note (2026-10-04): This planning draft preserves historical approval and production-gate wording below; those statements are not current policy. The project is development-only with no production environment, and authentication, sessions, cookies, CSRF, audit-event design, schema, migrations, and dependent units are open for development under exact briefs, independent review, and CI. The owner gives no approvals. Production enablement, real credentials, secrets or key material, real user data, live outside systems, and weakening review, CI, branch-protection, or approval gates remain closed.

Status: planning draft. The repository and monitoring/tooling baseline now exist; implementation remains blocked until the readiness gates and supervised work-unit batch are approved.

Jev/cost revision: Jev is a typed routing and triage aid, never an authority for schema ownership, authentication, authorization, security approval, production enablement, merge approval, or runner permissions. Keep Jev calls small and batched, include `none of these`, record confidence and source verification, and stop delegating below 0.80 confidence, on `escalate`, unavailable responses, or disagreement with source. Compare Jev-assisted and matched Sol-only units by cost per accepted unit, input/cached/output tokens, wall time, retries, and error rate after ten accepted units. The A6API collector and PowerShell summaries are operational evidence only; configuration is never evidence of savings.

## 1. Purpose and authority

Build a non-commercial preservation and hobby replacement for original `Quackster/PHPRetro`. Reimplement behavior, routes, validation, permissions, session effects, visible output, and database effects from original source and disposable golden captures. Do not copy original PHP code and do not use PHPRetro-PDO as the behavior source.

Authorities:

- Original `Quackster/PHPRetro`: behavior, routes, templates, edge cases, and golden target.
- PHPRetro-PDO: security ideas only: prepared statements, CSRF, output encoding, audit, and password handling.
- PolarIS: hotel storage and the supported hotel profile.
- Octane: the PolarIS-compatible emulator/client integration whose schema and handoff behavior must be verified separately.
- Pixel63: isolated optional profile with its own identity, schema, permissions, credentials, client, and protocol.
- Holograph: dropped.

Map only what original source, golden capture, or profile source proves. Preserve `UNKNOWN`; never infer shared identity, table ownership, or behavior from similar names.

## 2. Proposed technical direction

The proposed backend is **Go**. The frontend is **React** and is the required presentation layer for every supported theme. Go exposes typed HTTP/API contracts; React owns theme rendering, client interaction, and browser navigation. Server-rendered Go templates are not the theme architecture.

Minimal starting stack:

- Go standard library first (`net/http`, `html/template`, `database/sql`, `crypto/*`, structured standard logging where sufficient).
- MariaDB only, accessed through parameterized queries and named services.
- React frontend with a typed API boundary, shared component contracts, and every theme implemented as a React theme package; no theme may introduce a separate server-rendered template runtime.
- Redis is a required operational component for cache/session-support workloads where the relevant contract is approved; MariaDB remains the system of record. Redis keys, TTLs, serialization, invalidation, outage behavior, and whether a record is cache-only or session-critical must be specified and tested per slice.
- Localization is a first-class website capability: supported languages, fallback rules, translated labels/content, locale-aware URLs or selection state, and cache variation must be explicit and testable. Housekeeping must provide a safe language-management workflow without allowing arbitrary template or code execution.
- Database-backed sessions using opaque random tokens, separate public/staff records, expiry, logout, fixation resistance, and secure cookie attributes.
- Docker Compose only for disposable development/CI and a reproducible MariaDB test fixture.
- Go tests, integration tests, browser contract tests, and `go test -race` where applicable.

Deferred until their own evidence and acceptance slices: nginx, metrics, fuzzing, background queues, theme publish/rollback UI, and the Atom adapter. React and Redis are not deferred technologies; their production contracts and staged implementation remain gated by bounded work units. Add dependencies only through a recorded decision and measured need.

The setup plan installs a pinned Go toolchain on the VPS before any build work. GitHub Actions runs `go test`, `go test -race`, `govulncheck ./...`, and a license scan over direct and transitive modules from the lock/sum files. CI fails on an unpinned or vulnerable dependency, an incompatible license, or a missing scan result.

### Pre-approved dependencies

The initial foundation may use only these non-standard dependencies:

- one maintained MariaDB/MySQL Go driver, selected and pinned before implementation;
- `golang.org/x/crypto` for password-hash verification and migration support;
- `github.com/pquerna/otp` at a pinned release, a maintained Go TOTP implementation with RFC 6238 support and provisioning helpers, licensed Apache-2.0.

Agents must not hand-write cryptography, password hashing, TOTP, token generation, or verification primitives. Any version change or additional dependency requires a recorded decision and evidence.

### Presentation architecture

React is mandatory for all themes, including the PHPRetro-compatible theme and the modern Habbo-style theme. Each theme is a versioned React package that consumes restricted, typed, escaped view models from the Go API. Themes may change presentation, CSS, assets, typography, layout, and named component variants, but may not access databases, identities, secrets, sessions, permissions, CSRF state, audit mechanisms, arbitrary filesystem/process/network capabilities, or alter route/security behavior.

The API must preserve the measured original method/status/redirect/cookie/body contracts even when the browser presentation is React. Browser contract tests must cover initial loads, redirects, cookies, failure states, navigation, and progressive enhancement or explicitly documented unsupported behavior. React introduces a second runtime contract, so typed API schemas, fixture-driven component tests, browser tests, and golden output markers are mandatory rather than optional.

Go remains a proposed choice, not a measured speed claim. The foundation slice below has a time and cost cap.

## 3. Core architecture and security

Named services include `AccountService`, `SessionService`, `ProfileService`, `ContentService`, `AuditService`, and profile-specific adapters. Handlers validate, authorize, call named services, and render a template or documented response; they do not contain raw PolarIS SQL. Website-owned `phpretro_*` tables remain separate from PolarIS tables.

### Carried-over release requirements

- A non-disposable start must not expose a reachable seeded administrator. Disposable fixtures may create synthetic administrators only inside isolated test environments.
- A sensitive write and its audit record must commit together or both fail. There is no exception or deferred-audit escape hatch.
- Private guestbook reads must enforce owner/friend privacy in the service layer, including direct-ID and unauthenticated attempts.
- Staff 2FA must verify an enrolled per-staff secret. A code with the right length or shape is never success.

### Legacy vulnerability classes not to reproduce

- SQL injection from concatenated queries; all SQL is parameterized.
- XSS from inconsistent or context-wrong output escaping; templates use context-appropriate escaping and typed view data.
- Missing or unreliable CSRF on mutations; every state-changing form/endpoint requires a session-bound token.
- IDOR and arbitrary profile targeting; identity and ownership derive from the authenticated session and explicit policy.
- Session fixation, unsafe cookie attributes, plaintext/weak password storage, token leakage, open redirects, unsafe file/media paths, privilege confusion, and sensitive data in logs.

- Every sensitive mutation has validation, authorization, CSRF, prepared SQL, context-safe rendering, and an audit row in the same database transaction. No documented failure contract substitutes for atomic write plus audit. Registration, payments, client handoff, staff operations, and emulator writes remain outside the current bounded work until their decision gates, negative tests, audit behavior, and independent review requirements pass.

## 4. First-release slices and automated golden contracts

Golden captures are automated CI contract tests, run against disposable original-PHPRetro and rewrite fixtures. Pin the original PHPRetro checkout to commit `8ab8f81e6bcd09fc661547cb032ef045149c095e`. The local PHP 5.6 Apache fixture resolves to `php@sha256:0a40fd273961b99d8afe69a61a68c73c04bc0caa9de384d3b2dd9e7986eec86d`; CI must use that immutable digest (or fail closed if the runner cannot fetch it), never a moving tag. Record the resolved image digest. Compare route, method, status, redirect chain, cookies, selected headers, body markers, normalized HTML where appropriate, and response hashes where stable. Differences must be classified as intentional with evidence; a green unit test alone does not replace the golden contract.

Implement in this order:

1. **Account/session foundation.** First task: verify the PolarIS password-hash scheme from CleanDB/schema, real rows, and the original login source before choosing the Go verifier or upgrade path. Then implement public page, login, failed login, successful login, logout, guest behavior, expiry, and PolarIS user lookup. Translate disposable capture fixtures from the Holograph-era capture schema into the verified PolarIS schema through an explicit mapping script; reject unmapped fields rather than guessing.
2. Existing-user profile read using only schema-proven fields.
3. One website-owned article/archive content read from original behavior.
4. One authorized website-owned mutation with same-transaction durable audit and an injected audit-failure test.
5. Staff enrollment and real per-staff TOTP/step-up failures: missing, disabled, malformed, wrong, expired, wrong-user, and database error.
6. Personal guestbook read with owner/friend privacy enforcement.

Each slice requires source route evidence, request/response contract, ownership map, translated fixtures, browser flow, negative authorization cases, and explicit unsupported/`UNKNOWN` entries.

The TOTP library validates time-window codes but does not maintain application replay state: its `Validate`/`ValidateCustom` API checks a code against time counters and skew. The staff TOTP slice must persist the last accepted time-step (or an equivalent one-use record) per staff member and reject a second use of the same accepted step, with tests for replay, skew, expiry, and concurrent submissions.

## 5. Modular themes and CMS

Every theme uses a restricted, versioned React theme manifest: API version, component entry points, assets, capabilities, compatibility, and typed view-model versions. A theme cannot execute server code, access databases, identities, secrets, sessions, permissions, arbitrary JavaScript beyond its reviewed bundle, or unsafe HTML. Validate package paths, routes, URLs, media, ordering, role visibility, sizes, dependencies, and bundle capabilities server-side and in CI.

The PHPRetro theme preserves measured original markup, copy, routes, and behavior. The modern Habbo-style theme ports the supplied visual assets and appearance into templates; it does not execute the reference site's application code. Source path: `C:\Users\Karim\Documents\Codex\2026-09-14\phpretro-continuation-handoff-current-state-repository\ay\modern-assets`. Preserve original logic by reimplementing it; preserve original templates, CSS, and images only where selected and recorded with provenance.

Atom is deferred. If later approved, use a restricted presentation adapter only; Atom's code/theme licensing and bundled artwork do not establish permission or direct compatibility.

Adding a theme must require a manifest, validated React bundle, typed view-model compatibility, and provenance-checked assets, not core route rewrites. Theme publish/preview/rollback UI is deferred from the minimal start. Theme selection cannot change route behavior, database ownership, hotel profile, identity, sessions, CSRF, authorization, or audit.

### Housekeeping and website management

Housekeeping is the authenticated administration surface for managing the website, not merely a hotel-operations dashboard. It must use the same React theme system and a dedicated housekeeping visual theme/component set. Its capability model must be explicit and server-enforced; the frontend cannot grant permissions by hiding or showing controls.

The CMS management boundary will cover, through separately accepted slices:

- language/locale configuration, translation catalogs, fallback order, and activation;
- page creation and editing for new button pages, with stable page identifiers, published/draft state, ordering, and route-safe slugs;
- navigation and button management, including label, destination, visibility, ordering, locale variants, and theme-compatible presentation metadata;
- news/articles, FAQs, banners, landing sections, and other website-owned content proven by source or deliberately introduced as new website-owned schema;
- theme settings that are presentation-only, with typed validation, preview, audit, and rollback;
- media/provenance metadata and safe asset selection, without arbitrary file paths or executable uploads;
- website status, maintenance messaging, cache invalidation, audit history, and bounded operational settings.

Every mutation requires authentication, authorization, CSRF protection, validation, prepared SQL, same-transaction audit, and golden/negative tests. Housekeeping must never edit PolarIS-owned tables unless a separate ownership and migration decision explicitly permits it. Configuration changes must be versioned or auditable, and failed publication must not partially activate a theme, locale catalog, page, or navigation change.

## 6. PolarIS and Octane

PolarIS is the hotel storage and first supported profile. Octane is the emulator/client implementation used with that PolarIS profile; it is not a replacement for PolarIS ownership and it does not authorize the website to invent or alter emulator schema. Build a verified adapter for login, profile lookup, permissions, client entry, tickets, expiry, and failure behavior. The website owns its session and audit semantics.

Client entry is unsupported until end-to-end handoff, expiry/replay, non-loopback HTTPS, cookie, asset, and provenance checks pass. No PolarIS-owned table changes occur without verified emulator evidence and an explicit migration decision.

## 7. Pixel63 support

Pixel63 is an optional separately configured profile, not a table mapping behind a toggle. Reference path: `C:\Users\Karim\Documents\Codex\2026-09-14\phpretro-continuation-handoff-current-state-repository\ay\pixel63`.

Support requires a profile adapter and capability matrix for UUID identity, bcrypt login, JWT/token transport, permissions, currencies, client WebSocket handoff, schema, assets, logout, and expiry. Current evidence does not prove a safe CMS handoff or shared session/CSRF/audit design, so Pixel63 login, account mutation, and client launch remain unsupported until separately verified. The alternate `...repositorof code` path was not found and is not used.

## 8. Flash/SWF replacement

Flash replacement is **not committed to the autonomous plan and is out of scope for autonomous agents**. Any future human-approved milestone would inventory SWFs, inspect behavior in isolation, define an HTML5/WebGL/Canvas contract without Ruffle, and port one measured interaction before broader work. Do not invent emulator writes or copy unproven assets.

## 9. Go foundation slice: cap and stop rules

The foundation slice is limited to password-scheme verification, one account/session flow, one profile read, one content read, translated fixtures, and their golden CI contracts. Cap it at **10 working days and the foundation token cap recorded in `DECISIONS.md`**; no payment or paid-service spend is authorized by this plan. Each unit also has its own token cap recorded in `DECISIONS.md`. Measure input, cached-input, and output tokens from session logs; derive dollars afterward from the merchant's listed prices. Record wall time, retries, and accepted/parked status.

Stop immediately for missing credentials/authority, a payment/quota/auth failure, a second stream failure, a detected secret, guessed schema, production data access, or a destructive action. Stop after two materially similar failures, two failed fixes, five total verification failures, or a red/unexplained CI result after two attempts. Stop when a unit cap or the foundation cap is reached, when no measurable parity/progress is produced in two successive work units, or when the next action is a decision gate. Park unresolved mappings as `UNKNOWN`.

## 10. Delivery and decision gates

- 1. Record the repository name `phpretro-preservation`, visibility, access, and evidence transfer list.
2. Run the capped Go foundation slice and review its measured result; confirm or reject Go.
3. Complete the first-release security and golden-contract slices.
4. Add PHPRetro and modern themes after provenance review; defer Atom until separately approved.
5. Gate PolarIS/Octane client entry and Pixel63 independently.
6. Keep SWF replacement outside autonomous scope unless separately approved.
7. Near release, run fresh-session Claude Opus 5.5 then Fable 5.1 reviews. Label the result **AI-reviewed (Opus 5.5 and Fable 5.1), not human-reviewed**.

Until these gates are recorded, this remains a plan draft. No Go spike, C++ change, policy-file change, branch, repository creation, asset import, or push is authorized by this document alone.

## 10a. Agent access and branch/ruleset policy

The proposed repository is `phpretro-preservation`, owned by the user's GitHub account and public. Agents use a fine-grained GitHub token scoped to that repository only, with no organization or repository administration rights. The token may push only to `auto/*` branches and the `integration` branch; it may not push to `main`, alter rulesets, manage collaborators, create releases, or change repository settings.

`main` is the default branch and contains the scope-guard workflow, the worker-immutable policy reference, and a README linking to `integration`. `main` accepts changes only through pull requests with required reviews/checks. `integration` is the working branch and is governed by a repository ruleset: force-pushes and deletion are blocked, the scope check is required, and pull requests are not required there. `main` moves only to tagged milestones after the fresh-session Opus 5.5 and Fable 5.1 reviews.

The scope check and oversized-deletion guard run in CI from a policy file stored on protected `main` and fetched at a pinned `main` ref by the workflow. Workers cannot push to `main`, change rulesets, or alter repository settings, so the authoritative policy cannot be changed by their token. A policy change requires a protected-main pull request and review. The policy rejects unauthorized paths, force/deletion behavior, secrets, and diffs deleting more than 10 files or 500 net lines.

### Batch scope approval

Before autonomous work, Sol writes one plain-language list of the next 5–10 units, each with exact file scope, evidence inputs, tests, done criteria, stop conditions, and its unit token cap. Sol opens one scope-approval pull request to `main`. The user reviews and merges that PR. Agents may work only on units listed in the merged approval; a new unit or changed file scope requires another batch PR to `main`. Agents cannot push that PR to `main`, edit the policy, or approve their own scope. The policy file records the approved unit identifiers and exact path globs; CI rejects work outside the merged list.

## 11. Agent roles and delegation

- **Sol (`gpt-6.1-sol`)** coordinates: writes briefs and acceptance criteria, resolves schema/ownership/evidence contradictions, reviews diffs and tests, integrates by exact SHA, and updates status. Security-sensitive criteria for auth, sessions, TOTP, audit, privacy, ownership, secrets, and runner configuration remain Sol-only.
- **Luna A and Luna B (`gpt-6-luna`)** implement one bounded unit per fresh session in separate worktrees. For high-risk units, Sol first writes the acceptance criteria and negative cases; Luna implements from that brief; Sol reviews the diff and tests; then a fresh session performs the feature-boundary review. If Luna fails twice on the same high-risk unit, Sol may write the implementation, but a fresh session must review it afterward; Sol is never both the final writer and final reviewer.
- Each brief names the base SHA, exact file scope, evidence, behavior, tests, done criteria, stop conditions, and the unit token/dollar cap from `DECISIONS.md`.
- The delegation gate is code-first: Sol-only tasks stay with Sol; a declared low/medium-risk scope goes to Luna; ambiguous tasks get one batched typed routing judgment when available, followed by source verification. A child whose actual session model is not `gpt-6-luna` is aborted and recorded.
- Luna commits small finished work to `auto/*`, pushes only that branch, and reports focused tests. Two failed attempts park the unit; Sol may sharpen the brief once, but does not silently redo the Luna unit.
- No autonomous agent may implement Flash/SWF replacement, production registration, payments, client handoff, staff operations, Pixel63 support, Atom integration, theme publish/rollback UI, or Redis/nginx/metrics/fuzzing work during the minimal start.

## 12. Token and review efficiency

Keep stable instructions and short briefs. Maintain a generated repository map and review packets containing base/head SHAs, changed paths, diffstat, test results, CI status, warnings, and A6API token counts. Store long logs in files and expose only relevant failures or classified summaries. Record per-unit input, cached-input, output tokens, wall time, retries, and accepted/parked status. The headline measure is cost per accepted unit.

## 13. Jev routing

Use Jev only for cheap typed judgments that rank candidates before reading: candidate-file discovery with five or more candidates, log classification, legacy-file ranking, delegation routing, plausible-cause ranking, diff-hunk triage, and claim checks. Batch related questions, include a `none of these` choice, and verify the selected source afterward. Only the user's real A6API, OpenRouter, TypeSafe, and GitHub keys are off-limits; synthetic credentials, configs, and logs are allowed when they contain no real secrets. Helper scripts should gather candidates and call Jev so use is reproducible rather than discretionary.

At session start, attempt the required no-op availability check only when the MCP tool is actually exposed. The current check was exposed and succeeded; `codex mcp get jev --json` confirms `jev_judge` and `jev_gate` are enabled, and the global `PreToolUse` hook invokes `jev-use ... hook gate`. Treat the gate as a safety check that does not replace ordinary Codex permissions or prove savings. Sample consequential Jev answers against source. After ten accepted units, compare measured cost per accepted unit and error rate; retain Jev routing only where matched evidence shows benefit. The wrapper records output tokens but estimates cost from input tokens only, so output billing remains unverified.

## 14. Autonomous operation and hard stops

A future Goal runner may pull bounded units from `tasks/queue.md` with statuses `ready`, `running`, `review`, `accepted`, `parked`, or `blocked`. Autonomous running begins only after the new repository, access controls, branch protection, CI policy, and initial queue are approved. The first foundation slice is supervised; no unattended runner may advance it. Agents push only `auto/*`; Sol integrates to the default `integration` branch, and nothing writes to `main` automatically. `docs/ai-run-state.md` is updated at every unit boundary; `STOPPED.md` records a halted run and exact next step; `DECISIONS.md` records each open question with a recommendation and default.

Stop after a payment/quota/auth failure, a second stream failure, a detected secret, two materially similar failed fixes, unexplained red CI after two attempts, guessed schema, an open decision dependency, scope outside this plan, production enablement of registration/payments/client handoff/staff operations, a destructive migration, or an oversized deletion. If no independent unit is ready, stop and report the decision required. A unit without a commit or status change within 45 minutes is stopped. These rules are subordinate to the stricter 10-day foundation-slice cap above.

Every unit must have a token cap in `DECISIONS.md`; stop at that cap. Measure usage from session logs and derive dollars from merchant-listed prices. The runner also stops on an actual A6API payment, quota, or authentication failure, even if a unit or foundation cap remains. The foundation slice has its own separate token cap and cannot borrow unused allowance from later units.

## 15. Monitoring

The new repository and integration branch should expose commit and CI status, `ai-run-state.md`, `STOPPED.md`, and `DECISIONS.md`. Check whether A6API exposes balance or usage through an API before autonomous work; stop below the user-provided threshold when one is set. Do not infer spend or savings from configuration alone.

## 16. Decision gates

The user decides: confirmation of Go after the capped foundation-slice report; creation of public repository `phpretro-preservation` under the user's account; the per-unit and foundation token caps and any optional A6API spending cap in `DECISIONS.md`; the first PolarIS/Octane adapter scope; Pixel63; the SWF replacement; and the final Opus 5.5 then Fable 5.1 reviews. Code is GPL-3.0 and preserved assets stay in the same repository with a provenance file. Autonomous work proceeds only after repository approval and only on units not blocked by these gates.

### Proposed `DECISIONS.md` additions

These entries are draft content and have not been written as a file:

- **Repository:** `phpretro-preservation`, public, owned by the user's GitHub account; `main` is default and `integration` is the working branch.
- **License/assets:** GPL-3.0 code; selected original templates, CSS, images, modern assets, and later Atom-derived presentation remain in the same repository only with per-file provenance, source, retrieval date, hash, creator, and terms. No asset license is inferred from the code license.
- **Dependencies:** pinned `github.com/go-sql-driver/mysql`, `golang.org/x/crypto`, and `github.com/pquerna/otp` (Apache-2.0); exact versions and transitive license inventory are a supervised foundation task.
- **Production limits:** no registration, payments, client handoff, staff operations, or emulator writes until their decision gates, negative tests, atomic audit behavior, and reviews pass.
- **Autonomy:** autonomous operation starts only after repository/ruleset/CI approval; the first foundation slice is supervised.
- **A6API:** the checked-in collectors and reports record request usage, rates, estimated cost, Jev calls, and cost per accepted unit. Stop on an actual provider payment/quota/auth failure. No fixed balance floor is required; an optional user-defined spending cap may be added later. Provider telemetry remains authoritative.
- **Stage 3 UNKNOWNs:** host port `18081` remains unverified/unlistening; `/account/logout_ok` remains a PHP 5.6 compatibility fatal; direct internal capture and `/logout.php` are the verified fallback. Do not treat either UNKNOWN as resolved.

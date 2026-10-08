# Coordinator-approved restart contracts — 2026-10-08

The repair authorizes the following bounded development work. It supersedes
historical "owner decision required" wording for these exact contracts only.
Use synthetic/disposable rows and local files. No credentials, live sites,
external writes, real users, emulator writes or production activation.
Every delivery still needs the scope, tests, quality and exact-head review gates.
Each unit has the existing 3,000,000-token all-role cap and four-launch ladder.
The expected builder is Luna; first review is DeepSeek. Sensitive changes also
need the existing independent second-review gate. Do not fill a reserved,
explicitly unfilled design card just to make the queue larger.

## F61 — Public profile request and store injection

Observed defect: internal/server/server.go hardcodes profile ID 1 and embeds
profileFixtures. internal/profile/profile.go already has the read-only Store
interface; internal/polaris/store.go implements it over six explicitly selected
columns. Field authority is docs/evidence/F3-profile-schema.md, not the demo row.

Scope: internal/server/profile_handler.go, internal/server/profile_handler_test.go,
internal/server/server.go, internal/server/server_test.go,
docs/evidence/F61-profile-http.md and docs/units/F61.md. Size M; depends on F18.

Keep New() as a clearly documented demo constructor for existing smoke checks.
Add an explicit constructor accepting profile.Store, with no database opens.
GET /api/profile accepts exactly one positive decimal id or trimmed username
(1-32 ASCII letters/digits/underscore/hyphen). Missing, ambiguous, duplicate,
invalid or overlong selection returns 400 before calling the store. A known
missing profile returns 404; unavailable/nil store or malformed stored row
returns 503 with a generic error. Success uses the existing profile.v1 public
fields, never an account/password/full SQL row. tab remains the existing view
normalization. No authentication, session, schema, SQL or write changes.

Tests must prove two independently selected profiles, exact store calls, no
store call for invalid inputs, failures without private fields, and unchanged
demo smoke behavior. Tests: go test ./internal/server/... ./internal/profile/...
and bash scripts/check.sh. Stop on needing private data or wider policy.
This is a new HTTP contract over source-backed fields; capture fidelity is
unverified and must not be reported as legacy capture parity.

## F62 — React public profile loads from the API

Observed defect: frontend/src/main.tsx builds DemoUser in the browser without a
request. frontend/src/profile/viewModel.ts already validates profile.v1.
Authority: this contract plus docs/evidence/F3-profile-schema.md public fields.
Scope: frontend/src/main.tsx, frontend/src/profile/ProfileLoader.tsx,
frontend/src/profile/loadProfile.ts, frontend/tests/profile-loader.test.ts,
docs/evidence/F62-profile-loading.md, docs/units/F62.md. Size M; depends on F61.

The public profile section fetches a relative same-origin /api/profile URL for
the selected id/username. Provide explicit loading, empty-selection, not-found
and unavailable states; validate the JSON with acceptProfileViewModel before
rendering. An abort/stale response cannot replace the newest selection.
React text rendering escapes values. Never substitute DemoUser on API failure.
Other sections that still use fixtures retain explicit demo labels. No auth,
new theme, dependencies, external URLs or cookies beyond same-origin requests.
Tests use injected fetch responses and independent DTOs, covering successful
selection, error status, malformed DTO, stale/aborted responses and no fallback.
Tests: cd frontend && npm test && npm run typecheck && npm run build;
bash scripts/check.sh. Stop before any API/schema expansion. fidelity: guessed.

## F63 — Serve built frontend assets

Observed defect: the root page references /frontend/src/main.tsx, which Chrome
cannot execute as built JavaScript and the server does not serve as an asset.
Authority: this new development hosting contract, existing frontend/package.json
Vite build and server root route. Scope: internal/server/assets.go,
internal/server/assets_test.go, internal/server/server.go,
internal/server/server_test.go, cmd/phpretro/main.go,
docs/evidence/F63-built-assets.md, docs/units/F63.md. Size M; depends on F62.

Accept an injected fs.FS containing the Vite dist tree; runtime reads a
PHPRETRO_FRONTEND_DIST directory chosen by the operator (default frontend/dist).
Serve the built index only at / and declared static assets under /assets/;
missing build returns 503 with a build instruction, rather than a blank app.
Do not serve source, .env, directories or unrelated files, follow symlinks out
of the selected tree, or allow traversal. API routes remain registered first
and unknown routes remain 404. MIME types are correct and HEAD is supported.
Use Go stdlib; no downloaded assets or automatic npm installation at runtime.
Keep the explicit demo smoke constructor usable without a built tree; runtime
uses the asset-enabled constructor. Tests use a small injected build fixture,
assert real index/JS bytes, and negative traversal/dotfile/unknown/API cases.
Tests: go test ./internal/server/...; frontend npm test/typecheck/build;
bash scripts/check.sh. No claim of capture verification.

## F49 — Approved synthetic catalog package promotion

This is distinct from F8's lookup: validate a release package before activation.
Scope: frontend/src/localization/catalogPackage.ts,
frontend/tests/localization-package.test.ts, docs/evidence/F49-locale-catalog.md
and the promoted child's own docs/units note. Use one small child (F49a if free).
The package is a typed, data-only value with version catalog-package.v1,
contentVersion home.v1, defaultLocale en, locales en/fr, declared keys exactly
siteTitle/welcome/navigationHome (frontend/src/localization/index.ts), and locale entries represented as a list so
duplicate locales/keys can be detected. All keys must be declared exactly once
per locale; values are strings (empty strings are allowed). Reject unknown
versions/locales, duplicate/incomplete/unknown keys, non-string/executable
values and route/auth/capability fields. Return validated data without
persistence, activation, signing, network requests or cache writes. Preserve
F8's existing fallback tests. Acceptance and tests must use independent package
fixtures. Tests: frontend npm test/typecheck/build and scripts/check.sh.
Missing production signing/activation decisions do not block this validation
unit, but remain outside its scope. fidelity: guessed.

## F38 — Durable replay architecture decision, preserved unit history

The owner block is removed: choose a development-owned MariaDB table
website_staff_totp_used_steps with a binary staff identity (64 ASCII identifier
characters maximum), a nonnegative BIGINT step and a unique (identity,step)
primary key. One atomic insert reserves a pair. Only a confirmed duplicate-key
result means replay; connection, permission or other SQL errors fail closed.
Retain pairs for this development stage; no expiry deletion that permits reuse.
The injected ReplayStore interface remains the boundary; no implicit live DB
connection. Adapter tests must prove persistence across guard instances,
concurrent same-pair acceptance exactly once, separate identities/adjacent steps,
and outage denial, plus a disposable MariaDB integration test before calling
it durable. No real credentials, staff data or database migration execution.
Existing F38 PR #66 is preserved for review; its conflicting implementation
must not auto-recover or merge. Its recorded attempts/tokens are retained.
Implementation remains ineligible until that bounded adapter and required
independent sensitive-path review can be provided; this is a technical gate,
not an owner approval request. Other ready work continues.

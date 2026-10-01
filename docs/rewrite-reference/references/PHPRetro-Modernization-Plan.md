# PHPRetro Modernization Plan
**Target:** PHP 8.3, PDO + prepared statements, CSRF protection, hardened auth, production-ready.
**Source:** https://github.com/Quackster/PHPRetro (2009-era PHP4/5 codebase)

---

## How to use this document
This is written to be handed to an executing model (e.g. DeepSeek) phase-by-phase, with a
human or a second reviewing model (Claude) checking output between phases. Each phase has:

- **Goal** — what "done" looks like
- **Scope** — exact files/folders touched
- **Tasks** — concrete steps
- **Conventions** — rules the executor must follow (critical for consistency across phases,
  since different phases will likely be done in separate sessions/models)
- **Deliverable to reviewer** — what the executor should produce/report back, kept minimal
  on purpose so the reviewer doesn't have to re-read the whole diff to sanity-check it
- **Acceptance check** — how the reviewer verifies the phase before moving on

**Do not start a phase until the prior phase's acceptance check passes.** Each phase assumes
the previous phases' conventions are already in place.

---

## Global conventions (apply to every phase)

- **PHP version target:** 8.3. No `mysql_*`, no `get_magic_quotes_gpc()`, no old-style
  constructors (`function ClassName()`), no `var $x` — use typed properties.
- **DB access:** one new class, `Database` (PDO wrapper), replaces `$db` / `$serverdb`
  globals everywhere. No raw SQL string concatenation of variables, ever — bind params only.
- **Escaping helpers:** `HoloInput::FilterText()` is deleted once a file is migrated (it was
  an escaping shim for string concatenation; prepared statements make it obsolete). Keep
  `HoloText()` (output escaping / XSS) — that one stays and should still wrap all
  user-supplied data on output.
- **Secrets:** DB host/user/pass/salt live in environment variables (`.env` via `vlucas/phpdotenv`
  or plain `getenv()`), never committed. `includes/config.php` becomes a loader, not a value file.
- **Passwords:** `password_hash($pw, PASSWORD_DEFAULT)` / `password_verify()`. No `sha1()`.
- **Random tokens:** `bin2hex(random_bytes(n))`. No `mt_rand()` for anything security-relevant
  (session tokens, remember-me tokens, SSO tickets, password-reset temp passwords).
- **Commit granularity:** one commit per file or tightly related group of files, with a
  message like `[phase3][auth] migrate includes/classes.php HoloUser to PDO + password_hash`.
  This is what makes phase review cheap — reviewer reads commit messages + diffs, not whole files.
- **Do not "improve" unrelated code while migrating.** Scope creep is what blows up review cost.
  If something looks broken but is out of phase scope, leave a `// TODO(phaseN):` comment instead
  of fixing it inline.

---

## Phase 1 — PHP 8.3 compatibility pass (make it boot)

**Goal:** App runs on PHP 8.3 without fatal errors. Still uses old `mysql_*`-style DB
class internally for now (that's Phase 2) — this phase is purely "stop it from crashing."

**Scope:** `includes/classes.php`, `includes/core.php`, `includes/functions.php`, any file
using old-style constructors or removed functions.

**Tasks:**
1. Convert all old-style constructors (`function HoloUser()` inside `class HoloUser`) to `__construct()`.
2. Replace every `get_magic_quotes_gpc()` call/branch with a no-op (always `false` — this
   feature was removed in PHP 5.4+; delete the `stripslashes()` branch tied to it).
3. Replace all `mysql_*` function calls with placeholders that throw a clear
   `"not yet migrated — see Phase 2"` exception, OR stub them via a temporary shim if you
   need the app bootable before Phase 2 lands. State which approach you used.
4. Fix any `list($a, $b) = ...` / array-in-string / curly-brace string offset syntax removed in PHP 8.
5. Run `php -l` (lint) on every `.php` file and fix syntax errors.

**Deliverable to reviewer:**
- List of files changed
- Full `php -l` output for the whole tree (should be all "No syntax errors detected")
- List of any function/pattern you weren't sure how to migrate (flag, don't guess silently)

**Acceptance check:** `find . -name "*.php" -exec php -l {} \;` returns zero errors across
the whole repo.

---

## Phase 2 — PDO database layer

**Goal:** New `Database` class (PDO, prepared statements) exists and is a drop-in-ish
replacement for the old `$db`/`$serverdb` query pattern, but **nothing calls it yet** —
that's Phases 4-6. This phase is just building and unit-testing the tool.

**Scope:** New file `includes/Database.php`. Do not touch page files yet.

**Tasks:**
1. Build `Database` class wrapping `PDO`, with methods mirroring what the old code needs:
   - `query(string $sql, array $params = []): PDOStatement`
   - `fetchRow(string $sql, array $params = []): array|false`
   - `fetchAll(string $sql, array $params = []): array`
   - `fetchColumn(string $sql, array $params = []): mixed` (replaces old `$db->result()`)
   - `insertId(): string`
   - `execute(string $sql, array $params = []): int` (returns affected rows, for UPDATE/DELETE)
2. Constructor takes DSN/user/pass from env vars, sets `PDO::ATTR_ERRMODE =>
   PDO::ERRMODE_EXCEPTION` and `PDO::ATTR_EMULATE_PREPARES => false`.
3. All params bound positionally (`?`) or named — pick one style and use it consistently
   everywhere in the whole project (state which you chose).
4. Write a small standalone test script (`tests/db_smoke_test.php`) that connects, runs a
   trivial parameterized SELECT/INSERT/UPDATE/DELETE against a scratch table, and prints
   pass/fail. This is how the reviewer verifies the class works without reading every line.

**Deliverable to reviewer:** `includes/Database.php`, the smoke test script, and its output.

**Acceptance check:** Smoke test passes against a real (or throwaway Docker) MySQL instance.

---

## Phase 3 — Auth & session core migration

**Goal:** `includes/classes.php`'s `HoloUser`, `HoloInput::HoloHash`, session/login flow,
and remember-me/SSO ticket generation are migrated to PDO + `password_hash()` +
`random_bytes()`. This is the highest-risk file, so it gets its own phase.

**Scope:** `includes/classes.php`, `includes/functions.php` (`GenerateTicket`),
`security_check.php`, `login_popup.php`, `logout.php`, `reauthenticate.php`.

**Tasks:**
1. Replace `HoloHash()` (`sha1(pw.username)`) with `password_hash()`. Add a
   `needsRehash()`-style check on login: if a user's stored hash isn't a modern hash format,
   verify against legacy `sha1()` first, then re-hash with `password_hash()` and update the
   row — this is the standard "lazy migration" pattern, don't force a mass password reset.
2. Replace `GenerateTicket('remember'|'sso'|'random', ...)` internals to use `random_bytes()`.
3. Migrate `select1`, `select2`, `select3` (or wherever raw SQL for login lives) to
   `Database` with bound params.
4. Fix `security_check.php`'s remember-token lookup to use `hash_equals()` semantics —
   since PDO param binding already prevents injection, this is about timing-safety, not SQLi;
   note in your deliverable whether you added `hash_equals()` and where.
5. All of `HoloUser`'s constructor/methods converted to PDO.

**Deliverable to reviewer:** Diff of the files above + a short note: "legacy password
migration path: [describe exactly what happens on first login for an old sha1 user]".

**Acceptance check:** Manual test — log in with a pre-existing (sha1) test account,
confirm it upgrades to `password_hash` in the DB; log in again, confirm it works via the
new hash path.

---

## Phase 4 — Migrate top-level pages (root `.php` files, ~40 files)

**Goal:** Every root-level page (`profile.php`, `account.php`, `register.php`, `forgot.php`,
`club.php`, `discussions.php`, etc.) uses `Database` with bound params. No `FilterText()`
calls remain in these files for SQL purposes (output escaping via `HoloText()` stays).

**Scope:** All `*.php` files directly under repo root (not `includes/`, `install/`,
`housekeeping/`, `habblet/`).

**Tasks:**
1. Batch in groups of ~8-10 files per commit/report to keep review chunks small.
2. For each file: find every `->query(...)` / `->result(...)` call, convert to
   `Database` methods with `?` placeholders, remove `FilterText()` wrapping on those values.
3. **Specifically fix `forgot.php`'s `actionList` branch** — `$forgot_mail =
   $_POST['ownerEmailAddress']` was unescaped and unparameterized in the original; confirm
   it's now bound like every other query.
4. Flag (don't silently fix) any query that concatenates a column name or `ORDER BY`/`LIMIT`
   value from user input — those can't be parameterized with `?` and need a whitelist
   validation approach instead. List these separately.

**Deliverable to reviewer:** List of files migrated per batch + the flagged
column-name/ORDER-BY cases from task 4, called out explicitly.

**Acceptance check:** `grep -rn "FilterText\|->query(\"" *.php` at repo root returns nothing
(or only the flagged, justified exceptions).

---

## Phase 5 — Migrate `housekeeping/` (admin panel, ~30 files)

**Goal:** Same as Phase 4, applied to the admin panel. Treat as higher-risk since these
are privileged write operations (ban users, edit content, change ranks).

**Scope:** `housekeeping/*.php`.

**Tasks:**
1. Same query migration approach as Phase 4.
2. **Specifically re-verify `housekeeping/users.php`'s "savedetails"/"savebans" flows** — the
   original relied on a blanket `foreach($_POST as &$value){ $value = FilterText($value); }`
   at the top of the file; confirm the replacement explicitly binds each param per-query
   instead of relying on any global mutation pattern (global mutation is fragile and should
   not be reintroduced).
3. Confirm rank-check logic (`$page['rank']`, comparing user rank before allowing an action)
   is untouched/preserved — this is authorization logic, not something this migration should
   alter.

**Deliverable to reviewer:** File list + explicit confirmation that rank-check gating was
not modified (paste the before/after of that specific logic for each file where it appears).

**Acceptance check:** `grep -rn "FilterText\|->query(\"" housekeeping/*.php` clean.

---

## Phase 5b — Admin panel feature additions (rides along with Phase 5)

**Goal:** Add the admin-panel capabilities that don't currently exist, while the
`housekeeping/` auth/rank-check code is already being touched in Phase 5. Doing this
here is cheaper than a separate later pass since it reuses the same rank-gating and
`Database`/CSRF plumbing already in place by this point.

**Scope:** New files under `housekeeping/` following existing naming conventions, plus
schema additions (new tables) as needed.

**Tasks:**
1. **Admin action audit log** — new table (`admin_action_log`: admin_id, action_type,
   target_type, target_id, details, ip, created_at). Add a write call at the end of every
   existing privileged action in `housekeeping/*.php` (ban, rank change, catalogue edit,
   news post, etc.) — this is mechanical once the table/helper exists, do it file-by-file
   alongside the Phase 5 migration of that same file. New page: `housekeeping/auditlog.php`
   to search/filter by admin, action type, target, date range.
2. **Staff session management** — new page `housekeeping/staffsessions.php`: list active
   admin sessions (user, IP, last activity), with a "force logout" action per session.
   Reuses the session-token infrastructure from Phase 3.
3. **Admin 2FA** — TOTP-based (e.g. via a small library like `spomky-labs/otphp`), required
   for any account above a configurable rank threshold. New fields on the user table
   (`totp_secret`, `totp_enabled`), new setup flow, and a check inserted into the Phase 3
   login flow specifically for staff-rank accounts.
4. **User reports/complaints queue** — new table (`user_reports`: reporter_id,
   reported_user_id, reason, evidence/context, status, resolved_by, resolved_at). A
   user-facing "report" action (small addition to `habblet/`, coordinate with Phase 6) plus
   `housekeeping/reports.php` to triage: view, assign, resolve, action-taken notes.
5. **Bulk actions** — extend `users.php`/`bans.php` with multi-select + bulk-apply (bulk ban
   by list of names/IPs, bulk approve/reject pending catalogue submissions if applicable).
6. **Real dashboard metrics** — replace/extend `dashboard.php`'s content with actual
   figures: DAU/new-registrations chart (simple query + inline chart, no heavy JS framework
   needed), active ban count, pending reports count. Remove the existing remote
   `unserialize()` version-check call entirely per Phase 8 — don't rebuild on top of it.
7. **Unified admin search** — a single search box (`housekeeping/search.php`) that queries
   users (name/email/IP), catalogue items (name/ID), and reports in one pass, returning
   categorized results.
8. **Maintenance mode toggle** — a settings flag (reuse the existing `settings` table/object)
   with a UI toggle in `housekeeping/settings.php`, checked in `includes/core.php`'s
   bootstrap to show `templates/maintenance_header.php` site-wide when enabled, instead of
   requiring a manual file edit.

**Conventions specific to this phase:**
- Every new privileged page must call the same rank-check pattern established/verified in
  Phase 5 — no new page skips authorization.
- Every new privileged action must write to `admin_action_log` (task 1) — treat this as
  non-optional going forward, including for actions added in this phase itself.
- New DB tables get real foreign keys and indexes (on `target_id`, `reporter_id`,
  `created_at`, etc.) — this is new schema, not legacy data, so there's no excuse for
  skipping proper constraints.

**Deliverable to reviewer:** Schema diff (new tables/columns), list of new
`housekeeping/*.php` files, and confirmation that every existing privileged action
touched in Phase 5 now also writes an audit log entry (not just the new features from
this phase).

**Acceptance check:** Perform one action of each type (ban, rank change, catalogue edit)
as a test admin and confirm each produces a row in `admin_action_log` with correct
admin/target/timestamp. Confirm a non-2FA-enrolled staff-rank account is blocked from
logging in until TOTP setup is completed.

---

## Phase 6 — Migrate `habblet/` (AJAX handlers, ~60+ files — the long pole)

**Goal:** Same migration, applied to the AJAX/widget handler folder. This is the biggest
folder by file count, so split it into sub-batches.

**Scope:** `habblet/*.php`.

**Tasks:**
1. Split into logical sub-batches (e.g. `minimail_*`, `myhabbo_*`, `discussions_*`,
   `friendmanagement_*`, `ajax_*`) and report each sub-batch separately — this keeps
   individual review chunks manageable instead of one 60-file dump.
2. Same query-migration rules as Phase 4/5.
3. These are typically hit via `fetch`/XHR from the client — confirm none of them assume
   `$_POST` has already been globally sanitized by a parent include (check what each file's
   `require_once` chain actually guarantees before assuming it's safe).

**Deliverable to reviewer:** One short report per sub-batch (file list + anything unusual
found), not one giant end-of-phase report.

**Acceptance check:** `grep -rn "FilterText\|->query(\"" habblet/*.php` clean across all sub-batches.

---

## Phase 7 — CSRF protection

**Goal:** Every state-changing POST request across the whole app requires a valid,
per-session CSRF token.

**Scope:** New `includes/Csrf.php` + every `<form method="post">` and every AJAX POST
handler in `habblet/`, `housekeeping/`, and root pages.

**Tasks:**
1. Build `Csrf` class: `Csrf::token()` (generate/retrieve per-session token via
   `random_bytes()`), `Csrf::verify($submittedToken): bool` (using `hash_equals()`).
2. Add a hidden `<input type="hidden" name="csrf_token" value="...">` to every form found.
3. Add a `Csrf::verify()` check at the top of every POST-handling block; on failure, reject
   with a 403 and a generic error — don't leak why.
4. For `habblet/` AJAX handlers, decide once on a convention (token in POST body vs. a
   custom header like `X-CSRF-Token`) and apply it uniformly — call out which you chose.

**Deliverable to reviewer:** `includes/Csrf.php`, plus a list of every form/handler
touched (file + line of the check), grouped by folder.

**Acceptance check:** Spot-check 5 forms (reviewer's choice) — confirm token present in
form, verified server-side, and that submitting without/with a wrong token is rejected.

---

## Phase 8 — Close known structural vulnerabilities

**Goal:** Fix the specific issues already identified in code review (see prior analysis),
now that the DB/CSRF groundwork exists to do it properly.

**Scope:** `install/index.php`, `habbo-imaging/badge.php`, `housekeeping/dashboard.php`,
`housekeeping/updates.php`.

**Tasks:**
1. **`install/index.php`:** remove the `$_GET['bypass'] == "true"` escape hatch entirely.
   Add a hard lock: if `includes/config.php` exists, the installer refuses to run, full stop
   — no query-param override. Document in README that `install/` should be deleted after setup.
2. **`habbo-imaging/badge.php`:** validate `$_GET['badge']` against a strict allowlist
   pattern (e.g. `preg_match('/^[a-zA-Z0-9]+$/', $badgedata)`) before it ever touches a
   filesystem path; reject (don't sanitize-and-continue) on failure.
3. **`housekeeping/dashboard.php` / `updates.php`:** remove the `unserialize()` of a
   remote HTTP response entirely. Replace with `json_decode()` over an HTTPS URL, or drop
   the auto-update-check feature if no safe endpoint exists.

**Deliverable to reviewer:** Diff of exactly these 4 files, each with a one-line
"before: X, after: Y" summary.

**Acceptance check:** Reviewer confirms each of the 3 issues is closed by inspection
(these are small, targeted diffs — cheap to verify directly).

---

## Phase 9 — Caching + config/secrets

**Goal:** Real cache layer for settings/language/session data; secrets out of source.

**Scope:** `includes/config.php`, `cache/` folder and whatever reads from it, `.env.example`.

**Tasks:**
1. Move DB host/user/pass, mail credentials, and any API keys into env vars; add
   `.env.example` documenting required vars (never commit a real `.env`).
2. Add a `Cache` interface with at least two implementations: `FileCache` (fallback) and
   `RedisCache` (if `ext-redis`/Predis available), selected via env var.
3. Wire settings lookups (`$settings->find(...)`) and language string loads through the
   cache layer instead of hitting the DB on every request.

**Deliverable to reviewer:** `includes/Cache.php` (+ implementations), `.env.example`,
and confirmation that `includes/config.php` no longer contains literal credentials.

**Acceptance check:** `grep -rn "password\|secret" includes/config.php` shows only
`getenv()`/`$_ENV` reads, no literals.

---

## Phase 10 — Test pass, smoke test, cleanup

**Goal:** Everything holds together end-to-end.

**Tasks:**
1. Full-tree `grep -rn "mysql_\|FilterText\|mt_rand(" .` — should return nothing except
   any explicitly justified/flagged exceptions from earlier phases.
2. Manual click-through of core flows against a real DB: register → verify → login →
   edit profile → logout; admin login → ban a user → edit a badge; forgot-password flow.
3. Re-run `php -l` across the tree one more time.
4. Final README update: setup instructions, env vars required, note that `install/`
   must be removed/locked post-deploy.

**Deliverable to reviewer:** Test results (pass/fail per flow above) + final grep outputs.

**Acceptance check:** All flows pass manually; all greps clean.

---

## Notes for whoever reviews between phases (this is the "spend fewer tokens" part)

- Read the **deliverable**, not the full diff, first. Only pull up full file diffs for
  files the deliverable flags as unusual or where a convention might have drifted.
- The grep-based acceptance checks in each phase are designed to be a single command you
  (or I) can run to validate a phase in seconds rather than re-reading code.
- If a phase's executor deviates from a stated global convention (param style, token
  format, hashing choice), that's the one thing worth a full re-read — inconsistency
  across phases is what causes expensive rework later.

# Live XAMPP audit fixes — 2026-09-15

Fixes the P1–P3 findings in
[live-environment-audit-20260915.md](https://github.com/PapaBill1234/PHPRetro-PDO/blob/test/live-feature-audit-20260915/docs/phase-reports/live-environment-audit-20260915.md)
without bypassing authentication, suppressing fatals, or inventing PolarIS
balance/schema policy.

## F1 — session persistence

`HoloUser` was stored in `$_SESSION` while it still held a `Database` / PDO
connection. PHP 8.5 cannot serialize PDO, so login (success and failure) died at
session shutdown.

- `Database` and `HoloUser` now implement `__serialize` / `__unserialize`.
  The PDO connection is never stored; it is reconstructed per request.
- `account.php` and `reauthenticate.php` only write `$_SESSION['user']` after
  authentication succeeds. Failed logins keep the error in session and do not
  persist a user object.
- Staff `$_SESSION['hk_user']` and `$_SESSION['staff_2fa_pending_user']` use the
  same serializable object, so housekeeping login/2FA is covered too.

## F2 — housekeeping parse errors

All 27 housekeeping files had a leftover `)` on
`require_once __DIR__ . '/../includes/....php');` from PR #32. Every matching
include is corrected, not only the first hit in each file. Remaining
`require_once('../includes/AdminAudit.php')` calls after `core.php`'s `chdir()`
are converted to `__DIR__` so Apache no longer looks outside the site root.

## F3 — CAPTCHA

`PhpCaptcha` and `PhpCaptchaColour` now use `__construct`. Character count and
width are initialized before `SetWidth()`, and `CalculateSpacing()` refuses to
divide by zero. `session_start()` is skipped when a session is already active.

## F4 — registration avatars

`avatarURL()` always assigns a renderer URL first. A missing
`site_cache_images` setting no longer leaves `$URL` undefined (which leaked PHP
warnings into CSS `background-image`). Cache writes are best-effort and do not
replace the fallback URL when they fail. `HoloSettings` also defaults
`site_cache_images` to the installer value `"1"`.

## F5 — registration defaults

Missing `register_start_credits` is no longer cast to `0`. Credits are omitted
from the INSERT so PolarIS's native column default applies. A `users_settings`
row is created for the new account when one does not already exist. Missing
`email_verify_enabled` still follows the installer default (`0`, auto-verified);
this PR does not invent a mail policy.

## F6 — warning leaks

`core.php` initializes optional `$page` keys (`discussion`, `no_column3`,
`allow_guests`, `name`, `bodyid`, …). `session.php` saves `REQUEST_URI` when
`page.dir` is empty and never reads an undefined `$_SESSION['page']`.
`forgot.php` and `email.php` no longer call `session_start()` after `core.php`.

Housekeeping header optional keys `scrollbar` and `second_scrollbar` are initialized
and read with `!empty()`, so dashboard pages no longer emit undefined-array-key
warnings.

## F7 — empty optional assets

Login-family templates no longer emit `/web-gallery/js/` or `/web-gallery/styles/`
directory URLs. `HoloOptionalWebGalleryTag()` omits empty or missing files and
keeps `web-gallery/styles/local/com.css` when that file exists.

## Verification

```
php tests/live_audit_20260915_test.php
php tests/php85_runtime_fatals_test.php
```

Live retest still needs the operator's XAMPP + PolarIS `users` / `users_settings`
tables: successful and failed member login, housekeeping login/2FA, CAPTCHA
image bytes, and a fresh registration with avatar previews.

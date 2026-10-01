# PHP 8.5 runtime fatals (private-testing)

Private XAMPP PHP 8.5 testing of `master` surfaced four user-visible crashes. This
branch fixes those crashes plus the housekeeping session check that would have
been the next fatal after login.

## Reported failures

| Page | Symptom | Cause | Fix |
| --- | --- | --- | --- |
| Register | `Undefined variable $fail` in `includes/classes.php` and a red name box | `generateFigure()` read `$fail` before assigning it; blur only painted the field red until the magnifying-glass namecheck ran | Initialize `$fail` per set/color, skip empty pools (avoids `rand(0, -1)`), fallback look if XML is missing; auto-call `_checkName()` on blur |
| Housekeeping | `Undefined array key "hk_user"` then `require_once('../includes/Totp.php')` fatal | `core.php` `chdir()`s to the site root, so `../includes` looks outside the tree | Null-safe `$_SESSION['hk_user']`; housekeeping requires use `__DIR__ . '/../includes/...'` |
| Login | `pagename.home`, `HoloDate()['y']`, then `session_is_registered()` fatal | Locale not loaded, `mktime()` args were swapped so `'y'` was never set, PHP 4 session API | `addLocale("landing.login")`, rewrite `HoloDate()` to `date()`, `isset($_SESSION['page'])` |
| Privacy | `Call to undefined function HoloText()` | `HoloText` is a method on `HoloInput` | `papers.php` uses `$input->HoloText()`; `functions.php` also provides a global shim for leftover templates |

## Extra crash that would have followed housekeeping login

`includes/hksession.php` called `$serverdb->fetch_row($core->select3($user->id))`.
`Database` has no `fetch_row`, and `core_sql::select3()` still interpolates the
legacy `users.name` column. Rank is now `SELECT rank FROM users WHERE id = ?`.

## Register first-step UX

Original Habbo JS marks the name field as an error on blur and waits for a click
on the magnifying glass (`/habblet/ajax/namecheck`). Typing a name therefore
looked like a dead red box. The register page now:

- runs the namecheck on blur
- copies a selected no-Flash `randomFigure` radio into `bean.figure` / `bean.gender`
- accepts `randomFigure` on POST if the hidden figure is empty

Namecheck still goes through `habblet.php` `Csrf::protectPost()` with the existing
POST-body `csrf_token` hook.

## Verification

```
php tests/php85_runtime_fatals_test.php
php tests/csrf_test.php
```

Live click-through still needs the operator's XAMPP + PolarIS `users` table.
Do not merge until that private retest is green.

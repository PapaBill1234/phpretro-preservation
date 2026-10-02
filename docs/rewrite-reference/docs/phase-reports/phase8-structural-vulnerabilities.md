# Phase 8 — Close known structural vulnerabilities

Branch: `fix/phase8-structural-vulnerabilities`. Base: `master` (`500112c`, after PR #28). This PR is not merged or deployed.

Two remaining issues from the original security review, now that CSRF (Phase 7) is in. The third Phase 8 item (`unserialize()` of a remote HTTP response in housekeeping updates) is already closed on `master`: `housekeeping/updates.php` disabled the auto-update check, and `housekeeping/dashboard.php` is local stats only.

There is no project README. The live-site installer lock is the control; the already-installed error copy tells operators to delete `./install`.

PHP was not available in the implementation environment, so `php -l` was not run here.

## Before / after

| File | Before | After |
| --- | --- | --- |
| `install/index.php` | `file_exists('../includes/config.php') && $_GET['bypass'] != "true"` let `?bypass=true` skip the lock and re-run the installer on a live site. | Hard lock: if `includes/config.php` exists, the installer never starts. No query-param override. |
| `includes/languages/en.php` | Already-installed copy linked to `./index.php?bypass=true` and invited a destructive reinstall. | Copy tells the operator to delete `./install`. No bypass link. |
| `habbo-imaging/badge.php` | `$_GET['badge']` was concatenated into cache read/write paths (`./cache/badges/{badge}.gif`) with no validation, so `../` traversed the filesystem. | Strict allowlist `preg_match('/^[a-zA-Z0-9]+$/', $badgedata)` runs before any filesystem path is built. Failure is HTTP 400 and `exit` — reject, do not sanitize-and-continue. |

## `install/index.php`

The already-installed / upgrade branch now keys only on `file_exists('../includes/config.php')`.

- `?bypass=true` (and any other query param) cannot fall through to `./polaris.php` or `./migrate.php`.
- `?installed=` still only renders the post-install success page; it does not start a new install.
- Same-revision installs show `error.delete.installer` and stop.

To reinstall, `includes/config.php` must be removed by an operator with filesystem access. That is intentional.

## `habbo-imaging/badge.php`

Validation is the first use of `$_GET['badge']`, before `header()` and before `file_exists` / `imagecreatefromgif` / `imagegif` on `./cache/badges/`.

```php
$badgedata = $_GET['badge'] ?? '';
if (!is_string($badgedata) || preg_match('/^[a-zA-Z0-9]+$/', $badgedata) !== 1) {
    http_response_code(400);
    exit;
}
```

Rejects (HTTP 400): missing param, non-string (`badge[]=`), empty, dots, slashes, nulls, and any other non-alphanumeric. Habbo group badge codes (`b02214s09114s01113…`) are alphanumeric and still pass.

The later `str_replace(['b','X'], '', $badgedata)` and `explode('s', …)` still feed template/base filenames; those pieces stay alphanumeric because the parent string already is.

## Out of scope (already done)

| File | Status |
| --- | --- |
| `housekeeping/updates.php` | Auto-update check removed; no `unserialize()` of remote HTTP. |
| `housekeeping/dashboard.php` | Local DB stats only; no remote fetch. |

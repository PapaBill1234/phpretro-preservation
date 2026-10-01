# Phase 7 — CSRF protection

## Result

Branch: `feature/phase7-csrf`. Base: `dde7f52` (`master` after PR #26). This PR is not merged or deployed.

Every state-changing POST across the live CMS now requires a valid per-session CSRF token. Failure is HTTP 403 with the generic body `Request could not be completed.` — the reason is never leaked.

PHP was not available in the implementation environment, so `php -l` and `php tests/csrf_test.php` were not run here. `tests/csrf_test.php` is a no-database unit test covering generate / verify / `hash_equals` / field / hook.

## Token placement convention

**POST body field `csrf_token`. Not a custom header.**

2009 Habbo JS is Prototype `Ajax.Request` with `application/x-www-form-urlencoded` bodies. One field works for HTML forms and AJAX. `X-CSRF-Token` is deliberately unused; `Csrf::hookScript()` asserts that in tests.

| Client | How the token is sent |
| --- | --- |
| HTML `<form method="post">` | `Csrf::field()` hidden input |
| Prototype `Ajax.Request` | `Csrf::hookScript()` appends `csrf_token` to `options.parameters` for non-GET |
| `XMLHttpRequest` | same hook rewrites `send()` for non-GET/HEAD string bodies |
| Dynamically created forms | capture-phase `submit` listener injects the hidden input |

PayPal's hosted donation form is skipped by both `Csrf::field()` (never added) and the hook (action host `www.paypal.com`).

## `includes/Csrf.php`

| Method | Behaviour |
| --- | --- |
| `token()` | Per-session 32-byte `random_bytes()` as 64 hex chars, reused for the session |
| `verify($submitted = null)` | `hash_equals()` against `$_SESSION['_csrf_token']`; default submitted value is `$_POST['csrf_token']` |
| `field()` | `<input type="hidden" name="csrf_token" value="...">` (HTML-escaped) |
| `requireValid()` | 403 + generic text + `exit` |
| `protectPost()` | `requireValid()` for POST/PUT/PATCH/DELETE |
| `boot()` | mint token; then `protectPost()` unless `$GLOBALS['page']['csrf_skip']` |
| `hookScript()` | Prototype + XHR + form-submit injector |

## Enforcement layers

Defense in depth. A live request is a new PHP process, so the folder-wide gates always run.

| Layer | File:line | Covers |
| --- | --- | --- |
| CMS bootstrap | `includes/core.php:42` `Csrf::boot()` | Every page/habblet that includes `core.php`, including legacy habblets that include it directly |
| Habblet bootstrap | `includes/habblet.php:12` `Csrf::protectPost()` | Every habblet that `require`s `habblet.php` (Phase 6 + restored website features). Group/forum dispatchers get this via `habblet_groups.php` |
| Habblet login gate | `includes/habblet.php:27` inside `habbletRequireUser()` | Authenticated habblet mutations |
| Housekeeping session | `includes/hksession.php:43` `Csrf::protectPost()` | Authenticated HK POSTs after rank/IP checks |
| Installer | `install/polaris.php:7`, `install/migrate.php:22`, `install/upgrade.php:20` | Installer/upgrade POSTs that do not go through the same path as polaris/migrate |

CLI habblet tests define `IN_HOLOCMS` (skip `core.php`) and typically omit `REQUEST_METHOD`, so `protectPost()` is a no-op there. Production still enforces because each request boots `core.php`.

---

## Forms and handlers touched

`field` = `Csrf::field()` line. `check` = `Csrf::requireValid()` / `protectPost()` / `boot()` line. `x2` = two forms on the same line.

### `includes/`

| File | field | check |
| --- | --- | --- |
| `includes/Csrf.php` | (class) | (class) |
| `includes/core.php` | | 42 `boot()` |
| `includes/habblet.php` | | 12, 27 `protectPost()` |
| `includes/hksession.php` | | 43 `protectPost()` |
| `includes/habblet-templates/forum-opentopicsettings.php` | 1 | via `habblet.php:12` |
| `includes/habblet-templates/group-settings.php` | 1 | via `habblet.php:12` (`groups_actions_update_group_settings.php:19`) |
| `includes/habblet-templates/memberlist.php` | 3 | via `habblet.php:12` |

### Root pages

| File | field | check |
| --- | --- | --- |
| `account.php` | login forms in `index.php` / `landing.php` / `login_popup.php` / `templates/community_header.php` post here | 34 (`case "submit"`) |
| `register.php` | 99 | 13 (`bean_avatarName`) |
| `forgot.php` | 87, 125 | 30 (`actionForgot`), 43 (`actionList`) |
| `reauthenticate.php` | 76 | 31 |
| `iot.php` | 38 | 13 |
| `profile.php` | 14 | 5 |
| `index.php` | 135 | `account.php:34` |
| `landing.php` | 81 | `account.php:34` |
| `login_popup.php` | 69 | `account.php:34` |
| `club.php` | 127 (subscribe; handled by habblet AJAX) | `includes/core.php:42` + habblet |
| `credits.php` | 142 (voucher; handled by habblet AJAX) | `includes/core.php:42` + habblet |

### `templates/` (AJAX hook + forms)

| File | field / hook |
| --- | --- |
| `templates/client_header.php` | hook 89 |
| `templates/community_header.php` | hook 227; login form 267 |
| `templates/faq_header.php` | hook 83; search form 88 |
| `templates/housekeeping_header.php` | hook 59 |
| `templates/iot_header.php` | hook 32 |
| `templates/login_header.php` | hook 127 |
| `templates/register_header.php` | hook 155 |
| `templates/myhabbo_footer.php` | guestbook 150, guestbook delete 207, post delete 312 |

Homes/group discussion pages use `community_header` (hook) + `myhabbo_footer` (forms).

### `habblet/` — restored website mutations (explicit check)

These are the restored minimail / homes / group URL / club gift / collectibles / feed / reports / group purchase-edit / forum deletepost handlers. Each also inherits `habblet.php:12`.

| File | field | check |
| --- | --- | --- |
| `minimail_sendMessage.php` | AJAX hook | 19 |
| `minimail_deleteMessage.php` | AJAX hook | 19 |
| `minimail_emptyTrash.php` | AJAX hook | 19 |
| `minimail_report.php` | AJAX hook | 19 |
| `minimail_undeleteMessage.php` | AJAX hook | 19 |
| `minimail_confirmReport.php` | AJAX hook | 19 |
| `myhabbo_guestbook_add.php` | footer form + hook | 19 |
| `myhabbo_guestbook_remove.php` | footer form + hook | 19 |
| `myhabbo_layout_save.php` | AJAX hook | 3 |
| `myhabbo_widget_add.php` | AJAX hook | 19 |
| `myhabbo_widget_delete.php` | AJAX hook | 19 |
| `myhabbo_noteeditor_editor.php` | 30 | `includes/core.php:42` (includes `core.php` directly) |
| `ajax_habboclub_gift.php` | AJAX hook | 19 |
| `ajax_collectiblesPurchase.php` | AJAX hook | 19 |
| `ajax_removeFeedItem.php` | AJAX hook | 19 |
| `mod_add_report.php` | AJAX hook | 19 |
| `report_user.php` | AJAX hook | 3 |
| `grouppurchase_purchase_ajax.php` | AJAX hook | 19 |
| `grouppurchase_group_create_form.php` | 49 | `includes/core.php:42` |
| `groups_actions_startEditingSession.php` | AJAX hook | 20 |
| `groups_actions_saveEditingSession.php` | AJAX hook | 20 |
| `groups_actions_cancelEditingSession.php` | AJAX hook | 20 |
| `groups_actions_update_group_settings.php` | template form | 19 |
| `groups_actions_check_group_url.php` | AJAX hook | 19 |
| `discussions_actions_deletepost.php` | footer form + hook | 19 |

### `habblet/` — other POST handlers

Every other habblet that includes `habblet.php` or `core.php` is covered by the folder-wide gates. That includes remaining mutations such as `ajax_addFriend.php`, `ajax_updatemotto.php`, `friendmanagement_deletefriends.php`, `wardrobeStore.php`, `myhabbo_tag_add.php`, `myhabbo_tag_remove.php`, `myhabbo_friends_add.php`, `myhabbo_stickie_*`, `myhabbo_store_purchase.php`, and the group/forum dispatchers (`groups_actions_join.php`, `leave`, `delete_group`, `discussions_actions_savepost.php`, member-batch rights, etc.) which enter through `includes/habblet_groups.php` → `habblet.php:12` and `habbletRequireUser()` at `habblet.php:27`.

Read-only habblets that happen to be hit with POST (name check, tag search, load messages, …) are also rejected without a token. Prototype POSTs pick up the token from `hookScript()`.

`discussions_actions_pingsession.php` does not include `core.php` / `habblet.php` and only emits `X-JSON`; it is not a state-changing handler.

### `housekeeping/`

Authenticated pages also inherit `includes/hksession.php:43` except login (`index.php`) and 2FA setup (`twofactor.php`).

| File | field | check |
| --- | --- | --- |
| `index.php` (login) | 97 | 35 |
| `twofactor.php` | 9 | 7 |
| `alerts.php` | 80 (create), 115 (search) | 25 (search), 38 (save) |
| `banners.php` | 79 (save), 106 (remove) | 30 (save), 53 (remove) |
| `bans.php` | 14 x2 (bulk + unban) | 10 (bulk_ban), 12 (unban) |
| `campaigns.php` | 78 (save), 103 (remove) | 30 (save), 52 (remove) |
| `catalogue.php` | 93 (save), 135 (remove) | 30 (save), 63 (remove) |
| `collectables.php` | 11 x2 (save + delete) | 9 |
| `faq.php` | 28 (save), 29 (delete) | 6 |
| `help.php` | 43 | 16 |
| `logs.php` | 92 | 33 |
| `maintenance.php` | 5 | 3 |
| `news.php` | 11 x2 (save + delete) | 9 |
| `newsletter.php` | 117 | 74 |
| `recommended.php` | 92 (save), 112 (remove), 172 (search) | 30 (search), 44 (save), 66 (remove) |
| `reports.php` | 6 | 4 |
| `settings.php` | 72 | 62 |
| `staffsessions.php` | 5 | 3 |
| `users.php` | 48 x2 (savedetails + bulk rank) | 14 (bulk_rank), 36 (savedetails) |
| `vouchers.php` | 29 (save), 30 (delete) | 10 |

### `install/`

| File | field | check |
| --- | --- | --- |
| `polaris.php` | 53 | 7 (before copying `$_POST` into `$_SESSION`) |
| `migrate.php` | 212 | 22 |
| `upgrade.php` | (posted to by upgrade_*) | 20 |
| `upgrade_71.php` | 86 | `upgrade.php:20` + `core.php:42` |
| `upgrade_76.php` | 84 | `upgrade.php:20` + `core.php:42` |
| `upgrade_80.php` | 96 | `upgrade.php:20` + `core.php:42` |
| `installer_header.php` | hook 67 (only if `PHP_SESSION_ACTIVE`; autoloads `Csrf`) | |
| `install.php` | 271 (legacy dead installer form) | |

`installer_header.php` is shared by polaris / index / migrate / upgrade_*. The hook is guarded so pages that have not started a session do not fatal.

### Tests

| File | Notes |
| --- | --- |
| `tests/csrf_test.php` | No DB. Token format, stability, `verify()`, POST-body convention, hidden input, hook does not emit `X-CSRF-Token` |

## Intentionally skipped

| File | Why |
| --- | --- |
| `housekeeping/about.php:56` | PayPal hosted POST; token would break checkout. Hook also skips `www.paypal.com`. |
| `housekeeping/auditlog.php` | `method="get"` filter form. Not state-changing. |
| `references/**` | Historical snapshots, not live code. |

## Reviewer spot-check (plan acceptance)

Five forms with token in the form and verification on the POST block:

1. Login — `index.php:135` field → `account.php:34` check
2. Register — `register.php:99` field → `register.php:13` check
3. HK user edit — `housekeeping/users.php:48` field → `housekeeping/users.php:36` check
4. Minimail send — hook injects POST body → `habblet/minimail_sendMessage.php:19` check
5. Group settings — `includes/habblet-templates/group-settings.php:1` field → `habblet/groups_actions_update_group_settings.php:19` check

Submitting any of those without a token, or with a wrong token, is 403 `Request could not be completed.`

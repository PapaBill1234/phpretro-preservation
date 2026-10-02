# Phase 10 — Test pass, smoke test, cleanup

Branch: `fix/phase10-cleanup`. Base: `master` (`3af66d0`, after PRs #28–#30). **Do not merge this PR yourself.**

This is an honest status of the tree as it stands, plus the grep cleanup that Phase 10 required.

## Grep (task 1)

Command:

```sh
grep -rn "mysql_\|FilterText\|mt_rand(" .
```

**PHP (live + tests + installer): clean.** No `mysql_*`, no `FilterText`, no `mt_rand(` in any `.php` file outside `references/`.

Before this PR the live hits were:

| File | Before | After |
| --- | --- | --- |
| `includes/classes.php` `HoloInput::FilterText()` | Threw `Not yet migrated – see Phase 2` | Method deleted |
| `housekeeping/campaigns.php` | Concatenated `PREFIX.campaigns` + `FilterText` | PDO `phpretro_campaigns` |
| `housekeeping/banners.php` | Concatenated `PREFIX.banners` + `FilterText` | PDO `phpretro_banners` |
| `housekeeping/catalogue.php` | Concatenated `PREFIX.homes_catalogue` + `FilterText` | PDO `phpretro_homes_catalogue` |
| `housekeeping/recommended.php` | Concatenated `PREFIX.recommended` + `FilterText` + `housekeeping_sql` | PDO `phpretro_recommended` / PolarIS `rooms` / `guilds` |
| `housekeeping/settings.php` | Concatenated `PREFIX.settings_pages` + `FilterText` over `$_POST` keys | Allowlisted updates of existing `phpretro_site_settings` keys only |
| `housekeeping/logs.php` | `housekeeping_sql::select4` against Holograph `system_chatlog` + `FilterText` | PolarIS `chatlogs_room` |
| `install/install_functions.php` | Dead PolarIS-bypassed installer still called `FilterText` | `trim()` (this file is still unreachable: `install/install.php` requires `polaris.php` then `exit`) |

**Justified leftovers (not PHP, not live):**

- `PHPRetro-Modernization-Plan.md` — the Phase 10 grep recipe itself
- `docs/phase-reports/*` — historical receipts that name `FilterText`
- `references/**` — frozen pre-migration snapshots, not executed

`mt_rand(` is gone. Non-security `rand()` remains in the figure generator (`includes/classes.php`) and GD captcha (`captcha/php-captcha.inc.php`). That matches the plan: no `mt_rand()` for tokens/SSO/reset.

## `php -l` (task 3)

**Not re-run in this environment.** There is no `php` binary in the Phase 10 sandbox (`php: command not found`; apt cannot install). Last full lint on record is Phase 1: PHP **8.5.10** (XAMPP CLI/CGI), 261 files, 0 syntax errors (`docs/phase-reports/php85-compatibility.md`). The tree is now 295 PHP files outside `references/` and `web-gallery/`. Treat lint as **unchecked for this PR**.

Deployed target remains PHP 8.5. Confirm the private-test box with `php -v` before relying on it.

## Manual click-through (task 2)

**Not run.** No PHP and no MariaDB in this sandbox. Every flow below is **untested here**.

| Flow | Code status | Manual |
| --- | --- | --- |
| Register → verify → login | PolarIS `users` + `password_hash` / legacy sha1 rehash + `phpretro_email_verification_tokens` | **not run** |
| Edit profile → logout | Root pages use `Database` + CSRF | **not run** |
| Admin login → ban a user | `housekeeping/index.php` + `bans.php` + CSRF + audit log | **not run** |
| Edit a badge | No website badge editor. Flash editor is 501. Housekeeping user edit does not write PolarIS `users_badges` | **cannot pass as specified** |
| Forgot password | `forgot.php` binds `ownerEmailAddress`; CSRF on both POST branches | **not run** |

## README (task 4)

Added [README.md](../../README.md): PolarIS-first setup, required env vars, delete/lock `install/` after deploy, CSRF convention, 501 pointer.

---

## Is this ready for private testing?

**Yes, as a private PolarIS staff preview — not as a public hotel, and not as “Phase 10 acceptance passed.”**

You can install against a PolarIS `CleanDB`, apply `migrations/`, log in, use housekeeping users/bans/news/faq/vouchers/collectibles/settings, and exercise the website-owned restorations that already landed (minimail, user homes widgets except Trax/rating/store, group URLs, helpdesk, collectible claim, club-gift copy, feed dismiss, reports, group purchase/edit, forum deletepost). Expect 501s, expect CSRF 403s if the Prototype hook is missing, expect to delete `install/` yourself.

Do **not** tell testers it is production-ready.

---

## Every phase, true status

| Phase | PR | Merged? | True status |
| --- | --- | --- | --- |
| 1 PHP 8.5 boot | #14 | yes | Constructors / magic quotes / `case:` labels cleaned. Lint recorded on PHP 8.5.10. `var $` properties and stub `mysql`/`pgsql`/`sqlite`/`mssql` classes remain. |
| 2 PDO `Database` | (with later phases) | yes | `includes/Database.php` exists, positional `?`, env DSN. Smoke test file exists; not re-run here. |
| 3 Auth | polaris rework + later | yes | `HoloUser` uses PolarIS `users.username`, `password_hash` + sha1 lazy upgrade, `hash_equals` on remember tokens, `random_bytes` tickets. Session still stores the plaintext password for refresh. |
| 4 Root pages | batches + polaris rework | yes | Root `*.php` use `Database`. `forgot.php` binds the email. |
| 5 Housekeeping SQL | #11 | yes, **incomplete until this PR** | Users/bans/news/faq/vouchers/collectibles/dashboard migrated. Campaigns/banners/catalogue/recommended/settings/logs were still FilterText + `$db->fetch_assoc` (fatal on `Database`). This PR migrates them. |
| 5b Admin features | #12 | yes, with caveats | Audit log, staff sessions, TOTP pages, reports, search, maintenance, dashboard metrics exist. Staff-session lookup **fails open** if the table is missing (`includes/core.php`). Bulk rank is not transactional. 2FA enrollment was never click-tested here. |
| 6 habblet PDO | #19–#21 | yes | Habblets use `Database`. Features without a PolarIS/CMS equivalent return 501 instead of guessing schema. |
| 7 CSRF | #28 | yes | See CSRF section below. |
| 8 Structural vulns | #29 | yes for the two assigned bugs | Installer `?bypass=true` gone; `badge.php` alphanumeric allowlist. Dashboard `unserialize()` of a remote body was already removed in Phase 5 (`updates.php` dropped). |
| 9 Cache + secrets | #30 | yes | `.env` loader, no literals in `config.php`. FileCache default, Redis optional. Settings + locale + hotel status cached. PHP sessions are **not** in Redis. |
| 10 This report | this PR | open | Grep PHP-clean. Lint and manual flows **not run**. README added. |

Open work that is **not** a numbered plan phase: [PR #27](https://github.com/PapaBill1234/PHPRetro-PDO/pull/27) (`feature/restore-remaining-501s`) restored store / stickers / notes / ratings / guestbook privacy / group homes and **is merged**. Group tags are restored separately on `phpretro_guild_tags` — see [guild-tags.md](guild-tags.md).


---

## Features still returning 501 (on `master`)

These go through `habbletUnavailable()` / `HabbletGroupError(..., 501)`, or are called out as 200 client-handoff where a website grant would be a lie. They are blocked or handed off because PolarIS has no equivalent column, RCON, or encoding — not because the PHP is unfinished.

| Feature | Entry | Why 501 |
| --- | --- | --- |
| Flash group badge editor | `groups_actions_show_badge_editor` | **200 client-handoff** (PR client-handoff). `update_group_badge` stays 501 and never writes `guilds.badge`. Flash part encoding ≠ PolarIS badge string. |
| Room transfer | `HabbletGroups::settings()` when `roomId` changes | Form cannot perform PolarIS room-rights updates. |
| Group homes | `habblet/groups_widgets.php` | Layout model on `master` is user-homes only. **PR #27 restores this.** |
| Guestbook privacy | `myhabbo_guestbook_configure.php` | No privacy column on `master`. **PR #27 restores this.** |
| Home ratings | `myhabbo_rating_rate.php`, `myhabbo_rating_reset_ratings.php` | Not PolarIS `room_votes`. **PR #27 restores website ratings.** |
| MyHabbo store | `myhabbo_store_*.php` | No catalogue/inventory tables on `master`. **PR #27 restores this** (offline credit debit). |
| Stickers / notes place-edit | `myhabbo_sticker_*`, `myhabbo_stickie_*`, `myhabbo_noteeditor_place.php` | Same store/inventory gap. **PR #27 restores this.** |
| Club subscribe | `habboclub_habboclub_subscribe.php` | **200 client-handoff**. `optionNumber` ≠ `catalog_club_offers`; no take-credits RCON. Does not send `X-JSON daysLeft`. |
| Club reminder dismiss | `habboclub_habboclub_reminder_remove.php` | No persistent reminder row on `master`. **PR #27 maps it to `phpretro_feed_dismissals`.** |
| Trax | `traxplayerwidget`, `myhabbo_traxplayer_select_song.php`, `trax_song.php` | No website Trax/song store. Stays 501 after #27. |
| Website voucher redeem | `ajax_redeemvoucher.php` | **200 client-handoff**. No redeem RCON; faking `voucher_history` would double-grant against in-memory catalogue. Purse form is re-rendered so `PurseHabblet` can rebind. |
| Widget skins on this layout | `myhabbo_widget_edit.php` | Some skins are 501 on the current layout model. |
| Trax/rating widgets on user homes | `PhpretroHomes::BLOCKED_WIDGETS` | Explicit block list. Rating widget unblocks in #27; Trax stays blocked. |

Housekeeping “edit a badge” from the Phase 10 click-through list is **not** a 501 habblet — it simply does not exist as a website tool.

---

## CSRF (Phase 7) vs the restoration branch

Phase 7 merged **after** minimail / homes / group URLs / remaining website-owned features (#22–#26). It was written against that tree, not against the older habblet-only set.

Convention, unchanged: **POST body field `csrf_token`**. Not `X-CSRF-Token`.

Coverage of restored mutations is **yes**, two layers:

1. Folder-wide: `includes/core.php` `Csrf::boot()` and `includes/habblet.php:12` `Csrf::protectPost()` on every habblet that includes `habblet.php`.
2. Explicit `Csrf::requireValid()` on the restored handlers listed in `docs/phase-reports/phase7-csrf.md` (minimail send/delete/trash/report, guestbook add/remove, layout save, widget add/delete, habboclub gift, collectibles purchase, feed remove, mod reports, group purchase/edit/URL check, forum deletepost).

Unmerged PR #27 files still `require habblet.php` then `habbletRequireUser()` (which calls `Csrf::protectPost()` again). Restoring them does not punch a CSRF hole as long as that include stays first.

---

## Known limitations testers should expect

1. **No PHP/MariaDB in the agent sandbox.** This report is static review + grep, not a green CI run.
2. **Apply `migrations/008_phase10_website_content.sql`** (or re-run installer step 6) or banners/campaigns/recommended/catalogue HK pages have no tables.
3. **`phpretro_homes_catalogue` in 008 is the housekeeping-shaped table** (`type` 1/4, column `` `where` ``). [PR #27](https://github.com/PapaBill1234/PHPRetro-PDO/pull/27) wants a richer store catalogue. Merge order matters: `CREATE TABLE IF NOT EXISTS` will not reshape an existing table.
4. **`includes/data/holograph.php` is still required by `core.php`.** Rank checks no longer call it. Any leftover `$core->select*` / `$data->select*` path is Holograph SQL against the wrong schema and will error. `promo_habbos.php` was rewritten off `xml_sql`; other holograph callers may still exist in dead classes.
5. **Stub `HoloDatabase` / `mysql` / `pgsql` / `sqlite` / `mssql` classes still throw** “Not yet migrated – see Phase 2”. They must not be constructed.
6. **Session IP lock:** `includes/session.php` / `hksession.php` set `error = 5` if `$user->ip != REMOTE_ADDR`. Testers behind CGNAT, IPv6 fallback, or a reverse proxy will be kicked.
7. **Plaintext password in `$_SESSION['user']`** for session refresh.
8. **Staff sessions fail open** if `phpretro_staff_sessions` is missing.
9. **Newsletter** now selects PolarIS `users.mail` (there is no `newsletter` / `email_verified` CMS user table). A send emails every account with a mail address.
10. **CSRF 403** if a custom JS POST bypasses `Csrf::hookScript()` and omits `csrf_token`.
11. **Redis:** `CACHE_DRIVER=redis` without ext-redis/Predis silently uses files. Predis does not ping on connect.
12. **Installer:** live path is `install/polaris.php`. `install/install.php` exits immediately after requiring it; `install_functions.php` / `migrate_functions.php` are dead Holograph code still in the tree.
13. **Delete `install/` after setup.** Config existence is a hard lock (Phase 8); deleting the folder is still the production step.
14. **Captcha and random figures use `rand()`**, not `random_bytes()`. Not token-grade, not `mt_rand()`.
15. **No website Trax, no room transfer, no Flash `purchase_avatarsticker`** until a PolarIS fork/plugin exists. Club buy, voucher redeem, and the Flash badge viewer are 200 client-handoff pages ([client-handoff.md](client-handoff.md)) — they do not charge or grant.

---

## Files touched (this PR)

### `includes/`
- `classes.php` — deleted `FilterText`
- `session.php` — rank check uses `$user->user('rank')` (was `$serverdb->fetch_row($core->select3($id))` with undefined `$id`)
- `hksession.php` — same rank check; housekeeping actually boots now

### `housekeeping/`
- `campaigns.php`, `banners.php`, `catalogue.php`, `recommended.php`, `settings.php`, `logs.php` — PDO + CSRF + audit
- `newsletter.php` — PolarIS `users.mail`, `fetchAll` (was `fetch_row` on a missing method)

### `templates/`
- `housekeeping_header.php` — no `settings_pages` query; links maintenance / site settings / 5b pages
- `community_footer.php`, `myhabbo_footer.php` — `phpretro_banners` / `phpretro_faq` via `fetchAll`
- `faq_header.php`, `faq_footer.php` — `phpretro_faq`

### `xml/`
- `rss.php` — `phpretro_news`
- `promo_habbos.php` — PolarIS `users`, no `xml_sql`

### `install/`
- `install_functions.php` — `trim()` instead of `FilterText` (dead path)

### `migrations/`
- `008_phase10_website_content.sql` — banners, campaigns, recommended, homes_catalogue

### docs
- `README.md` (new)
- `docs/phase-reports/phase10-final-status.md` (this file)

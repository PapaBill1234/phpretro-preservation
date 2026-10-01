# Phase 4 batch 3 — Polaris SQL migration

## Summary

Migrated the requested root-page batch against Polaris. Only `users` is a real Polaris table among the legacy SQL used by these files. Unsupported legacy CMS tables were removed from the executable paths and are explicitly flagged below rather than replaced with invented schema.

## Files reviewed

- `iot.php` — legacy support-queue writes removed; no Polaris/custom replacement exists.
- `landing.php` — unsupported legacy tag-cloud query removed.
- `maintenance.php` — no SQL; unchanged.
- `maintenance_new.php` — no SQL; unchanged.
- `me.php` — rebuilt as a PDO-backed account summary using `users`.
- `papers.php` — removed unused legacy database helper; no SQL remains.
- `pixels.php` — no SQL; unchanged.
- `profile.php` — rebuilt around real `users` profile fields.
- `register.php` — already PDO-migrated on the email-verification parent branch; verified but not changed in this batch.

## Tables and columns used

### Polaris `users`

Verification command:

```bash
grep -n "CREATE TABLE IF NOT EXISTS \`users\`" references/schema/CleanDB.sql
```

Result:

```text
55189:CREATE TABLE IF NOT EXISTS `users` (
```

Verified columns used:

- `id`, `username`, `mail`, `mail_verified`, `account_created`, `account_day_of_birth`, `last_login`, `last_online`
- `motto`, `look`, `gender`, `credits`, `pixels`, `points`, `ip_register`, `ip_current`

### Custom email-verification table

`register.php` uses the project-owned `phpretro_email_verification_tokens` table from the email-verification parent PR. It is not a Polaris table.

Verification command:

```bash
grep -n "CREATE TABLE IF NOT EXISTS \`phpretro_email_verification_tokens\`" references/schema/CleanDB.sql
```

Result: no match, as expected. Its CREATE TABLE statement is in `migrations/001_custom_tables.sql` and `references/Custom-Schema-Additions.md` on the parent branch.

## Unsupported legacy schema flagged

The following legacy tables have no match in `CleanDB.sql` and have no project-owned custom equivalent supplied for this task:

- `help` — previously used by `iot.php` for support-ticket persistence.
- `tags` — previously used by `landing.php` for the tag cloud.
- `alerts`, `minimail`, `campaigns`, `forum_threads`, `forum_posts` — previously used by `me.php`.
- `wardrobe`, `verify` and legacy per-user preferences — previously used by `profile.php`.

These features are not silently remapped. `iot.php` now explains that support persistence has not been migrated; the landing tag cloud is empty; `me.php` exposes only confirmed account fields; and `profile.php` allows only the confirmed `motto`, `look`, and `gender` fields. A future focused feature/schema task is needed before restoring the unsupported functions.

## SQL safety check

On the Batch 3 branch, the requested files contain no `$serverdb->`, legacy `$db->`, or raw SQL interpolation calls. `me.php`, `profile.php`, and inherited `register.php` use `Database` and bound `?` parameters.

## Assumptions

- `settings->find(...)`, `GetOnlineCount()`, and `HotelStatus()` are existing application configuration/helpers, not direct page-level SQL, and were left alone.
- `register.php` remains inherited from `feature/restore-email-verification` to preserve token-backed verification. This makes Batch 3 a stacked PR until PR #7 is merged.

## PHP lint

`php -l` was not run because this task is GitHub-only and PHP is unavailable in the execution environment. The available shell reports:

```text
The term 'php' is not recognized as a name of a cmdlet, function, script file, or executable program.
```

Run after checkout with PHP 8.3:

```bash
php -l iot.php landing.php maintenance.php maintenance_new.php me.php papers.php pixels.php profile.php register.php
```
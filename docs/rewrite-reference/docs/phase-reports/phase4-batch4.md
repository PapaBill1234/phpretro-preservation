# Phase 4 batch 4 — Polaris SQL migration

## Summary

Completed the final three root-level pages. `tryout.php` and `welcome.php` now read only verified Polaris `users` fields through `Database` with bound parameters. `tag.php` no longer executes legacy tag SQL because Polaris has no `tags` table and this project has no custom replacement.

## Files changed

- `tag.php` — removes legacy `tags` query and legacy AJAX tag feature entry-points; shows a clear unavailable message.
- `tryout.php` — replaces legacy `figure`/`sex` access with PDO lookup of `users.look` and `users.gender`.
- `welcome.php` — replaces `welcome_sql` legacy lookup with PDO lookup of `users.username`, `users.look`, and `users.online`.

## Table and column verification

### `users`

Command:

```bash
grep -n "CREATE TABLE IF NOT EXISTS \`users\`" references/schema/CleanDB.sql
```

Result:

```text
55189:CREATE TABLE IF NOT EXISTS `users` (
```

Verified columns used: `id`, `username`, `look`, `gender`, and `online`.

### Legacy `tags`

Command:

```bash
grep -n "CREATE TABLE IF NOT EXISTS \`tags\`" references/schema/CleanDB.sql
```

Result: no match. `tags` is not a Polaris table and is not defined in `references/Custom-Schema-Additions.md`.

## Assumptions and unresolved items

- Classic tag clouds, search, matching, and tag fights require a purpose-built custom schema; none was supplied, so no table was invented.
- The tryout page is reduced to a current-figure preview. The legacy Flash wardrobe and club-selection UI is not compatible with the modern Polaris/Nitro target and is not restored here.
- `online` is fetched for the referrer but no longer drives legacy CSS/behaviour; the authoritative data remains Polaris's `users.online` field.

## SQL safety check

The three files contain no legacy `$serverdb`, `$db`, `FilterText`, or raw interpolated SQL. `tryout.php` and `welcome.php` use `Database` with `?` placeholders.

## PHP lint

`php -l` was not run because this task is GitHub-only and PHP is unavailable in the execution environment:

```text
The term 'php' is not recognized as a name of a cmdlet, function, script file, or executable program.
```

Run after checkout with PHP 8.3:

```bash
php -l tag.php tryout.php welcome.php
```
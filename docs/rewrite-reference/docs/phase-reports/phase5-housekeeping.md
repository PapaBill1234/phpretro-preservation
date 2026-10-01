# Phase 5 — housekeeping Polaris SQL audit

## Summary

This PR removes legacy PHPRetro database access from the housekeeping pages that have a verified Polaris or approved custom-schema equivalent:

- `housekeeping/bans.php`: lists and removes rows from Polaris `bans`.
- `housekeeping/collectables.php`: manages `phpretro_collectibles`.
- `housekeeping/dashboard.php`: uses aggregate reads of Polaris `users`, `rooms`, and `bans`.
- `housekeeping/news.php`: manages `phpretro_news`.
- `housekeeping/users.php`: lists and edits verified Polaris user fields; a credit adjustment also records the approved `phpretro_transactions` audit row.
- `housekeeping/vouchers.php`: manages Polaris `vouchers`.
- `housekeeping/updates.php`: drops the unsafe update-check feature.

`housekeeping/faq.php` was already using parameterized PDO with the approved `phpretro_faq` table, so it was audited but did not need another change.

## Files changed

- housekeeping/bans.php
- housekeeping/collectables.php
- housekeeping/dashboard.php
- housekeeping/news.php
- housekeeping/updates.php
- housekeeping/users.php
- housekeeping/vouchers.php
- docs/phase-reports/phase5-housekeeping.md

## Schema verification receipts

The full schema was checked directly from `references/schema/CleanDB.sql`; project-owned additions were checked in `references/Custom-Schema-Additions.md`.

```sh
rg -n -A 20 "CREATE TABLE IF NOT EXISTS \`bans\`" references/schema/CleanDB.sql
# 790: CREATE TABLE IF NOT EXISTS `bans`
# columns used: id, user_id, ip, timestamp, ban_expire, ban_reason, type
rg -n -A 22 "CREATE TABLE IF NOT EXISTS \`users\`" references/schema/CleanDB.sql
# 55189: CREATE TABLE IF NOT EXISTS `users`
# columns used: id, username, mail, rank, credits, pixels, points, online
rg -n -A 14 "CREATE TABLE IF NOT EXISTS \`rooms\`" references/schema/CleanDB.sql
# 54683: CREATE TABLE IF NOT EXISTS `rooms`
# column used: id
rg -n -A 14 "CREATE TABLE IF NOT EXISTS \`vouchers\`" references/schema/CleanDB.sql
# 55630: CREATE TABLE IF NOT EXISTS `vouchers`
# columns used: id, code, credits, points, points_type, catalog_item_id, amount, limit
rg -n -A 18 "phpretro_news\|phpretro_collectibles\|phpretro_transactions\|phpretro_faq" references/Custom-Schema-Additions.md
# verified custom tables and the exact columns used by the migrated pages
```

No table or column was inferred. In particular, `limit` is the literal Polaris voucher column and is quoted in SQL.

## Admin authorization review

No rank/authorization requirement was weakened.

The following rank logic was touched only where its page was rewritten. Before and after values are shown verbatim or, for the PHP 8-safe users guard, semantically identical:

```php
// bans.php, collectables.php, dashboard.php, news.php, updates.php, vouchers.php
// before
$page['rank'] = 5;
// after
$page['rank'] = 5;
```

```php
// users.php before
if($_GET['do'] == "savedetails" || $_GET['do'] == "savebadges"){
$page['rank'] = 7;
}else{
$page['rank'] = 6;
}

// users.php after
if(($_GET['do'] ?? '') == "savedetails" || ($_GET['do'] ?? '') == "savebadges"){
$page['rank'] = 7;
}else{
$page['rank'] = 6;
}
```

The only difference is the null-coalescing read, which avoids a PHP 8 undefined-index notice. Both privileged actions still require rank 7; all other actions still require rank 6. The existing `hksession.php` inclusion remains in every changed privileged page.

## Unsafe remote update checks

Both `dashboard.php` and `updates.php` contained a plain-HTTP `file_get_contents()` followed by `unserialize()`. It was removed. No verified HTTPS JSON endpoint is configured in this repository, so the update-check feature is disabled rather than trusting unauthenticated remote data.

## Audited but unresolved legacy pages

The following pages were audited. Their legacy SQL names have no verified Polaris/custom equivalent, so this PR deliberately does **not** map them to invented storage: `alerts.php`, `banners.php`, `cache.php`, `campaigns.php`, `catalogue.php` (the old CMS catalogue is not the same model as Polaris `catalog_items`), `help.php`, `logs.php`, `newsletter.php`, `recommended.php`, and `settings.php`.

`about.php`, `index.php`, `logout.php`, and `permissions.php` were audited for their housekeeping/bootstrap behavior. Their existing authorization setup was not altered. No new storage was invented for any of these pages.

## Assumptions and follow-up flags

- The transaction table is assumed to have been migrated from the approved custom migration before a housekeeping credit adjustment is saved.
- Existing custom-table migrations must be applied before using news, collectibles, FAQ, or transaction features.
- Unsupported legacy CMS features above require an explicit custom-schema design and a focused follow-up PR; they were not silently redirected to unrelated Polaris tables.

## PHP lint

No local files were created or used; this work was performed through the GitHub repository connector only. PHP was unavailable in the execution environment, so `php -l` could not run:

```
The term 'php' is not recognized as a name of a cmdlet, function, script file, or executable program.
```

The changed PHP files should be linted in CI or a PHP-enabled checkout before merge.

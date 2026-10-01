# Restore remaining 501 features (a/b from the reality check)

## Result

Branch: `feature/restore-remaining-501s`. Base: `feature/polaris-cms-rcon` (`8ec6e2f`, PR #26 still open). Do not merge ahead of #22–#26.

Website-owned restorations use `phpretro_*` tables plus `phpretro_emulator_outbox` (`synced_at` NULL, `PhpretroLiveSync::notifyLiveGame()` empty). PolarIS columns are not invented. Store credit debit is the documented (b) exception: it writes PolarIS `users.credits` only while the user is offline, same caveat as group purchase.

Categories are from `docs/phase-reports/polaris-cms-rcon.md`.

## Items

| # | Feature | Category | Built | Left 501 |
| --- | --- | --- | --- | --- |
| 1 | Homepage rating | **(a)** | `phpretro_home_ratings`. Not `room_votes`. 1–5, unique per rater, self-vote forbidden, owner reset | |
| 2 | Guestbook privacy | **(a)** | `phpretro_myhabbo_layouts.privacy`. Friends-only on user homes (`messenger_friendships`); members-only on groups (`guilds_members.level_id` IN 0/1/2) | |
| 3 | Club subscribe | **(c)** then handoff | | `habboclub_habboclub_subscribe.php` was 501. Now HTTP 200 client-handoff ([client-handoff.md](client-handoff.md)) |
| 4 | Club reminder | **(a)** | `habboclub_habboclub_reminder_remove.php` → `dismissFeed('hc-reminder')` on `phpretro_feed_dismissals` | |
| 5 | Trax | **(c)** | | `traxplayerwidget`, `myhabbo_traxplayer_select_song.php`, `trax_song.php` |
| 6 | Store catalogue/inventory | **(a)** | `phpretro_homes_catalogue` + `phpretro_homes_items` | |
| 6b | Store credit debit | **(b)** | Debits `users.credits` + `phpretro_transactions` only when `users.online` is not `'1'`/`'2'`. UI: leave the hotel first. PolarIS has no take-credits RCON | |
| 7 | Stickers | **(a)** | Place/remove on `phpretro_homes_items`. HTML `sticker-{id}` | |
| 8 | Notes / stickies | **(a)** | Place/edit/delete. Inventory notes, not PolarIS `items` | |
| 9 | Group homes | **(a)** | Same `phpretro_myhabbo_layouts` with `guild_id` (no second table — widget ids must not collide). Group guestbook in `phpretro_group_guestbook` | |
| 10 | Room transfer | **(c)** | | `HabbletGroups::settings()` still 501s a `roomId` change |
| 11 | Website voucher redeem | **(c)** then handoff | | `ajax_redeemvoucher.php` was 501. Now HTTP 200 client-handoff |
| — | Badge editor | **(c)** then handoff | | `groups_actions_show_badge_editor.php` is 200 client-handoff. `update_group_badge` stays 501 |
| — | Group tags | **(a)** | Later: `phpretro_guild_tags` (`migrations/009_guild_tags.sql`). See [guild-tags.md](guild-tags.md) | |
| — | `purchase_avatarsticker` | **(c)** | | Flash sticker editor, never restored |

## Schema receipts

Every PolarIS column was checked against `references/schema/CleanDB.sql`. Custom tables are absent from CleanDB (intentional).

### PolarIS tables used (SELECT / constrained writes)

| Source | Columns | Why |
| --- | --- | --- |
| `CleanDB.sql:55189` `users` | `id`, `username`, `motto`, `look`, `rank`, `credits` (55204), `online` enum `'0'\|'1'\|'2'` (55207) | Profile render; store debit; in-hotel gate |
| `CleanDB.sql:55483` `users_settings` | `club_expire_timestamp` (55516) SELECT only | HC skins 7/8. CMS never INSERT/UPDATE settings |
| `CleanDB.sql:52763` `messenger_friendships` | `user_one_id`, `user_two_id` | Private user guestbook = friends |
| `CleanDB.sql:40776` `guilds` | `id`, `user_id`, `name`, `description`, `room_id`, `state`, `badge`, `date_created` | Group-home widgets. `room_id` is not rewritten |
| `CleanDB.sql:41336` `guilds_members` | `guild_id`, `user_id`, `level_id` (41340) | Owner 0 / admin 1 / member 2 / pending 3 |
| `CleanDB.sql:54636` `room_votes` | inspected only | In-room thumbs-up. **Not** homepage rating |

```sh
grep -n "CREATE TABLE IF NOT EXISTS \`users\`" references/schema/CleanDB.sql
# 55189
grep -n "online\` enum" references/schema/CleanDB.sql
# 55207:  `online` enum('0','1','2') NOT NULL DEFAULT '0',
grep -n "club_expire_timestamp" references/schema/CleanDB.sql
# 55516
grep -n "CREATE TABLE IF NOT EXISTS \`room_votes\`" references/schema/CleanDB.sql
# 54636
grep -n "phpretro_home_ratings\|phpretro_homes_catalogue\|phpretro_homes_items\|phpretro_group_guestbook" references/schema/CleanDB.sql
# (no matches)
```

Homes PHP still never writes `users_settings`. Store debit is the only PolarIS write besides existing group purchase.

### Custom tables (`migrations/007_restore_remaining_501s.sql`)

ALTER `phpretro_myhabbo_layouts`:

| Column / index | Purpose |
| --- | --- |
| `privacy` ENUM('public','private') DEFAULT 'public' | Guestbook configure. Original lived on `PREFIX.homes.variable` |
| `guild_id` INT NOT NULL DEFAULT 0 | 0 = user home. >0 = group home. One id space so `widgetId` cannot hit the wrong row |
| UNIQUE `idx_user_guild_column_position` (`user_id`,`guild_id`,`column_number`,`position`) | Replaces `idx_user_column_position`. Group widgets store the guild **owner** as `user_id` |

New tables:

| Table | Purpose |
| --- | --- |
| `phpretro_home_ratings` | Homepage 1–5. UNIQUE `(profile_user_id, rater_id)`. FK `users.id` |
| `phpretro_homes_catalogue` | Website store. `type` sticker/widget/note/background. `placement` homes/groups/anywhere. Seed ids 101–107,109 user widgets (skip trax 108), 110–112 group widgets (skip group trax 113), 114 notes, 116–118 stickers/background |
| `phpretro_homes_items` | Inventory + placed stickers/notes/backgrounds. `placed` 0/1, `x/y/z`, `guild_id` |
| `phpretro_group_guestbook` | Group-home comments. FK `guilds.id` |

Credit audit reuses `phpretro_transactions` (`migrations/001_custom_tables.sql`) type `homes_store`. Reminder reuses `phpretro_feed_dismissals` key `hc-reminder`.

Every website write leaves `synced_at` NULL and records `phpretro_emulator_outbox`. Installer already applies `migrations/*.sql` in name order (`install/polaris.php`).

## Behaviour

| File | Result |
| --- | --- |
| `myhabbo_rating_rate.php` | GET `ownerId`/`ratingId`/`givenRate`. Stars then average. Self-vote 400. Duplicate vote is a no-op |
| `myhabbo_rating_reset_ratings.php` | Owner only |
| `myhabbo_guestbook_configure.php` | Toggle privacy; original JS pulses `#guestbook-type` |
| `myhabbo_guestbook_add.php` | Public = signed-in. Private user = friends. Private group = members |
| `habboclub_habboclub_reminder_remove.php` | `dismissFeed('hc-reminder')` |
| `myhabbo_store_{main,items,preview,purchase,purchase_confirm,inventory*}.php` | Catalogue + inventory. Confirm copy: credits show in-game next enter; item is in website inventory immediately |
| `myhabbo_store_purchase.php` | Offline required (409 + cancel button if in-hotel). Body `OK` + X-JSON inventory id |
| `myhabbo_sticker_place_sticker.php` / `remove_sticker.php` | Place posts `{selectedStickerId,zindex}`; X-JSON array of ids |
| `myhabbo_noteeditor_place.php` / `stickie_{edit,delete}.php` | Notes from inventory. Delete unplaces, does not destroy the catalogue grant |
| `groups_widgets.php` | Add-or-render group widgets while `$_SESSION['group_page_edit']` is set |
| `groups_actions_saveEditingSession.php` | Uses session if POST `groupId` missing (JS save has no groupId). `saveLayout($_POST)` then `waitAndGo` |
| `home.php` / `groups.php` | `#mypage-bg` + `#playground` for widgets, stickers, notes, background |

Pending/recorded copy (same idea as collectibles/club-gift):

- Store confirm: “You must be signed out of the hotel. Credits are deducted from your hotel account and will show in-game the next time you enter. The item is added to your website inventory immediately.”
- Store preview disables purchase while in-hotel with the same leave-the-hotel explanation.
- Purchase error 409: “Leave the hotel first. PolarIS has no take-credits command, so buying while online would be overwritten when you disconnect.”

## Still 501 (c)

- `myhabbo_traxplayer_select_song.php`, `trax_song.php`, `traxplayerwidget`
- Room transfer (`roomId` change in group settings)
- `groups_actions_update_group_badge.php` — Flash part encoding ≠ PolarIS `guilds.badge`
- Flash `purchase_avatarsticker`

Club subscribe, website voucher redeem, and `show_badge_editor` are no longer 501; they are HTTP 200 client-handoff pages ([client-handoff.md](client-handoff.md)). Group tags were category (c) here because `guilds` has no tags column. They are now website-owned on `phpretro_guild_tags` ([guild-tags.md](guild-tags.md)).


## Validation

```sh
php -l includes/PhpretroHomes.php home.php groups.php \
  includes/habblet_groups_actions.php habblet/myhabbo_*.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/restore_remaining_501s_test.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/web_homes_test.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/restore_remaining_features_test.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/phase6_habblet_batch1_test.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/phase6_habblet_batch2_test.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/phase6_habblet_batch3_test.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/polaris_cms_rcon_test.php
```

`php -l` clean. Disposable-MariaDB tests passed (73 + 28 + 44 + 57 + 178 + 44 + 39).

No PolarIS plugin, custom packet, or `cms_*` schema. Do not merge.

# Restore remaining website-owned 501 features

## Result

Branch: `feature/restore-remaining-features`. Base: `feature/web-group-urls` (`411af6b`, PR #24). Do not merge ahead of group-urls / homes / minimail / batch 3.

Website-owned restorations use `phpretro_*` tables plus `phpretro_emulator_outbox` (`synced_at` NULL, `PhpretroLiveSync::notifyLiveGame()` empty). PolarIS columns are not invented. Group purchase is the documented exception that mirrors PolarIS `RequestGuildBuyEvent` / `GuildManager.createGuild`.

## Review questions

### 1. Minimail report copies evidence before delete

Yes. No code change required.

`PhpretroMinimail::report()` locks the row, inserts `phpretro_user_reports.evidence` from `$row['subject']."\n\n".$row['body']`, then deletes the recipient copy.

```sh
grep -n -A12 "public function report" includes/PhpretroMinimail.php
```

```
199:    public function report(int $id): void
200-    {
201-        $this->transaction(function () use ($id) {
202-            $row = $this->message($id, true);
...
206-                'INSERT INTO phpretro_user_reports (reporter_id, reported_user_id, reason, evidence, status, action_notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
207-                [$this->actor, (int) $row['sender_id'], 'minimail', $row['subject']."\n\n".$row['body'], 'open', '', time()]
...
211-            $this->db->execute('DELETE FROM phpretro_minimail WHERE id = ? AND recipient_id = ?', [$id, $this->actor]);
```

The disposable-MariaDB test sends a mail, reports it as the recipient, and asserts the evidence contains both subject and body after the mail row is gone.

### 2. Homes is SELECT-only on `users_settings`

Yes. PolarIS owns those rows. The schema comment is:

```sh
grep -n "DONT HAVE YOUR CMS INSERT" references/schema/CleanDB.sql
# 55485:  `user_id` int(11) NOT NULL DEFAULT 0 COMMENT 'WARNING: DONT HAVE YOUR CMS INSERT ANYTHING IN HERE. THE EMULATOR DOES THIS FOR YOU!',
```

```sh
grep -n "INSERT INTO users_settings\|UPDATE users_settings" includes/PhpretroHomes.php home.php \
  habblet/myhabbo_homes.php habblet/myhabbo_guestbook.php habblet/myhabbo_guestbook_add.php \
  habblet/myhabbo_guestbook_list.php habblet/myhabbo_guestbook_remove.php \
  habblet/myhabbo_layouts.php habblet/myhabbo_layout_save.php \
  habblet/myhabbo_widget_add.php habblet/myhabbo_widget_delete.php
# (no matches)
```

`PhpretroHomes::profile()` is the only homes-path use: `LEFT JOIN users_settings` for `hide_online`, `tags`, `guild_id`. Test fixtures may INSERT `users_settings`; production homes code does not. There is no `homes.php`; the page is `home.php`.

### 3. Guestbook posting restriction

Logged-in only. Nothing stronger exists, and nothing stronger is added while privacy configure is 501.

| Gate | Where |
| --- | --- |
| `habbletRequireUser()` | `habblet/myhabbo_guestbook_add.php` — unsigned requests 403 / "Please sign in again." |
| `$this->actor > 0` | `PhpretroHomes::addGuestbook()` |
| Privacy / friends-only | **not implemented**. `myhabbo_guestbook_configure.php` stays 501. There is no privacy column on `phpretro_myhabbo_guestbook` or PolarIS. |

Any signed-in user may post to any user's guestbook. Friends-only is not invented.

## PolarIS Help Desk check

PolarIS has `support_tickets` (`CleanDB.sql:55048`). It is the in-game mod tool (`sender_id`, `reported_id`, `room_id`, `issue`, `category`, `group_id`, `thread_id`, `comment_id`, `photo_item_id`). The original CMS Help Tool used `PREFIX.help` (`iot.php` / `/iot/go`). PolarIS has no `help` table.

```sh
grep -n "CREATE TABLE IF NOT EXISTS \`support_tickets\`" references/schema/CleanDB.sql
# 55048:CREATE TABLE IF NOT EXISTS `support_tickets` (
grep -n "CREATE TABLE IF NOT EXISTS \`help\`" references/schema/CleanDB.sql
# (no matches)
```

The CMS does **not** write `support_tickets`. Website tickets go to `phpretro_helpdesk_tickets`.

## Schema receipts

Every table/column touched was checked against `references/schema/CleanDB.sql`. Custom tables are absent from CleanDB (intentional).

### PolarIS tables used

| Source | Columns used | Why |
| --- | --- | --- |
| `CleanDB.sql:55048` `support_tickets` | inspected only | In-game mod tool. Not written. |
| `CleanDB.sql:40776` `guilds` | `id`, `user_id`, `name` varchar(50), `description` varchar(250), `room_id`, `color_one`, `color_two`, `badge`, `date_created` | Group purchase INSERT matches `GuildManager.createGuild`. latin1. No `alias`. |
| `CleanDB.sql:40804` `guilds_elements` | id 1 `base` / `base_color` / `symbol` / `symbol_color` / `background_color` | Placeholder `b001010` + colors 1/1. |
| `CleanDB.sql:41299` `guilds_forums_comments` | `id`, `thread_id`, `state`, `admin_id` | Forum hide. |
| `CleanDB.sql:54683` `rooms` | `id`, `owner_id`, `guild_id` | Owned room with `guild_id = 0`. |
| `CleanDB.sql:54501` `room_rights` | `room_id`, `user_id` | `DELETE FROM room_rights WHERE room_id = ?` matches `RoomRightsManager.removeAllRights`. |
| `CleanDB.sql:55189` `users` | `id`, `username`, `mail`, `credits` | Helpdesk lookup; group purchase debit. |
| `CleanDB.sql:55483` `users_settings` | `user_id` (SELECT only from homes), `club_expire_timestamp` (club check), `hc_gifts_claimed` (assert unchanged) | CMS never INSERTs settings rows. |

```sh
grep -n "CREATE TABLE IF NOT EXISTS \`guilds\`" references/schema/CleanDB.sql
# 40776
grep -n "CREATE TABLE IF NOT EXISTS \`rooms\`" references/schema/CleanDB.sql
# 54683
grep -n "CREATE TABLE IF NOT EXISTS \`room_rights\`" references/schema/CleanDB.sql
# 54501
grep -n "hc_gifts_claimed" references/schema/CleanDB.sql
# 55533:  `hc_gifts_claimed` int(11) DEFAULT 0,
grep -n "phpretro_helpdesk_tickets\|phpretro_collectible_purchases\|phpretro_club_gifts\|phpretro_feed_dismissals\|phpretro_object_reports" references/schema/CleanDB.sql
# (no matches)
```

Placeholder badge encoding (`GuildBadgeBuilder.readBadge`): part 0 is `b` + 3-digit id + 2-digit color + position. id=1, color=1, position=0 → `b001010`.

Name length follows PolarIS `GuildInputLimits.MAX_GUILD_NAME_LENGTH = 29`. Description length follows the **column** `varchar(250)`, not Java `MAX_GUILD_DESCRIPTION_LENGTH = 254` (that would truncate in latin1). Price `10` is `catalog.guild.price`. Club required matches `catalog.guild.hc_required` default true. Membership cap 100 / `level_id < 3` matches existing CMS join logic.

### Forum hide: state 10 vs 20

`ForumThreadState` names 10=`HIDDEN_BY_STAFF_MEMBER` / 20=`HIDDEN_BY_GUILD_ADMIN` are inverted relative to the live write handler.

```
GuildForumModerateMessageEvent.java
// Restrict state 20 (staff hidden) to staff only
if (state == 20 && !hasStaffPermissions) { ... 403; }
```

Guild admins (`mod_forum`) may set 10. State 20 requires `ACC_MODTOOL_TICKET_Q`. The CMS hide writes `state = 10` and `admin_id = actor`. That is the write contract.

### Custom tables (`migrations/006_restore_remaining.sql`)

| Table | Purpose |
| --- | --- |
| `phpretro_helpdesk_tickets` | IOT / housekeeping Help Tool. `user_id` nullable (guests). FK `users.id`. |
| `phpretro_collectible_purchases` | Website claim. UNIQUE `(user_id, collectible_id)`. No PolarIS credit debit. |
| `phpretro_club_gifts` | Month 1–12 preview copy. Does not grant or write `hc_gifts_claimed`. |
| `phpretro_feed_dismissals` | PK `(user_id, item_key)`. `feedItemIndex` stored as a literal. |
| `phpretro_object_reports` | Object/room reports. **No `reported_user_id`**. Distinct from `phpretro_user_reports`. |

Every website write leaves `synced_at` NULL and records `phpretro_emulator_outbox`. Installer already applies `migrations/*.sql` in name order (`install/polaris.php`).

## Behaviour

| File | Result |
| --- | --- |
| `iot.php` (`/iot/go`) | POST username/email/subject/message → `phpretroHelpdesk()->submit`. Guests allowed. Does not write `support_tickets`. |
| `housekeeping/help.php` | Rank-gated list / pickup / remove against the CMS table. Bulk delete-all removed (id must be > 0). Reply-to-alerts not restored (PolarIS alerts not migrated). |
| `ajax_collectiblesConfirm.php` | Shows current `phpretro_collectibles` month + purchase control. Furniture is not granted. |
| `ajax_collectiblesPurchase.php` | Website claim once per user+month. Duplicate is a no-op. PolarIS `users.credits` unchanged. |
| `ajax_habboclub_gift.php` | Preview from `phpretro_club_gifts`. PolarIS `club_gift` catalog / `hc_gifts_claimed` untouched. |
| `ajax_removeFeedItem.php` | Stores `feedItemIndex` as `item_key` (injection stays data). |
| `mod_add_report.php` | GET `type` from `.htaccess` `mod/add_(.*)_report`. Allowlist `name\|room\|motto\|stickie\|animator\|habbomovie\|groupname\|url\|groupdesc\|guestbook\|discussionpost`. Room type verifies `rooms.id`. Duplicate open report returns `SPAM`; else `SUCCESS`. |
| `grouppurchase_purchase_ajax.php` | PolarIS createGuild: club, owned room `guild_id=0`, 10 credits, placeholder badge `b001010`, owner membership `level_id=0`, `rooms.guild_id`, clear `room_rights`. UI marks the badge as placeholder. |
| `groups_actions_start/save/cancelEditingSession.php` | Owner-only website session `$_SESSION['group_page_edit']`, 302 to `habbletGroupURL`. Group homes widgets stay 501. |
| `discussions_actions_deletepost.php` | Hide: `state=10`, `admin_id=actor`. Requires `mod_forum`. |
| `groups_actions_show_badge_editor.php` / `update_group_badge.php` | **501** unchanged. |

Record vs notify: website helpers call `record()` then `notifyLiveGame()`. Step 2 is a no-op today. Group purchase also writes PolarIS `guilds` / `guilds_members` / `rooms` / `users.credits` / `room_rights` because that is the live createGuild contract; the outbox event is `groups.purchased` with `placeholder_badge`.

## Gaps still 501 / not invented

- Flash badge editor (part encoding differs from PolarIS).
- Group homes widgets / store / stickers / notes / trax / rating.
- Voucher redeem, club subscribe, club reminder.
- Guestbook privacy / friends-only (no column).
- PolarIS plugin / custom packet / Java outbox consumer.
- No `cms_*` schema. No invented PolarIS columns.

## Validation

Disposable MariaDB `127.0.0.1:3307`, `DB_USER=root`, empty password, `skip-grant-tables`. Tests create scratch databases from CleanDB CREATE statements plus project migrations; they never touch a live schema.

```sh
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= php tests/restore_remaining_features_test.php
# PASS: 44 assertions; remaining restorations on disposable MariaDB.
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= php tests/phase6_habblet_batch1_test.php
# PASS: 56 assertions; all 37 batch-1 endpoints exercised against disposable MariaDB schema.
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= php tests/phase6_habblet_batch2_test.php
# Batch 2: 178 assertions passed.
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= php tests/phase6_habblet_batch3_test.php
# Batch 3: 61 assertions passed.
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= php tests/web_minimail_test.php
# PASS: 35 assertions
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= php tests/web_homes_test.php
# PASS: 28 assertions
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= php tests/web_group_urls_test.php
# PASS: 44 assertions
```

`php -l` on the new/changed PHP files: no syntax errors.

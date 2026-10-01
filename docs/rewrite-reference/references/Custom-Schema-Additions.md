# Custom Schema Additions (Polaris + PHPRetro-specific)

These tables do NOT exist in Polaris's stock schema (`CleanDB.sql`) — they are
custom additions this project owns. Prefixed with `phpretro_` specifically so
they're never confused with a real Polaris table, and so future Polaris updates
never collide with them.

Give this file to Codex alongside `Polaris-Schema-Reference.md` for any task
touching these three features.

---

## 1. `phpretro_news` — restores articles.php's full feature set

```sql
CREATE TABLE IF NOT EXISTS `phpretro_news` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `title` VARCHAR(255) NOT NULL,
  `summary` TEXT NOT NULL,
  `story` TEXT NOT NULL,
  `author` VARCHAR(100) NOT NULL,
  `categories` VARCHAR(255) NOT NULL DEFAULT '',
  `images` TEXT NOT NULL DEFAULT '',
  `time` INT NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_time` (`time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```
Matches the original PHPRetro news table's shape (categories as a comma-separated
string, images as a comma-separated string of URLs — same convention the
original `articles.php` already expected, so the PHP-side parsing logic can be
reused largely as-is). `idx_time` supports the "today/yesterday/this week/this
month" and archive-pagination queries efficiently.

## 2. `phpretro_collectibles` — restores collectables.php's feature

```sql
CREATE TABLE IF NOT EXISTS `phpretro_collectibles` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(255) NOT NULL,
  `description` TEXT NOT NULL,
  `image` VARCHAR(255) NOT NULL,
  `time` INT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `idx_time` (`time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```
`time` is unique since the original logic assumes one collectible per calendar
month (`mktime(0,0,0,$month,1,$year)`) — this constraint prevents accidentally
creating two "current" collectibles for the same period.

## 3. Client error logging — adapt for Nitro, don't just port the Flash version

**Do not assume a specific Nitro error-reporting convention without checking.**
No standard Habbo-Nitro-client error-reporting format was found via general
research — Codex should check the actual Nitro client source/docs directly
(the modern HTML5 Habbo client, not to be confused with the unrelated
`nitrojs/nitro` Node.js framework or Nitro PDF) for any existing
error-reporting call/endpoint convention it already makes. If one exists,
match it. If not, use this as a sensible new design:

```sql
CREATE TABLE IF NOT EXISTS `phpretro_client_errors` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NULL,
  `ip` VARCHAR(45) NOT NULL,
  `error_type` VARCHAR(50) NOT NULL,
  `message` TEXT NOT NULL,
  `stack_trace` TEXT NULL,
  `user_agent` VARCHAR(255) NULL,
  `url` VARCHAR(255) NULL,
  `client_version` VARCHAR(50) NULL,
  `created_at` INT NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```
This replaces the old Flash-specific fields (`hookerror`, `mus_errorcode`,
`neterr_cast`, etc. — all SWF/Shockwave-runtime concepts with no meaning in a
browser context) with generic, modern client-error fields that make sense for
a JS/TS-based HTML5 client. `ip` widened to VARCHAR(45) to support IPv6.

## Migration approach

Since Polaris auto-creates/migrates its own schema on startup, these custom
tables should be added via **your own separate migration step** — either a
one-time SQL script you run manually alongside Polaris's own schema setup, or
(cleaner) a small PHP-side "ensure table exists" check run once. Do NOT try to
register these as Polaris migrations — that's Polaris's own internal system and
mixing in project-specific tables there risks conflicts with future Polaris
updates.

## 4. phpretro_email_verification_tokens — restores email verification

~~~sql
CREATE TABLE IF NOT EXISTS `phpretro_email_verification_tokens` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `token_hash` CHAR(64) NOT NULL,
  `created_at` INT NOT NULL,
  `expires_at` INT NOT NULL,
  `used_at` INT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `idx_token_hash` (`token_hash`),
  INDEX `idx_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
~~~

Store only SHA-256 token hashes. A token is valid only while unused and before expires_at.

## 5. phpretro_transactions — restores transaction/purchase history

~~~sql
CREATE TABLE IF NOT EXISTS `phpretro_transactions` (
  `id` INT NOT NULL AUTO_INCREMENT, `user_id` INT NOT NULL, `type` VARCHAR(50) NOT NULL, `amount` INT NOT NULL, `balance_after` INT NOT NULL, `description` VARCHAR(255) NOT NULL DEFAULT '', `reference_id` VARCHAR(100) NULL, `created_at` INT NOT NULL, PRIMARY KEY (`id`), INDEX `idx_user_id_created` (`user_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
~~~

## 6. phpretro_faq — restores FAQ content

~~~sql
CREATE TABLE IF NOT EXISTS `phpretro_faq` (
  `id` INT NOT NULL AUTO_INCREMENT, `category` VARCHAR(100) NOT NULL DEFAULT 'general', `question` VARCHAR(255) NOT NULL, `answer` TEXT NOT NULL, `sort_order` INT NOT NULL DEFAULT 0, `active` TINYINT(1) NOT NULL DEFAULT 1, PRIMARY KEY (`id`), INDEX `idx_category_sort` (`category`, `sort_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
~~~

## 7. MyHabbo personal layout customization

~~~sql
CREATE TABLE IF NOT EXISTS `phpretro_myhabbo_layouts` (
  `id` INT NOT NULL AUTO_INCREMENT, `user_id` INT NOT NULL, `column_number` TINYINT NOT NULL, `widget_key` VARCHAR(50) NOT NULL, `position` INT NOT NULL DEFAULT 0, `visible` TINYINT(1) NOT NULL DEFAULT 1, PRIMARY KEY (`id`), UNIQUE INDEX `idx_user_column_position` (`user_id`, `column_number`, `position`), INDEX `idx_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `phpretro_myhabbo_guestbook` (
  `id` INT NOT NULL AUTO_INCREMENT, `profile_user_id` INT NOT NULL, `author_user_id` INT NOT NULL, `message` TEXT NOT NULL, `created_at` INT NOT NULL, PRIMARY KEY (`id`), INDEX `idx_profile_user_id` (`profile_user_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
~~~

Layouts are a simplified reconstruction; inspect real widgets before implementation.
## 5. `phpretro_transactions` — restores transaction/purchase history

```sql
CREATE TABLE IF NOT EXISTS `phpretro_transactions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `type` VARCHAR(50) NOT NULL,
  `amount` INT NOT NULL,
  `balance_after` INT NOT NULL,
  `description` VARCHAR(255) NOT NULL DEFAULT '',
  `reference_id` VARCHAR(100) NULL,
  `created_at` INT NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_user_id_created` (`user_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

`type` examples: `voucher_redeem`, `purchase`, `admin_grant`, `club_subscription`.
NaN is a snapshot for fast display without recomputing from history every time.

## 6. `phpretro_faq` — restores FAQ content

```sql
CREATE TABLE IF NOT EXISTS `phpretro_faq` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `category` VARCHAR(100) NOT NULL DEFAULT 'general',
  `question` VARCHAR(255) NOT NULL,
  `answer` TEXT NOT NULL,
  `sort_order` INT NOT NULL DEFAULT 0,
  `active` TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  INDEX `idx_category_sort` (`category`, `sort_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Straightforward CMS-style content table. `active` allows hiding an entry without deleting it.

## 7. MyHabbo personal layout customization — two tables

```sql
CREATE TABLE IF NOT EXISTS `phpretro_myhabbo_layouts` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `column_number` TINYINT NOT NULL,
  `widget_key` VARCHAR(50) NOT NULL,
  `position` INT NOT NULL DEFAULT 0,
  `visible` TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `idx_user_column_position` (`user_id`, `column_number`, `position`),
  INDEX `idx_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `phpretro_myhabbo_guestbook` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `profile_user_id` INT NOT NULL,
  `author_user_id` INT NOT NULL,
  `message` TEXT NOT NULL,
  `created_at` INT NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_profile_user_id` (`profile_user_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

`phpretro_myhabbo_layouts` stores which widgets a user has enabled, in which column and order. `phpretro_myhabbo_guestbook` covers the classic "leave a comment on someone's page" widget specifically, since it needs its own table shape (not just a layout position).

**This is a simplified reconstruction, not a guaranteed match to the original feature set.**

## 8. Live-sync outbox — website record vs PolarIS notify

Website-owned writes never touch PolarIS live tables. `PhpretroLiveSync::record()` inserts a pending outbox row; `notifyLiveGame()` is a no-op hook for a later Java consumer.

```sql
CREATE TABLE IF NOT EXISTS `phpretro_emulator_outbox` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `event_type` VARCHAR(64) NOT NULL,
  `payload_json` JSON NOT NULL,
  `status` ENUM('pending','processing','done','failed') NOT NULL DEFAULT 'pending',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `processed_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_status_created` (`status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 9. `phpretro_minimail` — website mailbox (subjects, trash, conversations)

One row per recipient, matching original PHPRetro minimail plus `synced_at`. PolarIS `messenger_*` tables are chat, not mail, and are never written here. `synced_at` stays NULL until a live-game consumer exists.

```sql
CREATE TABLE IF NOT EXISTS `phpretro_minimail` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `sender_id` INT NOT NULL,
  `recipient_id` INT NOT NULL,
  `subject` VARCHAR(100) NOT NULL,
  `body` TEXT NOT NULL,
  `conversation_id` INT NOT NULL DEFAULT 0,
  `sent_at` INT NOT NULL,
  `read_at` INT NULL,
  `deleted` TINYINT(1) NOT NULL DEFAULT 0,
  `deleted_at` INT NULL,
  `synced_at` TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_inbox` (`recipient_id`, `deleted`, `id`),
  INDEX `idx_sent` (`sender_id`, `id`),
  INDEX `idx_conversation` (`conversation_id`),
  CONSTRAINT `fk_phpretro_minimail_sender` FOREIGN KEY (`sender_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_phpretro_minimail_recipient` FOREIGN KEY (`recipient_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 10. MyHabbo layouts — `synced_at` live-sync columns

`phpretro_myhabbo_layouts` / `phpretro_myhabbo_guestbook` stay the 001 shape. Migration `004_web_homes.sql` adds nullable `synced_at`. Widget keys used on user homes: `profilewidget`, `guestbookwidget`, `highscoreswidget`, `badgeswidget`, `friendswidget`, `groupswidget`, `roomswidget`. Trax/rating/store/stickers and group homes stay 501. Layout row `id` is the widget id for guestbook and friends paging.

## 11. `phpretro_group_url_aliases` — website-owned `/groups/{alias}`

PolarIS `guilds` has no alias / `name_seo` column (`CleanDB.sql:40776`). Aliases are website-owned, claimed once, never written to PolarIS. `synced_at` stays NULL; claim also records `groups.alias_claimed` on `phpretro_emulator_outbox`.

```sql
CREATE TABLE IF NOT EXISTS `phpretro_group_url_aliases` (
  `alias` VARCHAR(64) NOT NULL,
  `guild_id` INT NOT NULL,
  `created_at` INT NOT NULL,
  `synced_at` TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (`alias`),
  UNIQUE INDEX `idx_guild_id` (`guild_id`),
  CONSTRAINT `fk_phpretro_group_url_guild` FOREIGN KEY (`guild_id`) REFERENCES `guilds` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Validation: 1–30 chars, `^[A-Za-z][A-Za-z0-9-]{0,29}$`, must equal `stringToURL($alias, false, false)`, not purely numeric, not reserved `actions|id|discussions|home`. `.htaccess` already routes `/groups/{alias}` to `groups.php?alias=`.

## 12. `phpretro_helpdesk_tickets` — CMS Help Tool (IOT)

PolarIS `support_tickets` (`CleanDB.sql:55048`) is the in-game mod tool and is never written from the CMS. Original PHPRetro used `PREFIX.help` for `/iot/go`. This table is the website-owned replacement.

```sql
CREATE TABLE IF NOT EXISTS `phpretro_helpdesk_tickets` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NULL,
  `username` VARCHAR(25) NOT NULL DEFAULT '',
  `email` VARCHAR(255) NOT NULL DEFAULT '',
  `ip` VARCHAR(45) NOT NULL,
  `subject` VARCHAR(50) NOT NULL,
  `message` TEXT NOT NULL,
  `room_id` INT NOT NULL DEFAULT 0,
  `status` ENUM('open','picked','closed') NOT NULL DEFAULT 'open',
  `picked_by` INT NULL,
  `created_at` INT NOT NULL,
  `synced_at` TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_status_created` (`status`, `created_at`),
  CONSTRAINT `fk_phpretro_helpdesk_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_phpretro_helpdesk_picker` FOREIGN KEY (`picked_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

`user_id` is nullable so guests can submit. `synced_at` stays NULL; submit/pickup/remove also record `phpretro_emulator_outbox`.

## 13. `phpretro_collectible_purchases` — website collectible claim

`phpretro_collectibles` has no PolarIS catalogue item id or price. The CMS records a claim and does not debit `users.credits` or grant furniture.

```sql
CREATE TABLE IF NOT EXISTS `phpretro_collectible_purchases` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `collectible_id` INT NOT NULL,
  `created_at` INT NOT NULL,
  `synced_at` TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `idx_user_collectible` (`user_id`, `collectible_id`),
  CONSTRAINT `fk_phpretro_collectible_purchase_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_phpretro_collectible_purchase_item` FOREIGN KEY (`collectible_id`) REFERENCES `phpretro_collectibles` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 14. `phpretro_club_gifts` — website club-gift preview copy

PolarIS club gifts live in the catalog (`club_gift` layout) and `users_settings.hc_gifts_claimed`. The CMS must not grant those. This table is preview text only, keyed by calendar month 1–12.

```sql
CREATE TABLE IF NOT EXISTS `phpretro_club_gifts` (
  `month` TINYINT NOT NULL,
  `name` VARCHAR(255) NOT NULL,
  `image` VARCHAR(255) NOT NULL DEFAULT '',
  `description` TEXT NOT NULL,
  `synced_at` TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (`month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 15. `phpretro_feed_dismissals` — dismissed website feed keys

The Habbo JS posts `feedItemIndex`. There is no PolarIS feed-item table to join, so the posted value is stored as a literal `item_key`.

```sql
CREATE TABLE IF NOT EXISTS `phpretro_feed_dismissals` (
  `user_id` INT NOT NULL,
  `item_key` VARCHAR(64) NOT NULL,
  `dismissed_at` INT NOT NULL,
  `synced_at` TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (`user_id`, `item_key`),
  CONSTRAINT `fk_phpretro_feed_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 16. `phpretro_object_reports` — object/room reports (not users)

Distinct from `phpretro_user_reports`. Object types do not always have a user owner, so this table has **no `reported_user_id`**. Allowlisted `object_type` values match `.htaccess` `mod/add_(.*)_report`: `name`, `room`, `motto`, `stickie`, `animator`, `habbomovie`, `groupname`, `url`, `groupdesc`, `guestbook`, `discussionpost`.

```sql
CREATE TABLE IF NOT EXISTS `phpretro_object_reports` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `reporter_id` INT NOT NULL,
  `object_type` VARCHAR(32) NOT NULL,
  `object_id` INT NOT NULL,
  `reason` VARCHAR(100) NOT NULL DEFAULT '',
  `evidence` TEXT NOT NULL,
  `status` VARCHAR(20) NOT NULL DEFAULT 'open',
  `created_at` INT NOT NULL,
  `synced_at` TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_reporter_created` (`reporter_id`, `created_at`),
  INDEX `idx_object` (`object_type`, `object_id`),
  INDEX `idx_status_created` (`status`, `created_at`),
  CONSTRAINT `fk_phpretro_object_reporter` FOREIGN KEY (`reporter_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 17. `phpretro_myhabbo_layouts.privacy` / `guild_id` — guestbook privacy + group homes

PolarIS has no guestbook table. Homepage widgets and group-home widgets share this CMS table so `widgetId` cannot collide.

```sql
ALTER TABLE `phpretro_myhabbo_layouts`
  ADD COLUMN `privacy` ENUM('public','private') NOT NULL DEFAULT 'public',
  ADD COLUMN `guild_id` INT NOT NULL DEFAULT 0,
  DROP INDEX `idx_user_column_position`,
  ADD UNIQUE INDEX `idx_user_guild_column_position` (`user_id`, `guild_id`, `column_number`, `position`),
  ADD INDEX `idx_guild_id` (`guild_id`);
```

`guild_id = 0` is a user home. `guild_id > 0` is a group home; `user_id` is the guild owner. `privacy` is the guestbook widget toggle (friends-only / members-only).

## 18. `phpretro_home_ratings` — homepage rating (not `room_votes`)

PolarIS `room_votes` is an in-room thumbs-up (`user_id`, `room_id`, no 1–5 value). Homepage rating is website-only.

```sql
CREATE TABLE IF NOT EXISTS `phpretro_home_ratings` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `profile_user_id` INT NOT NULL,
  `rater_id` INT NOT NULL,
  `rating` TINYINT NOT NULL,
  `created_at` INT NOT NULL,
  `synced_at` TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `idx_profile_rater` (`profile_user_id`, `rater_id`),
  INDEX `idx_profile` (`profile_user_id`),
  CONSTRAINT `fk_phpretro_home_ratings_profile` FOREIGN KEY (`profile_user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_phpretro_home_ratings_rater` FOREIGN KEY (`rater_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 19. `phpretro_homes_catalogue` / `phpretro_homes_items` — MyHabbo store

PolarIS has no `homes_catalogue`. Stickers/notes/backgrounds are not hotel furniture.

```sql
CREATE TABLE IF NOT EXISTS `phpretro_homes_catalogue` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(255) NOT NULL,
  `description` VARCHAR(255) NOT NULL DEFAULT '',
  `type` ENUM('sticker','widget','note','background') NOT NULL,
  `data` VARCHAR(255) NOT NULL,
  `price` INT NOT NULL DEFAULT 0,
  `amount` INT NOT NULL DEFAULT 1,
  `category` VARCHAR(255) NOT NULL DEFAULT 'Default',
  `category_id` INT NOT NULL DEFAULT 0,
  `min_rank` INT NOT NULL DEFAULT 1,
  `placement` ENUM('homes','groups','anywhere') NOT NULL DEFAULT 'anywhere',
  PRIMARY KEY (`id`),
  INDEX `idx_type_category` (`type`, `category_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `phpretro_homes_items` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `guild_id` INT NOT NULL DEFAULT 0,
  `catalogue_id` INT NOT NULL,
  `item_type` ENUM('sticker','stickie','background') NOT NULL,
  `skin` VARCHAR(64) NOT NULL DEFAULT '',
  `data` TEXT NOT NULL,
  `x` INT NOT NULL DEFAULT 0,
  `y` INT NOT NULL DEFAULT 0,
  `z` INT NOT NULL DEFAULT 0,
  `placed` TINYINT(1) NOT NULL DEFAULT 0,
  `synced_at` TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_user_placed_type` (`user_id`, `placed`, `item_type`),
  INDEX `idx_guild_placed` (`guild_id`, `placed`),
  CONSTRAINT `fk_phpretro_homes_items_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_phpretro_homes_items_catalogue` FOREIGN KEY (`catalogue_id`) REFERENCES `phpretro_homes_catalogue` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Credit debit is PolarIS `users.credits` only while `users.online` is `'0'`. Audit row type is `homes_store` on `phpretro_transactions`.

## 20. `phpretro_group_guestbook` — group-home comments

```sql
CREATE TABLE IF NOT EXISTS `phpretro_group_guestbook` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `guild_id` INT NOT NULL,
  `author_user_id` INT NOT NULL,
  `message` TEXT NOT NULL,
  `created_at` INT NOT NULL,
  `synced_at` TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_guild_created` (`guild_id`, `created_at`),
  CONSTRAINT `fk_phpretro_group_guestbook_guild` FOREIGN KEY (`guild_id`) REFERENCES `guilds` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_phpretro_group_guestbook_author` FOREIGN KEY (`author_user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 21. `phpretro_guild_tags` — website-owned group tags

PolarIS `guilds` has no tags column (`CleanDB.sql:40776`). User tags stay in `users_settings.tags` (semicolon-packed) and are never written by group-tag habblets. Tags are stored lowercase; `UNIQUE (guild_id, tag)` is the case-insensitive cap. Owner (`guilds.user_id`) and admin (`guilds_members.level_id = 1`) mutate; members/pending cannot. Outbox events: `guild.tag_added` / `guild.tag_removed`.

```sql
CREATE TABLE IF NOT EXISTS `phpretro_guild_tags` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `guild_id` INT NOT NULL,
  `tag` VARCHAR(20) NOT NULL,
  `created_by_user_id` INT NULL,
  `created_at` INT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE INDEX `idx_guild_tag` (`guild_id`, `tag`),
  INDEX `idx_tag` (`tag`),
  CONSTRAINT `fk_phpretro_guild_tags_guild` FOREIGN KEY (`guild_id`) REFERENCES `guilds` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_phpretro_guild_tags_user` FOREIGN KEY (`created_by_user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```



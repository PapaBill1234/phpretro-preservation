# Phase 4 Polaris schema rework

## Summary by file

- `account.php`: reviewed; it has no direct SQL. Authentication is delegated to the Phase 3 `HoloUser` path, so no schema query was added here.
- `articles.php`: replaced the old full-article `news` queries with `hotelview_news` announcement queries. The page now lists and displays only `title`, `text`, `button_text`, `button_type`, `button_link`, and `image`.
- `client.php`: reviewed; it has no direct SQL.
- `clientutils.php`: removed the write to the nonexistent legacy `client_errors` table. When logging is enabled it emits a PHP error-log entry instead; persistent telemetry requires a later Polaris migration.
- `club.php`: reviewed; it has no direct SQL.
- `collectables.php`: removed unverified `collectibles` queries. The current item and showroom deliberately remain unavailable because stock Polaris has no equivalent table.
- `community.php`: migrated room, user, forum, and announcement queries to Polaris `rooms`, `users`, `guilds_forums_threads`, and `hotelview_news`. Thread page counts now use the maintained `posts_count` column. The old standalone tag-cloud query is disabled because Polaris only exposes denormalized `rooms.tags`.
- `credits.php`: reviewed; it has no direct SQL.
- `discussions.php`: migrated group/member/thread/comment queries to `guilds`, `guilds_members`, `guilds_forums_threads`, and `guilds_forums_comments`; uses `subject`, `opener_id`, `guild_id`, `created_at`, `pinned`, and `locked`. It uses `posts_count` for pagination/replies and no longer writes an unsupported views counter.

## Schema verification

The source used was a fresh clone of `https://github.com/duckietm/Polaris-Emulator` at `/tmp/Polaris-Emulator`, specifically `Database/Default Database/CleanDB.sql`.

Exact lookups run:

```bash
cd /tmp/Polaris-Emulator
rg -n -i -C 3 "CREATE TABLE IF NOT EXISTS \`rooms\`|CREATE TABLE \`rooms\`" 'Database/Default Database/CleanDB.sql'
rg -n -i -C 3 "CREATE TABLE IF NOT EXISTS \`guilds\`|CREATE TABLE \`guilds\`" 'Database/Default Database/CleanDB.sql'
rg -n -i -C 3 "CREATE TABLE IF NOT EXISTS \`guilds_members\`|CREATE TABLE \`guilds_members\`" 'Database/Default Database/CleanDB.sql'
rg -n -i -C 3 "CREATE TABLE IF NOT EXISTS \`guilds_forums_threads\`|CREATE TABLE \`guilds_forums_threads\`" 'Database/Default Database/CleanDB.sql'
rg -n -i -C 3 "CREATE TABLE IF NOT EXISTS \`guilds_forums_comments\`|CREATE TABLE \`guilds_forums_comments\`" 'Database/Default Database/CleanDB.sql'
rg -n -i -C 3 "CREATE TABLE IF NOT EXISTS \`hotelview_news\`|CREATE TABLE \`hotelview_news\`" 'Database/Default Database/CleanDB.sql'
rg -n -i -C 3 "CREATE TABLE IF NOT EXISTS \`users\`|CREATE TABLE \`users\`" 'Database/Default Database/CleanDB.sql'
sed -n '40776,40820p;41299,41332p;41316,41332p;41336,41355p;41439,41455p;54683,54740p;55189,55270p' 'Database/Default Database/CleanDB.sql'
rg -n -i 'CREATE TABLE IF NOT EXISTS `[^`]*(collect|tag|client)[^`]*`' 'Database/Default Database/CleanDB.sql'
```

Verified tables and columns used:

- `rooms`: `id`, `name`, `owner_id`, `owner_name`, `users`, `users_max`, `is_public`, `is_staff_picked`.
- `users`: `id`, `username`, `account_day_of_birth`, `motto`, `look`.
- `guilds`: `id`, `user_id`, `name`, `description`, `state`, `forum`, `read_forum`, `post_messages`, `post_threads`, `mod_forum`, `badge`.
- `guilds_members`: `user_id`, `guild_id`, `level_id`.
- `guilds_forums_threads`: `id`, `guild_id`, `opener_id`, `subject`, `posts_count`, `created_at`, `updated_at`, `state`, `pinned`, `locked`, `admin_id`.
- `guilds_forums_comments`: `id`, `thread_id`, `user_id`, `message`, `created_at`, `state`, `admin_id`.
- `hotelview_news`: `id`, `title`, `text`, `button_text`, `button_type`, `button_link`, `image`.

## Scope reductions and migrations required

- Polaris `hotelview_news` is an announcement/banner table, not the old article system. It has no categories, archive dates, author, summary, story body, image gallery, or publication time. The article page is intentionally reduced to stock Polaris capabilities. Restoring the original feature scope requires a separate schema migration and product decision.
- Polaris CleanDB has no `collectibles`/`collectables` table. This feature is intentionally shown as unavailable instead of querying or inventing a table. A separate schema migration is required to restore it.
- Polaris CleanDB has no `client_errors` table. Persistent client telemetry requires a separate schema migration.
- Polaris stores room tags in `rooms.tags`; there is no verified standalone tag table compatible with the old tag-cloud aggregation. The old cloud is intentionally disabled.
- Polaris guilds do not have the legacy SEO alias, favorite-membership, or thread view-counter columns. Alias routing, favorite state, and view counting need a later product/schema decision if they must be restored.

## PHP lint

```text
No syntax errors detected in account.php
No syntax errors detected in articles.php
No syntax errors detected in client.php
No syntax errors detected in clientutils.php
No syntax errors detected in club.php
No syntax errors detected in collectables.php
No syntax errors detected in community.php
No syntax errors detected in credits.php
No syntax errors detected in discussions.php
```

## Final direct CleanDB verification (pre-merge)

This final pass used the authoritative `references/schema/CleanDB.sql` directly, rather than the summary document. The direct SQL inventory command was:

```bash
rg -n -i '(SELECT|INSERT|UPDATE|DELETE)[[:space:]]|\bFROM\b|\bINTO\b' articles.php clientutils.php collectables.php community.php discussions.php
```

The following are the **exact commands and complete results** for every table referenced by direct SQL in the changed PHP files.

`articles.php`: **checked and matches**. Its only table is `hotelview_news`; the direct result below contains every selected column: `id`, `title`, `text`, `button_text`, `button_type`, `button_link`, and `image`.

```bash
grep -n -A 12 -m 1 'CREATE TABLE IF NOT EXISTS `hotelview_news`' references/schema/CleanDB.sql
```

```text
41439:CREATE TABLE IF NOT EXISTS `hotelview_news` (
41440-  `id` int(11) NOT NULL AUTO_INCREMENT,
41441-  `title` varchar(100) NOT NULL,
41442-  `text` varchar(500) NOT NULL,
41443-  `button_text` varchar(50) NOT NULL,
41444-  `button_type` enum('client','web') NOT NULL DEFAULT 'web',
41445-  `button_link` varchar(200) NOT NULL,
41446-  `image` varchar(200) NOT NULL,
41447-  PRIMARY KEY (`id`) USING BTREE
41448-) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_general_ci ROW_FORMAT=DYNAMIC;
41449-
41450--- Dumping data for table camwijsnew.hotelview_news: ~1 rows (approximately)
41451-INSERT INTO `hotelview_news` (`id`, `title`, `text`, `button_text`, `button_type`, `button_link`, `image`) VALUES
```

`community.php`: **checked and matches**. Its room query uses `id`, `name`, `owner_id`, `owner_name`, `users`, `users_max`, `is_public`, and `is_staff_picked`; the direct result below contains every one.

```bash
grep -n -A 24 -m 1 'CREATE TABLE IF NOT EXISTS `rooms`' references/schema/CleanDB.sql
```

```text
54683:CREATE TABLE IF NOT EXISTS `rooms` (
54684-  `id` int(11) NOT NULL AUTO_INCREMENT,
54685-  `owner_id` int(11) NOT NULL DEFAULT 0,
54686-  `owner_name` varchar(25) NOT NULL DEFAULT '',
54687-  `name` varchar(50) CHARACTER SET utf8mb3 COLLATE utf8mb3_bin NOT NULL DEFAULT '',
54688-  `description` varchar(512) NOT NULL DEFAULT '',
54689-  `model` varchar(20) NOT NULL DEFAULT 'model_a',
54690-  `password` varchar(20) NOT NULL DEFAULT '',
54691-  `state` enum('open','locked','password','invisible') NOT NULL DEFAULT 'open',
54692-  `users` int(11) NOT NULL DEFAULT 0,
54693-  `users_max` int(11) NOT NULL DEFAULT 25,
54694-  `guild_id` int(11) NOT NULL DEFAULT 0,
54695-  `category` int(11) NOT NULL DEFAULT 1,
54696-  `score` int(11) NOT NULL DEFAULT 0,
54697-  `paper_floor` varchar(5) NOT NULL DEFAULT '0.0',
54698-  `paper_wall` varchar(5) NOT NULL DEFAULT '0.0',
54699-  `paper_landscape` varchar(5) NOT NULL DEFAULT '0.0',
54700-  `thickness_wall` int(11) NOT NULL DEFAULT 0,
54701-  `wall_height` int(11) NOT NULL DEFAULT -1,
54702-  `thickness_floor` int(11) NOT NULL DEFAULT 0,
54703-  `moodlight_data` varchar(254) NOT NULL DEFAULT '2,1,1,#000000,255;2,3,1,#000000,255;2,3,1,#000000,255;',
54704-  `tags` varchar(500) NOT NULL DEFAULT '',
54705-  `is_public` enum('0','1') NOT NULL DEFAULT '0',
54706-  `is_staff_picked` enum('0','1') NOT NULL DEFAULT '0',
54707-  `allow_other_pets` enum('0','1') NOT NULL DEFAULT '0',
```

`community.php`: **checked and matches**. Its user query uses `id`, `username`, `account_day_of_birth`, `motto`, and `look`; the direct result below contains every one.

```bash
grep -n -A 14 -m 1 'CREATE TABLE IF NOT EXISTS `users`' references/schema/CleanDB.sql
```

```text
55189:CREATE TABLE IF NOT EXISTS `users` (
55190-  `id` int(11) NOT NULL AUTO_INCREMENT,
55191-  `username` varchar(25) NOT NULL,
55192-  `real_name` varchar(25) NOT NULL DEFAULT 'KREWS DEV',
55193-  `password` varchar(64) NOT NULL,
55194-  `mail` varchar(500) DEFAULT NULL,
55195-  `mail_verified` enum('0','1') NOT NULL DEFAULT '0',
55196-  `account_created` int(11) NOT NULL,
55197-  `account_day_of_birth` int(11) NOT NULL DEFAULT 0,
55198-  `last_login` int(11) NOT NULL DEFAULT 0,
55199-  `last_online` int(11) NOT NULL DEFAULT 0,
55200-  `motto` varchar(127) NOT NULL DEFAULT '',
55201-  `look` varchar(256) NOT NULL DEFAULT 'hr-115-42.hd-195-19.ch-3030-82.lg-275-1408.fa-1201.ca-1804-64',
55202-  `gender` enum('M','F') NOT NULL DEFAULT 'M',
55203-  `rank` int(11) NOT NULL DEFAULT 1,
```

`community.php`: **checked and matches**. Its forum-list query uses `id`, `guild_id`, `subject`, `posts_count`, and `updated_at`; the direct result below contains every one.

```bash
grep -n -A 14 -m 1 'CREATE TABLE IF NOT EXISTS `guilds_forums_threads`' references/schema/CleanDB.sql
```

```text
41316:CREATE TABLE IF NOT EXISTS `guilds_forums_threads` (
41317-  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
41318-  `guild_id` int(11) DEFAULT 0,
41319-  `opener_id` int(11) DEFAULT 0,
41320-  `subject` varchar(255) DEFAULT '',
41321-  `posts_count` int(11) DEFAULT 0,
41322-  `created_at` int(11) DEFAULT 0,
41323-  `updated_at` int(11) DEFAULT 0,
41324-  `state` int(11) DEFAULT 0,
41325-  `pinned` tinyint(4) DEFAULT 0,
41326-  `locked` tinyint(4) DEFAULT 0,
41327-  `admin_id` int(11) DEFAULT 0,
41328-  PRIMARY KEY (`id`) USING BTREE,
41329-  KEY `idx_guild_forum_threads_guild_id` (`guild_id`,`id`)
41330-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin ROW_FORMAT=COMPACT;
```

`community.php`: **checked and matches**. Its announcement query uses the same `hotelview_news` columns verified for `articles.php`; the repeated direct result is included here for this file.

```bash
grep -n -A 12 -m 1 'CREATE TABLE IF NOT EXISTS `hotelview_news`' references/schema/CleanDB.sql
```

```text
41439:CREATE TABLE IF NOT EXISTS `hotelview_news` (
41440-  `id` int(11) NOT NULL AUTO_INCREMENT,
41441-  `title` varchar(100) NOT NULL,
41442-  `text` varchar(500) NOT NULL,
41443-  `button_text` varchar(50) NOT NULL,
41444-  `button_type` enum('client','web') NOT NULL DEFAULT 'web',
41445-  `button_link` varchar(200) NOT NULL,
41446-  `image` varchar(200) NOT NULL,
41447-  PRIMARY KEY (`id`) USING BTREE
41448-) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_general_ci ROW_FORMAT=DYNAMIC;
41449-
41450--- Dumping data for table camwijsnew.hotelview_news: ~1 rows (approximately)
41451-INSERT INTO `hotelview_news` (`id`, `title`, `text`, `button_text`, `button_type`, `button_link`, `image`) VALUES
```

`discussions.php`: **checked and matches**. Its guild query uses `id`, `user_id`, `name`, `description`, `state`, `forum`, `read_forum`, `post_messages`, `post_threads`, `mod_forum`, and `badge`; the direct result below contains every one.

```bash
grep -n -A 22 -m 1 'CREATE TABLE IF NOT EXISTS `guilds`' references/schema/CleanDB.sql
```

```text
40776:CREATE TABLE IF NOT EXISTS `guilds` (
40777-  `id` int(11) NOT NULL AUTO_INCREMENT,
40778-  `user_id` int(11) NOT NULL DEFAULT 0,
40779-  `name` varchar(50) NOT NULL DEFAULT '',
40780-  `description` varchar(250) NOT NULL DEFAULT '',
40781-  `room_id` int(11) NOT NULL DEFAULT 0,
40782-  `state` int(11) NOT NULL DEFAULT 0,
40783-  `rights` enum('0','1') NOT NULL DEFAULT '0',
40784-  `color_one` int(11) NOT NULL DEFAULT 0,
40785-  `color_two` int(11) NOT NULL DEFAULT 0,
40786-  `badge` varchar(256) NOT NULL DEFAULT '',
40787-  `date_created` int(11) NOT NULL,
40788-  `forum` enum('0','1') NOT NULL DEFAULT '0',
40789-  `read_forum` enum('EVERYONE','MEMBERS','ADMINS') NOT NULL DEFAULT 'EVERYONE',
40790-  `post_messages` enum('EVERYONE','MEMBERS','ADMINS','OWNER') NOT NULL DEFAULT 'EVERYONE',
40791-  `post_threads` enum('EVERYONE','MEMBERS','ADMINS','OWNER') NOT NULL DEFAULT 'EVERYONE',
40792-  `mod_forum` enum('ADMINS','OWNER') NOT NULL DEFAULT 'ADMINS',
40793-  PRIMARY KEY (`id`) USING BTREE,
40794-  KEY `id` (`id`) USING BTREE,
40795-  KEY `data` (`room_id`,`user_id`) USING BTREE,
40796-  KEY `name` (`name`) USING BTREE,
40797-  KEY `description` (`description`) USING BTREE
40798-) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci ROW_FORMAT=DYNAMIC;
```

`discussions.php`: **checked and matches**. Its membership query uses `user_id`, `guild_id`, and `level_id`; the direct result below contains every one.

```bash
grep -n -A 13 -m 1 'CREATE TABLE IF NOT EXISTS `guilds_members`' references/schema/CleanDB.sql
```

```text
41336:CREATE TABLE IF NOT EXISTS `guilds_members` (
41337-  `id` int(11) NOT NULL AUTO_INCREMENT,
41338-  `guild_id` int(11) NOT NULL DEFAULT 0,
41339-  `user_id` int(11) NOT NULL DEFAULT 0,
41340-  `level_id` int(11) NOT NULL DEFAULT 0,
41341-  `member_since` int(11) NOT NULL DEFAULT 0,
41342-  PRIMARY KEY (`id`) USING BTREE,
41343-  KEY `id` (`id`) USING BTREE,
41344-  KEY `user_id` (`user_id`) USING BTREE,
41345-  KEY `guild_id` (`guild_id`) USING BTREE,
41346-  KEY `userdata` (`user_id`,`guild_id`) USING BTREE,
41347-  KEY `level_id` (`level_id`) USING BTREE,
41348-  KEY `member_since` (`member_since`) USING BTREE
41349-) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci ROW_FORMAT=DYNAMIC;
```

`discussions.php`: **checked and matches**. Its thread queries use `id`, `guild_id`, `opener_id`, `subject`, `posts_count`, `created_at`, `updated_at`, `state`, `pinned`, `locked`, and `admin_id`; the direct result below contains every one.

```bash
grep -n -A 15 -m 1 'CREATE TABLE IF NOT EXISTS `guilds_forums_threads`' references/schema/CleanDB.sql
```

```text
41316:CREATE TABLE IF NOT EXISTS `guilds_forums_threads` (
41317-  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
41318-  `guild_id` int(11) DEFAULT 0,
41319-  `opener_id` int(11) DEFAULT 0,
41320-  `subject` varchar(255) DEFAULT '',
41321-  `posts_count` int(11) DEFAULT 0,
41322-  `created_at` int(11) DEFAULT 0,
41323-  `updated_at` int(11) DEFAULT 0,
41324-  `state` int(11) DEFAULT 0,
41325-  `pinned` tinyint(4) DEFAULT 0,
41326-  `locked` tinyint(4) DEFAULT 0,
41327-  `admin_id` int(11) DEFAULT 0,
41328-  PRIMARY KEY (`id`) USING BTREE,
41329-  KEY `idx_guild_forum_threads_guild_id` (`guild_id`,`id`)
41330-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin ROW_FORMAT=COMPACT;
41331-
```

`discussions.php`: **checked and matches**. Its comment queries use `id`, `thread_id`, `user_id`, `message`, `created_at`, `state`, and `admin_id`; the direct result below contains every one.

```bash
grep -n -A 13 -m 1 'CREATE TABLE IF NOT EXISTS `guilds_forums_comments`' references/schema/CleanDB.sql
```

```text
41299:CREATE TABLE IF NOT EXISTS `guilds_forums_comments` (
41300-  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
41301-  `thread_id` int(11) NOT NULL DEFAULT 0,
41302-  `user_id` int(11) NOT NULL DEFAULT 0,
41303-  `message` text NOT NULL,
41304-  `created_at` int(11) NOT NULL DEFAULT 0,
41305-  `state` int(11) NOT NULL DEFAULT 0,
41306-  `admin_id` int(11) NOT NULL DEFAULT 0,
41307-  PRIMARY KEY (`id`) USING BTREE,
41308-  KEY `id` (`id`) USING BTREE,
41309-  KEY `thread_data` (`thread_id`,`user_id`,`created_at`,`state`) USING BTREE
41310-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin ROW_FORMAT=COMPACT;
41311-
41312--- Dumping data for table camwijsnew.guilds_forums_comments: ~0 rows (approximately)
```

`discussions.php`: **checked and matches**. Its user lookups use `id`, `username`, `motto`, and `look`; the direct result below contains every one.

```bash
grep -n -A 14 -m 1 'CREATE TABLE IF NOT EXISTS `users`' references/schema/CleanDB.sql
```

```text
55189:CREATE TABLE IF NOT EXISTS `users` (
55190-  `id` int(11) NOT NULL AUTO_INCREMENT,
55191-  `username` varchar(25) NOT NULL,
55192-  `real_name` varchar(25) NOT NULL DEFAULT 'KREWS DEV',
55193-  `password` varchar(64) NOT NULL,
55194-  `mail` varchar(500) DEFAULT NULL,
55195-  `mail_verified` enum('0','1') NOT NULL DEFAULT '0',
55196-  `account_created` int(11) NOT NULL,
55197-  `account_day_of_birth` int(11) NOT NULL DEFAULT 0,
55198-  `last_login` int(11) NOT NULL DEFAULT 0,
55199-  `last_online` int(11) NOT NULL DEFAULT 0,
55200-  `motto` varchar(127) NOT NULL DEFAULT '',
55201-  `look` varchar(256) NOT NULL DEFAULT 'hr-115-42.hd-195-19.ch-3030-82.lg-275-1408.fa-1201.ca-1804-64',
55202-  `gender` enum('M','F') NOT NULL DEFAULT 'M',
55203-  `rank` int(11) NOT NULL DEFAULT 1,
```

`clientutils.php`: **checked and matches**. It has no direct SQL after removal of the legacy `client_errors` insert.

`collectables.php`: **checked and matches**. It has no direct SQL after removal of the unverified legacy `collectibles` queries.

`phase4-polaris-rework.md`: **checked**. It is documentation only and has no direct SQL.

No table or column mismatch was found in this final direct-schema pass, so no PHP query changes were required.

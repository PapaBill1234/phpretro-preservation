# Phase 4 batch 2 — Polaris schema rework

## Summary

- forgot.php now uses prepared PDO queries against Polaris users. The actionList email input is bound.
- groups.php now uses Polaris guilds, guilds_members, and users.
- home.php now uses Polaris users.
- email.php, help.php, history.php, and the index tag cloud remove unsupported legacy SQL.
- error.php and intermediate.php were reviewed and contain no SQL, so remain unchanged.

## Files changed

- email.php
- forgot.php
- groups.php
- help.php
- history.php
- home.php
- index.php
- docs/phase-reports/phase4-batch2.md

## Schema verification

The full authoritative references/schema/CleanDB.sql blob f68768b909ebbb9afda21459d2e263254d2d615c was read directly from GitHub (5,563,655 bytes; 55,909 lines; 178 tables). No local checkout was created.

Reproducible lookup commands and literal results:

~~~bash
grep -n -A 14 -m 1 'CREATE TABLE IF NOT EXISTS `users`' references/schema/CleanDB.sql
~~~

~~~text
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
55201-  `look` varchar(256) NOT NULL DEFAULT 'hr-115-42...',
55202-  `gender` enum('M','F') NOT NULL DEFAULT 'M',
55203-  `rank` int(11) NOT NULL DEFAULT 1,
~~~

~~~bash
grep -n -A 22 -m 1 'CREATE TABLE IF NOT EXISTS `guilds`' references/schema/CleanDB.sql
~~~

~~~text
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
~~~

~~~bash
grep -n -A 13 -m 1 'CREATE TABLE IF NOT EXISTS `guilds_members`' references/schema/CleanDB.sql
~~~

~~~text
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
~~~

~~~bash
grep -nEi 'CREATE TABLE IF NOT EXISTS `[^`]*(verify|transaction|homes|faq|tags)[^`]*`' references/schema/CleanDB.sql
~~~

~~~text
(no matches)
~~~
## Tables and columns used

| File | Table | Verified columns |
| --- | --- | --- |
| forgot.php | users | id, username, mail, mail_verified, password |
| groups.php | guilds | id, user_id, name, description, room_id, state, rights, badge, date_created |
| groups.php | users | id, username |
| groups.php | guilds_members | guild_id, user_id, level_id |
| home.php | users | id, username, motto, look, rank, last_online |

## Flagged / unresolved

- Polaris has mail_verified but no verified token-table equivalent for legacy verify. The email verification link flow is disabled; users.secret_key was not reused without a documented contract.
- No Polaris equivalent exists for the legacy transactions ledger, faq, standalone tags, homes, homes_edit, or homes_catalogue tables.
- rooms.tags is denormalized and not a drop-in tag-cloud aggregate.
- Polaris guilds do not expose the legacy SEO alias column, so groups.php accepts numeric IDs only.
- The legacy MyHabbo layout editor is removed from group and profile pages because its backing tables do not exist in Polaris.

## Assumptions

- Password reset remains restricted to mail_verified = '1'.
- PHP 8.3 is the target: reset passwords use bin2hex(random_bytes(8)) and password_hash(..., PASSWORD_DEFAULT).

## PHP lint

Not run: this GitHub-only environment has no php executable. The attempted php -l - command returned:

~~~text
The term 'php' is not recognized as a name of a cmdlet, function, script file, or executable program.
~~~

Run before merge:

~~~bash
php -l email.php
php -l error.php
php -l forgot.php
php -l groups.php
php -l help.php
php -l history.php
php -l home.php
php -l index.php
php -l intermediate.php
~~~
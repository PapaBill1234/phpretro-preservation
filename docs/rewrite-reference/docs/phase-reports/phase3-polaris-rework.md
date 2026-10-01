# Phase 3 Polaris schema rework

## Summary by file

- `includes/classes.php`: migrated account-ban checks to Polaris `bans`; migrated HC membership reads and grants to `users_subscriptions`; added password-free `HoloUser::loginFromToken()` for already validated remember-me tokens; and aligned the supporting Polaris user fields used by login/session loading.
- `security_check.php`: validates a SHA-256 hash of the remember-me cookie against `users.remember_token_hash`, requires a future `remember_token_expires_at`, then completes the login through `loginFromToken()`.

## Schema verification

The source used was `references/schema/CleanDB.sql`, the checked-in Polaris schema source of truth described in `Polaris-Schema-Reference.md`.

Exact discovery lookups run:

```bash
grep -n -i 'CREATE TABLE IF NOT EXISTS `[^`]*club[^`]*`' references/schema/CleanDB.sql
grep -n -i 'CREATE TABLE IF NOT EXISTS `[^`]*subscription[^`]*`' references/schema/CleanDB.sql
```

```text
900:CREATE TABLE IF NOT EXISTS `builders_club_items` (
1614:CREATE TABLE IF NOT EXISTS `catalog_club_offers` (
55570:CREATE TABLE IF NOT EXISTS `users_subscriptions` (
```

`users_subscriptions` is the verified HC/club membership storage: it has a per-user subscription type, Unix `timestamp_start`, `duration`, and `active` state. The implementation stores HC grants with `subscription_type = 'hc'`, preserves any unexpired time when granting another month, and calculates the remaining calendar days from `timestamp_start + duration`.

## Final direct CleanDB verification (pre-merge)

The following are the **exact commands and complete results** for every table referenced by the schema-rework SQL changes.

`includes/classes.php`: **checked and matches**. Account-ban checks use `bans.user_id`, `bans.ban_reason`, `bans.ban_expire`, and `bans.type`.

```bash
grep -n -A 14 -m 1 'CREATE TABLE IF NOT EXISTS `bans`' references/schema/CleanDB.sql
```

```text
790:CREATE TABLE IF NOT EXISTS `bans` (
791-  `id` int(11) NOT NULL AUTO_INCREMENT,
792-  `user_id` int(11) NOT NULL,
793-  `ip` varchar(50) NOT NULL DEFAULT '',
794-  `machine_id` varchar(255) NOT NULL DEFAULT '',
795-  `user_staff_id` int(11) NOT NULL,
796-  `timestamp` int(11) NOT NULL,
797-  `ban_expire` int(11) NOT NULL DEFAULT 0,
798-  `ban_reason` varchar(200) NOT NULL DEFAULT '',
799-  `type` enum('account','ip','machine','super') NOT NULL DEFAULT 'account' COMMENT 'Account is the entry in the users table banned.\nIP is any client that connects with that IP.\nMachine is the computer that logged in.\nSuper is all of the above.',
800-  `cfh_topic` int(11) NOT NULL DEFAULT -1,
801-  PRIMARY KEY (`id`) USING BTREE,
802-  KEY `user_data` (`user_id`,`ip`,`machine_id`,`ban_expire`,`timestamp`,`ban_reason`) USING BTREE,
803-  KEY `general` (`id`,`type`) USING BTREE
804-) ENGINE=InnoDB DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci ROW_FORMAT=DYNAMIC;
```

`includes/classes.php`: **checked and matches**. HC membership reads and writes use `users_subscriptions.id`, `user_id`, `subscription_type`, `timestamp_start`, `duration`, and `active`.

```bash
grep -n -A 13 -m 1 'CREATE TABLE IF NOT EXISTS `users_subscriptions`' references/schema/CleanDB.sql
```

```text
55570:CREATE TABLE IF NOT EXISTS `users_subscriptions` (
55571-  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
55572-  `user_id` int(10) unsigned DEFAULT NULL,
55573-  `subscription_type` varchar(255) DEFAULT NULL,
55574-  `timestamp_start` int(10) unsigned DEFAULT NULL,
55575-  `duration` int(10) unsigned DEFAULT NULL,
55576-  `active` tinyint(1) DEFAULT 1,
55577-  PRIMARY KEY (`id`) USING BTREE,
55578-  KEY `user_id` (`user_id`) USING BTREE,
55579-  KEY `subscription_type` (`subscription_type`) USING BTREE,
55580-  KEY `timestamp_start` (`timestamp_start`) USING BTREE,
55581-  KEY `active` (`active`) USING BTREE
55582-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci ROW_FORMAT=DYNAMIC;
55583-
```

`includes/classes.php` and `security_check.php`: **checked and matches**. Login and remember-me handling use `users.id`, `username`, `password`, login/session fields, and Polaris's `remember_token_hash` and `remember_token_expires_at` fields.

```bash
grep -n -A 31 -m 1 'CREATE TABLE IF NOT EXISTS `users`' references/schema/CleanDB.sql
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
55204-  `credits` int(11) NOT NULL DEFAULT 2500,
55205-  `pixels` int(11) NOT NULL DEFAULT 500,
55206-  `points` int(11) NOT NULL DEFAULT 10,
55207-  `online` enum('0','1','2') NOT NULL DEFAULT '0',
55208-  `auth_ticket` varchar(256) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL DEFAULT '',
55209-  `ip_register` varchar(45) NOT NULL,
55210-  `ip_current` varchar(45) NOT NULL COMMENT 'Have your CMS update this IP. If you do not do this IP banning won''t work!',
55211-  `machine_id` varchar(64) NOT NULL DEFAULT '',
55212-  `home_room` int(11) NOT NULL DEFAULT 0,
55213-  `secret_key` varchar(40) DEFAULT NULL,
55214-  `pincode` varchar(11) DEFAULT NULL,
55215-  `extra_rank` int(11) DEFAULT NULL,
55216-  `auth_ticket_expires_at` timestamp NULL DEFAULT NULL,
55217-  `remember_token_hash` varchar(64) NOT NULL DEFAULT '',
55218-  `remember_token_expires_at` int(11) unsigned NOT NULL DEFAULT 0,
55219-  `access_token_version` bigint(20) NOT NULL DEFAULT 0,
55220-  `background_id` int(11) NOT NULL DEFAULT 0,
```

## PHP lint

```text
No syntax errors detected in includes/classes.php
No syntax errors detected in security_check.php
```

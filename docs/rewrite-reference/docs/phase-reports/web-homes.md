# Website Homes (MyHabbo layouts)

## Result

Branch: `feature/web-homes`. Base: `feature/web-minimail` (PR #22). Do not merge ahead of minimail.

User homes use the existing `phpretro_myhabbo_layouts` / `phpretro_myhabbo_guestbook` tables. Original widget list from `habblet/myhabbo_widgets.php`: profile, guestbook, highscores, badges, friends, groups, rooms, traxplayer, rating. Trax, rating, store, stickers, notes and **group homes** stay 501.

## Schema

| Source | Columns |
| --- | --- |
| `migrations/001_custom_tables.sql` — `phpretro_myhabbo_layouts` | `id`, `user_id`, `column_number`, `widget_key`, `position`, `visible` |
| `migrations/004_web_homes.sql` | adds `synced_at` to layouts + guestbook |
| `migrations/001` — `phpretro_myhabbo_guestbook` | `id`, `profile_user_id`, `author_user_id`, `message`, `created_at` |
| `CleanDB.sql:55189` `users` | `id`, `username`, `motto`, `look`, `account_created`, `last_online`, `online` |
| `CleanDB.sql:55483` `users_settings` | `tags`, `hide_online`, `guild_id` |
| `CleanDB.sql:55274` `users_badges` | `badge_code`, `slot_id` |
| `CleanDB.sql:52763` `messenger_friendships` | `user_one_id`, `user_two_id` |
| `CleanDB.sql:40776` / `41336` | `guilds`, `guilds_members.level_id` IN (0,1,2) |
| `CleanDB.sql:54683` `rooms` | `owner_id`, `name`, `description` |

No PolarIS high-score table is used. High scores render empty. Catalogue item IDs from the old store are not guessed.

## Behaviour

| File | Result |
| --- | --- |
| `myhabbo_widget_add.php` | Allowlisted user widgets; layout `id` is the widget id; records `homes.widget_added` |
| `myhabbo_widget_delete.php` | Owner only; profile widget cannot be removed |
| `myhabbo_widget_edit.php` | Column/position; skins 501 |
| `myhabbo_widgets.php` | Renders user widgets from PolarIS reads + guestbook table |
| `myhabbo_guestbook_{add,list,remove}.php` | Widget id → layout `user_id` |
| `myhabbo_guestbook_configure.php` | **501** — no privacy column |
| `myhabbo_avatarlist_friendsearchpaging.php` | Widget id → friends of layout owner |
| `myhabbo_homes.php` | Website edit session (`$_SESSION['page_edit']`); save maps x/y to column/position |
| `home.php` | Two-column widget render; edit link for owner |
| `groups_widgets.php` | **501** group homes |
| store / stickers / notes / rating / trax | **501** unchanged |

Record vs notify remains `PhpretroLiveSync`. `synced_at` stays NULL.

## Validation

```sh
php tests/web_homes_test.php
php tests/phase6_habblet_batch3_test.php
```

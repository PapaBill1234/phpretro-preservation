# Group tags (`phpretro_guild_tags`)

## Result

Branch: `feature/guild-tags`. Base: current `master` (PR #27 already merged). Website-owned group tags; PolarIS `guilds` is not altered.

This is the easiest remaining 501 from the PolarIS/Nitro remaining-501 plan: PHP-only, no emulator plugin, no guessed PolarIS column.

## Why a new table

PolarIS `guilds` (`CleanDB.sql:40776`) has no tags column. User tags live in `users_settings.tags` as a semicolon-packed string. Group tags must never write that column.

## Schema (`migrations/009_guild_tags.sql`)

Installer already applies `migrations/*.sql` in name order (`install/polaris.php`). Existing installs re-run step 6; `phpretro_schema_migrations` skips files already applied.

| Column | Purpose |
| --- | --- |
| `id` | Surrogate PK |
| `guild_id` | FK `guilds.id` ON DELETE CASCADE |
| `tag` | Lowercase, `VARCHAR(20)`, same web contract as user tags |
| `created_by_user_id` | Nullable FK `users.id` ON DELETE SET NULL |
| `created_at` | Unix timestamp |
| UNIQUE `(guild_id, tag)` | Case-insensitive uniqueness via lowercase store |
| INDEX `(tag)` | Exact-match search |

No PolarIS write. Outbox events `guild.tag_added` / `guild.tag_removed` go to `phpretro_emulator_outbox` (`PhpretroLiveSync::notifyLiveGame()` still a no-op).

## Behaviour

Tag validation reuses `habbletValidUserTag` (non-empty, ≤20 chars, no `;`, `stringToURL`/`HoloText` identity) then stores lowercase. Per-guild cap 20; the 21st add returns `taglimit` so `TagWidgetPartial.errorMessage` can show `#tag-limit-message`.

| File | Result |
| --- | --- |
| `myhabbo_tag_addgrouptag.php` | POST `groupId` + `tagName`. Owner (`guilds.user_id`) or admin (`guilds_members.level_id = 1`) only. Body `valid` / `invalidtag` / `taglimit` |
| `myhabbo_tag_listgrouptags.php` | Logged-in. Inner HTML for `#profile-tag-list`. Delete controls if can-edit; `tag-add-link` for other signed-in users |
| `myhabbo_tag_removegrouptag.php` | Owner/admin; then includes list. Member/stranger is a no-op |
| `includes/habblet-templates/group-widget.php` | `#profile-tag-list`, add form for editors, `new GroupInfoWidget(guildId, userId)` |
| `ajax_tagsearch.php` | Keeps `N users.` paging. Adds `M groups.` and exact-match group rows. Does not write `users_settings.tags` |

Members (`level_id = 2`) and pending (`3`) cannot mutate. List is any signed-in user. Guests see tags on the widget without the add form.

CSRF: habblets include `habblet.php` then `habbletRequireUser()` → `Csrf::protectPost()`. Tests include via GET so the CSRF gate is skipped, same as the rest of Phase 6.

## Still 501 after this

Trax, room transfer, Flash `purchase_avatarsticker`. Club subscribe, website voucher redeem, and `show_badge_editor` later became HTTP 200 client-handoff pages ([client-handoff.md](client-handoff.md)); `update_group_badge` stays 501. Tag fight/cloud stay user-tag counts (exact semicolon match); they do not mix group hits.

## Validation

```sh
php -l includes/habblet.php habblet/myhabbo_tag_addgrouptag.php \
  habblet/myhabbo_tag_listgrouptags.php habblet/myhabbo_tag_removegrouptag.php \
  habblet/ajax_tagsearch.php includes/habblet-templates/group-widget.php \
  tests/guild_tags_test.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/guild_tags_test.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/restore_remaining_501s_test.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/phase6_habblet_batch3_test.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/phase6_habblet_batch1_test.php
```

No PolarIS plugin, custom packet, or `cms_*` schema.

# Phase 6 — habblet batch 3 of 3

## Result and audit baseline

Branch: `feature/phase6-habblet-batch3`. Base: `815d264e7b5ef3cc83b5a24191ed0910a22b8f57` (`feature/phase6-habblet-batch2`, PR #20 still open). This PR is stacked on batch 2 and is not merged or deployed.

The frozen three-way inventory from batch 1 is unchanged: 37 + 39 + 34 = 110 files. This batch migrates the 34 MyHabbo widget/home/store/trax habblets. The original audit pattern now finds **zero** remaining habblets. Phase 6's `FilterText` / old-database-call acceptance check is clean across `habblet/*.php`.

| Batch | Category | Files | State |
| --- | --- | ---: | --- |
| 1 | Messaging, friends, account and miscellaneous AJAX | 37 | PR #19; unchanged here |
| 2 | Discussions, group actions/purchase/member management | 39 | PR #20; unchanged here |
| 3 | MyHabbo profile widgets, home editing, store and trax | 34 | This PR: 4 migrated; 30 explicitly unavailable |

User-tag add/remove/list and the note-editor linktool are the only handlers with a verified Polaris mapping. Homes item placement, the web store, guestbooks, 1–5 home ratings, Trax widgets and group tags do not. `phpretro_myhabbo_layouts` and `phpretro_myhabbo_guestbook` are not substituted. Batch 1 and batch 2 handlers are unchanged. No schema migrations, invented columns, or Polaris schema alterations.

## Batch 3 behavior, file by file

All paths below are relative to `habblet/`.

| File | Result |
| --- | --- |
| `groups_widgets.php` | **Unavailable (501)** after authentication. Group home widgets are identified by a homes row, which has no native equivalent. |
| `myhabbo_guestbook_add.php` | **Unavailable (501)** — guestbook identity is a homes widget ID. The custom guestbook table has no widget mapping and is not used. |
| `myhabbo_guestbook_configure.php` | **Unavailable (501)** — public/private status was stored on `homes.variable`. |
| `myhabbo_guestbook_list.php` | **Unavailable (501)** — list paging is widget-scoped. |
| `myhabbo_guestbook_remove.php` | **Unavailable (501)** — delete authorization is widget-scoped. |
| `myhabbo_homes.php` | **Unavailable (501)** after authentication. `no_ajax` is set so the legacy full-page start/cancel/save GET/POST is not bounced by the habblet XHR gate. Editing-session ownership has no native equivalent. |
| `myhabbo_linktool_search.php` | Bound `LOCATE` search of users.username, rooms.name and guilds.name. Scope is allowlisted to habbo/room/group. Empty or unknown scopes return the original prompt with no rows. Names are escaped. IDs are native integers. `%`/`_` stay literal. |
| `myhabbo_noteeditor_place.php` | **Unavailable (501)** — stickie notes were rows in `homes`. |
| `myhabbo_rating_rate.php` | **Unavailable (501)** — 1–5 home ratings have no equivalent. `rooms.score` / `room_votes` are room votes, not profile ratings. No vote is written. |
| `myhabbo_rating_reset_ratings.php` | **Unavailable (501)** — does not delete room votes. |
| `myhabbo_sticker_place_sticker.php` | **Unavailable (501)** — sticker inventory and coordinates live in `homes`. |
| `myhabbo_sticker_remove_sticker.php` | **Unavailable (501)** |
| `myhabbo_stickie_delete.php` | **Unavailable (501)** |
| `myhabbo_stickie_edit.php` | **Unavailable (501)** |
| `myhabbo_store_inventory.php` | **Unavailable (501)** — no `homes_catalogue` / homes inventory. |
| `myhabbo_store_inventory_items.php` | **Unavailable (501)** |
| `myhabbo_store_inventory_preview.php` | **Unavailable (501)** |
| `myhabbo_store_items.php` | **Unavailable (501)** |
| `myhabbo_store_main.php` | **Unavailable (501)** |
| `myhabbo_store_preview.php` | **Unavailable (501)** |
| `myhabbo_store_purchase.php` | **Unavailable (501)** — does not debit `users.credits` or write `phpretro_transactions`. Never charge for an undeliverable sticker/background/widget. |
| `myhabbo_store_purchase_confirm.php` | **Unavailable (501)** |
| `myhabbo_tag_add.php` | Own-tag insert into `users_settings.tags`. Account ID must match the session user. Validation keeps the legacy 1–20 character / `stringToURL` web contract, plus a 20-tag cap and the native 255-character packed-string limit. Missing `users_settings` rows are not invented. Returns `valid` / `invalidtag`. |
| `myhabbo_tag_addgrouptag.php` | **Unavailable (501)** — `guilds` has no tags column. |
| `myhabbo_tag_list.php` | Reads the signed-in user's Polaris tags and retains the original list DOM, including delete controls. |
| `myhabbo_tag_listgrouptags.php` | **Unavailable (501)** — no group-tag store. |
| `myhabbo_tag_remove.php` | Own-tag removal, case-insensitive like `HabboStats.removeTag`, then re-renders the list. Foreign `accountId` is a no-op. |
| `myhabbo_tag_removegrouptag.php` | **Unavailable (501)** |
| `myhabbo_traxplayer_select_song.php` | **Unavailable (501)** — selected song was stored on a homes widget. |
| `myhabbo_widget_add.php` | **Unavailable (501)** |
| `myhabbo_widget_delete.php` | **Unavailable (501)** |
| `myhabbo_widget_edit.php` | **Unavailable (501)** |
| `myhabbo_widgets.php` | **Unavailable (501)** — profile/friends/rooms/badges/rating/trax widgets are homes items. |
| `trax_song.php` | **Unavailable (501)**. `no_ajax` is set so `/trax/song/{id}` is a real GET for the Flash player instead of an XHR-gate redirect. Polaris soundtracks and jukebox discs are a different inventory and are not served as user Trax. |

## Verified schema and source

Required references read: `PHPRetro-Modernization-Plan.md`, `Polaris-Schema-Reference.md`, `references/schema/CleanDB.sql`, and `references/Custom-Schema-Additions.md` (the actual tracked custom-reference path).

| Source | Verified columns used |
| --- | --- |
| `CleanDB.sql:55189` — `users` | `id`, `username`, `credits` |
| `CleanDB.sql:55483` — `users_settings` | `user_id`, `tags` (varchar(255), semicolon-delimited) |
| `CleanDB.sql:54683` — `rooms` | `id`, `name` (`utf8mb3_bin`) |
| `CleanDB.sql:40776` — `guilds` | `id`, `name` (no tags column, no URL alias) |

Semantics were verified in the workspace `polaris-reference` tree (source read only):

- `Emulator/src/main/java/com/eu/habbo/habbohotel/users/HabboStats.java`: `tags` is split on `;`; `addTag` trims, rejects empty/duplicate (case-insensitive), persists `String.join(";", tags)` with no trailing semicolon; `removeTag` is case-insensitive. Missing `users_settings` rows are not created here. The table comment still says the CMS must not insert settings rows.
- `WiredEffectAddTag`: wired tags are capped at 38 characters. The web UI keeps the original 20-character / `stringToURL` contract rather than widening it.
- Room tag count is a separate `rooms.tags` setting capped at 2; it is not a profile tag store.
- `TraxManager` / `InteractionMusicDisc` / `soundtracks` / `users_soundtracks` are jukebox/hotel tracks, not homes Trax widgets or user-composed Flash songs.

Every executable query branch was run against a disposable database created from those same CREATE definitions.

## Gaps deliberately not invented

- **Homes/layout editing:** no native equivalent for stickers, stickies, widgets, skins, z-index, editing sessions or `homes_edit` locks. The simplified `phpretro_myhabbo_layouts` table (`user_id`, `column_number`, `widget_key`, `position`, `visible`) cannot represent x/y/z, skins, stickers, notes or group homes. It is not substituted. Start/save/cancel and every place/remove/edit handler return 501.
- **Store:** no `homes_catalogue`. Purchase does not debit credits or write `phpretro_transactions`.
- **Guestbook:** original identity is a homes widget, with user/group owner type and a `homes.variable` privacy flag. `phpretro_myhabbo_guestbook` is keyed by `profile_user_id` only, has no widget ID, no group guestbook and no privacy column. Custom-schema text already calls this a simplified reconstruction. It is not substituted.
- **Home ratings:** `room_votes` is a binary room vote; `rooms.score` is a room quality score. Neither is a 1–5 profile rating. Rate/reset return 501 and do not touch room votes.
- **Group tags:** `guilds` has no tags column. Add/list/remove return 501 and do not write `users_settings.tags`.
- **Trax:** user-composed homes songs and widget-selected tracks have no mapping to Polaris soundtracks or music discs. The song URL and widget selector return 501 rather than serving a different catalogue.
- **Linktool group aliases:** `groups_details.alias` does not exist. Search is `guilds.name` only.
- **Live emulator caches** are not synchronized by direct CMS database writes. Tag changes are persisted the same way `HabboStats.persistTags` writes `users_settings.tags`, but an already-connected client is not notified. No verified bridge was supplied.
- **`mytagslist.php`** (batch 1) is unchanged. It still points tag editing at the hotel client; the home-page tag widget remains 501 with the rest of widget rendering.
- **Authentication tests** use a session fixture because the existing HoloUser/PDO session-serialization flow is outside this batch. No full browser login or pixel-comparison validation has been performed.

## Input, authentication and query checks

Protected handlers require a logged-in session user via `habbletRequireUser()`. Direct requests bootstrap from the repository root. The existing core XHR gate is used, except `myhabbo_homes.php` and `trax_song.php`, which set `no_ajax` for the legacy full-page/Flash GET. CSRF retrofitting remains phase 7.

All data is bound through `Database` with positional `?` parameters. Batch-3 files have no `FilterText`, legacy fetch/result/num_rows methods, `_sql` classes, `$data->` calls, `PREFIX` SQL, or raw SQL interpolation. Linktool search uses bound `LOCATE` (literal wildcards) with a bound `LIMIT 5`. Tag writes lock `users_settings` for the session user only. No missing `users_settings` row is invented. Packed tags that would exceed varchar(255) are rejected.

Output uses `HoloText`/HTML escaping. Tag add/remove keep the original `valid`/`invalidtag` and list-HTML contracts.

## Validation

- PHP **8.2.33**: **294 PHP files linted, zero failures** (293 from the batch-2 checkpoint plus the new batch-3 test).
- `tests/phase6_habblet_batch3_test.php`: **69 assertions pass** against a disposable MariaDB database created from checked-in CREATE definitions, with PHP warnings treated as exceptions. Every batch-3 endpoint is exercised. Coverage includes own-tag insert/duplicate/foreign-account/malformed/semicolon/length/array input, missing settings rows, the 20-tag web cap, the 255-character packed-string cap, case-insensitive add/remove, list DOM/empty copy, escaped linktool names, literal wildcards, injection-as-data, empty/unknown scopes, `no_ajax` on homes/trax, and every unavailable handler. Unavailable store/group-tag endpoints leave credits and tags unchanged. The scratch database is dropped in `finally`; production records/schema are not changed.
- Batch-1 regression suite: 62 assertions pass.
- Batch-2 regression suite: 171 assertions pass.
- Frozen-list comparison: exactly 34 changed habblets, zero leftover audit matches in `habblet/`.
- `git diff --check` against batch 2 passes.
- Authenticated tests use a session fixture. Full browser login, live emulator notification, and pixel-comparison validation remain unverified.

Run the integration test from the repository root with `DB_DSN`, `DB_USER`, `DB_PASS` set for a local MariaDB account that can create/drop a disposable database:

```sh
php tests/phase6_habblet_batch3_test.php
```

The test connects without selecting the application database, creates only `phpretro_phase6_batch3_test_<random>` and drops that exact database. It does not import CleanDB's destructive DROP statements or its seed data.

## Frozen batch 3 inventory

### Batch 3 — MyHabbo widgets, home/store editing and trax (34 files)

- `habblet/groups_widgets.php`
- `habblet/myhabbo_guestbook_add.php`
- `habblet/myhabbo_guestbook_configure.php`
- `habblet/myhabbo_guestbook_list.php`
- `habblet/myhabbo_guestbook_remove.php`
- `habblet/myhabbo_homes.php`
- `habblet/myhabbo_linktool_search.php`
- `habblet/myhabbo_noteeditor_place.php`
- `habblet/myhabbo_rating_rate.php`
- `habblet/myhabbo_rating_reset_ratings.php`
- `habblet/myhabbo_sticker_place_sticker.php`
- `habblet/myhabbo_sticker_remove_sticker.php`
- `habblet/myhabbo_stickie_delete.php`
- `habblet/myhabbo_stickie_edit.php`
- `habblet/myhabbo_store_inventory.php`
- `habblet/myhabbo_store_inventory_items.php`
- `habblet/myhabbo_store_inventory_preview.php`
- `habblet/myhabbo_store_items.php`
- `habblet/myhabbo_store_main.php`
- `habblet/myhabbo_store_preview.php`
- `habblet/myhabbo_store_purchase.php`
- `habblet/myhabbo_store_purchase_confirm.php`
- `habblet/myhabbo_tag_add.php`
- `habblet/myhabbo_tag_addgrouptag.php`
- `habblet/myhabbo_tag_list.php`
- `habblet/myhabbo_tag_listgrouptags.php`
- `habblet/myhabbo_tag_remove.php`
- `habblet/myhabbo_tag_removegrouptag.php`
- `habblet/myhabbo_traxplayer_select_song.php`
- `habblet/myhabbo_widget_add.php`
- `habblet/myhabbo_widget_delete.php`
- `habblet/myhabbo_widget_edit.php`
- `habblet/myhabbo_widgets.php`
- `habblet/trax_song.php`

# Phase 6 — habblet batch 1 of 3

## Result and audit baseline

Branch: `feature/phase6-habblet-batch1`. Base: `85060c38f31c677facdc94fa69590f7b585a6e03` (`master`, after PR #18). No merge or deployment is performed by this batch.

The reproducible audit finds **110 files**, not the approximate 109 in the handoff: 98 contain `FilterText(`, plus 12 with old database calls but no `FilterText(`. The old audit's exact snapshot/pattern was not supplied, so no one-file historical explanation is assumed. Files using only modern Database fetch/execute calls and empty category-handler files are not included. The full, disjoint, frozen three-way inventory is below; future batches should use these names, not recount the shrinking audit.

```sh
git grep -l -E 'FilterText\(|\$(serverdb|db)->(query|result|fetch_row|fetch_assoc|fetch_array|num_rows)' 85060c38f31c677facdc94fa69590f7b585a6e03 -- habblet
```

| Batch | Category | Files | State |
| --- | --- | ---: | --- |
| 1 | Messaging, friends, account and miscellaneous AJAX | 37 | This PR: 21 migrated/partially supported; 16 explicitly unavailable |
| 2 | Discussions, group actions/purchase/member management | 39 | Unchanged; next batch |
| 3 | MyHabbo profile widgets, home editing, store and trax | 34 | Unchanged; final batch |

The member-search paging endpoint belongs with group membership in batch 2. `groups_widgets.php` belongs with widget rendering in batch 3. `trax_song.php` stays with the MyHabbo trax widget in batch 3. `proxy.php` and `quickmenu.php` remain in batch 1 because they are mixed read-only AJAX dispatchers. This avoids splitting the tightly coupled home/store family just to equalize counts.

## Batch 1 behavior, file by file

All paths below are relative to `habblet/`.

| File | Result |
| --- | --- |
| `ajax_addFriend.php` | Friend request insert/checks with ownership, blocked-request setting and duplicate protection; email side effect removed (no preference equivalent). |
| `ajax_collectiblesConfirm.php` | Reads phpretro_collectibles.name/time metadata; purchase control removed because there is no inventory delivery mapping. |
| `ajax_collectiblesPurchase.php` | **Unavailable (501)** — The monthly collectible has no catalogue item mapping or delivery contract. |
| `ajax_confirmAddFriend.php` | Bound users.username lookup and escaped confirmation; missing account returns 404. |
| `ajax_emailcheck.php` | No SQL; removes escaping shim, validates raw scalar input; existing response tokens retained. |
| `ajax_habboclub_gift.php` | **Unavailable (501)** — No equivalent for the legacy month-indexed gifts catalogue. |
| `ajax_load_events.php` | Active room_promotions by category joined to rooms; expired/future events excluded; zero room capacity handled. |
| `ajax_namecheck.php` | Bound users.username availability query; existing naming rules and X-JSON contract retained. |
| `ajax_password.php` | No SQL; checks raw scalar password length; existing response tokens retained. |
| `ajax_redeemvoucher.php` | **Unavailable (501)** — Polaris vouchers use reward bundles, usage limits and voucher_history; legacy destructive one-use redemption is incompatible. Use the emulator redemption flow. |
| `ajax_removeFeedItem.php` | **Unavailable (501)** — No alerts table or per-user feed dismissal equivalent. |
| `ajax_tagfight.php` | Counts exact semicolon-delimited Polaris user tags, not legacy combined user/group tags. UI states this scope. |
| `ajax_tagmatch.php` | Reads user tags; percentage uses the actual intersection, avoiding the legacy total-count bug. |
| `ajax_tagsearch.php` | Bound whole-tag user search, escaped profiles and bounded paging; group tags and legacy add-tag control unavailable. |
| `ajax_updatemotto.php` | Bound users.motto update restricted to session user, 38-byte legacy limit retained, session display value refreshed without reauthentication. |
| `friendmanagement_deletefriends.php` | Deletes both directions of only the signed-in user/selected friend relationship; renders migrated list. |
| `friendmanagement_viewcategory.php` | Directional friendships joined to users; filtered counts and bounded native prepared LIMIT/OFFSET. |
| `habboclub_habboclub_reminder_remove.php` | **Unavailable (501)** — No alerts table or persistent club reminder dismissal equivalent. |
| `habboclub_habboclub_subscribe.php` | **Unavailable (501)** — Legacy optionNumber prices have no mapping to catalog_club_offers IDs/types/rewards. Never charge for an unverified offer. |
| `habbosearchcontent.php` | Bound username search, real look/last_online/online fields; native prepared paging now actually applies. |
| `minimail_confirmReport.php` | **Unavailable (501)** — No minimail equivalent: messenger_messages/members/offline do not provide subjects, mailbox trash or the legacy conversation/read model. No message is read, sent, reported or deleted here. |
| `minimail_deleteMessage.php` | **Unavailable (501)** — No minimail equivalent: messenger_messages/members/offline do not provide subjects, mailbox trash or the legacy conversation/read model. No message is read, sent, reported or deleted here. |
| `minimail_emptyTrash.php` | **Unavailable (501)** — No minimail equivalent: messenger_messages/members/offline do not provide subjects, mailbox trash or the legacy conversation/read model. No message is read, sent, reported or deleted here. |
| `minimail_loadMessage.php` | **Unavailable (501)** — No minimail equivalent: messenger_messages/members/offline do not provide subjects, mailbox trash or the legacy conversation/read model. No message is read, sent, reported or deleted here. |
| `minimail_loadMessages.php` | **Unavailable (501)** — No minimail equivalent: messenger_messages/members/offline do not provide subjects, mailbox trash or the legacy conversation/read model. No message is read, sent, reported or deleted here. |
| `minimail_recipients.php` | Own directional friendships joined to users; valid secure-wrapper JSON including empty lists and escaped names. This does not re-enable minimail. |
| `minimail_report.php` | **Unavailable (501)** — No minimail equivalent: messenger_messages/members/offline do not provide subjects, mailbox trash or the legacy conversation/read model. No message is read, sent, reported or deleted here. |
| `minimail_sendMessage.php` | **Unavailable (501)** — No minimail equivalent: messenger_messages/members/offline do not provide subjects, mailbox trash or the legacy conversation/read model. No message is read, sent, reported or deleted here. |
| `minimail_undeleteMessage.php` | **Unavailable (501)** — No minimail equivalent: messenger_messages/members/offline do not provide subjects, mailbox trash or the legacy conversation/read model. No message is read, sent, reported or deleted here. |
| `mod_add_report.php` | **Unavailable (501)** — The object report has no verified object-to-user mapping. phpretro_user_reports requires a real reported_user_id; objectId is not a user ID. |
| `myhabbo_avatarlist_avatarinfo.php` | Real users and worn users_badges lookup; missing users return 404; no old home_sql or badge helper queries. |
| `myhabbo_avatarlist_friendsearchpaging.php` | **Unavailable (501)** — No homes widget ID to profile-owner mapping. phpretro_myhabbo_layouts is a different layout model. |
| `myhabbo_friends_add.php` | Same verified friend request operation, preserving the JavaScript dialog response. |
| `mytagslist.php` | Reads the signed-in user’s Polaris tags; read-only list directs tag editing to client until batch 3 is migrated. |
| `proxy.php` | Native queries for rated/staff-picked rooms, accepted guild memberships and user-tag cloud; fixed hid allowlist. No legacy groupURL queries or Holograph badge/purchase controls. |
| `quickmenu.php` | Own directional friends, accepted guild memberships (including verified favorite/owner/admin flags), and owned rooms; fixed key allowlist. Honors hide_online for friend presence. |
| `wardrobeStore.php` | Verified users_wardrobe columns; existing figure validator and slot range retained; native transaction locks owner before insert/update (no unique slot constraint exists). |

## Verified schema and semantics

Required references read: `PHPRetro-Modernization-Plan.md`, `Polaris-Schema-Reference.md`, `references/schema/CleanDB.sql`, and `references/Custom-Schema-Additions.md`. The handoff path `references/schema/Custom-Schema-Additions.md` does not exist; the actual tracked custom reference is one directory higher.

Every SQL table/column used by the migrated handlers/helper was checked against these CREATE definitions, and every executable query branch was run against a disposable database created from those same definitions. No migration, new table, new column, or schema alteration is included. The app never inserts missing `users_settings` records; Polaris owns their creation.

| Source | Verified columns used |
| --- | --- |
| `CleanDB.sql:55189` — `users` | `id`, `username`, `motto`, `look`, `account_created`, `last_online`, `online` |
| `CleanDB.sql:55483` — `users_settings` | `user_id`, `block_friendrequests`, `club_expire_timestamp`, `tags`, `guild_id`, `hide_online` |
| `CleanDB.sql:52750` — `messenger_friendrequests` | `id`, `user_from_id`, `user_to_id` |
| `CleanDB.sql:52763` — `messenger_friendships` | `id`, `user_one_id`, `user_two_id` |
| `CleanDB.sql:55603` — `users_wardrobe` | `id`, `user_id`, `slot_id`, `look`, `gender` |
| `CleanDB.sql:55274` — `users_badges` | `id`, `user_id`, `slot_id`, `badge_code` |
| `CleanDB.sql:54683` — `rooms` | `id`, `owner_id`, `owner_name`, `name`, `description`, `users`, `users_max`, `is_public`, `is_staff_picked`, `state` |
| `CleanDB.sql:54636` — `room_votes` | `user_id`, `room_id` (one row is a vote; there is no `vote` column) |
| `CleanDB.sql:54487` — `room_promotions` | `room_id`, `title`, `description`, `start_timestamp`, `end_timestamp`, `category` |
| `CleanDB.sql:40776` — `guilds` | `id`, `name`, `room_id`, `user_id` |
| `CleanDB.sql:41336` — `guilds_members` | `id`, `guild_id`, `user_id`, `level_id` |
| `migrations/001_custom_tables.sql` — `phpretro_collectibles` | `name`, `time`; no price/catalogue-item identifier |

Additional semantics were checked in `duckietm/Polaris-Emulator` commit `0060de6b4668b8572d9b624c47eb3a141e3be30a` (source read only):

- `Emulator/src/main/java/com/eu/habbo/habbohotel/messenger/Messenger.java`: friend lists use `user_one_id` → `user_two_id`; requests use `user_from_id` → `user_to_id`; deleting a friend removes both directions.
- `Emulator/src/main/java/com/eu/habbo/habbohotel/guilds/GuildRank.java`: owner=0, admin=1, member=2, requested=3, deleted/blocked=4. Queries include only 0/1/2.
- `Emulator/src/main/java/com/eu/habbo/habbohotel/users/HabboStats.java`: `tags` is split on semicolons; `guild_id` is the favorite group; `club_expire_timestamp` is read for club membership.
- `Emulator/src/main/java/com/eu/habbo/habbohotel/rooms/RoomPromotion.java`: the event category and start/end timestamps belong to promotions.

## Gaps deliberately not invented

- **Minimail:** inspected `messenger_conversations`, `messenger_members`, `messenger_messages`, and `messenger_offline` at CleanDB lines 52734–52828. These are chat/conversation schemas, not the old subject/body mailbox. No subject, per-message recipient trash, legacy `conversationid` allocation or minimail mail-notification preference exists. All eight minimail read/write/report endpoints return 501 without touching messenger records. The independently useful recipient lookup is migrated.
- **Friend email notifications:** `users.mail/mail_verified` exist, but `email_friendrequest` does not. Request creation remains supported; the legacy email side effect is omitted.
- **Collectible purchases:** `phpretro_collectibles` has descriptive metadata only. It does not identify a deliverable catalogue item or price. Confirm shows the real metadata without an actionable purchase button; purchase returns 501 and does not debit credits.
- **Vouchers:** real `vouchers` and `voucher_history` exist (55617/55630), but they encode credits/points/catalogue rewards, usage limits and history. The legacy `(type,value)` plus delete-the-code flow is not equivalent. `vouchers` is MyISAM, so merely surrounding the old flow with a transaction would also be unsafe. This PR delegates redemption to the emulator instead of implementing an unverified partial reward/limit protocol.
- **Club:** inspected `catalog_club_offers` (1614), `users_subscriptions` (55570), and `users_settings.club_expire_timestamp`. Legacy option numbers and hardcoded prices have no established mapping to Polaris offer IDs/type/points/rewards. The old `gifts(month,type)` preview and `alerts` reminder also lack equivalents. Purchase, gift preview and reminder dismissal return 501; balances/subscriptions remain untouched.
- **Object reports:** `phpretro_user_reports` from migration 002 requires a real reporter and reported user. `mod_add_report.php` receives an object type/ID; it cannot treat that ID as a user. The endpoint does not claim `SUCCESS` or write a fabricated report. Existing `report_user.php` is unchanged.
- **Friends widget ownership:** no `homes.id` → `ownerid` mapping exists. The custom `phpretro_myhabbo_layouts` model is structurally different. Friend-search paging returns 501 instead of trusting a submitted profile owner.
- **Tags:** real semicolon-separated user tags are readable. There is no equivalent of the old combined user/group tag table. Fight/search/cloud visibly count users only. The own-tags list is read-only; legacy add/remove controls are deferred to batch 3.
- **Emulator integration:** legacy `SendMUSData` calls are removed from changed handlers. Database-backed friend/wardrobe/motto changes are verified, but immediate synchronization with an already-connected Polaris client is not claimed. Cross-process cache/notification integration needs a separate supported protocol. Owner-row locks serialize this website's duplicate-request/wardrobe writes, not arbitrary emulator writes.

## Input, authentication and query checks

`includes/habblet.php` provides the shared bootstrap, scalar string/integer readers, user gate, unavailable response and narrowly scoped friend/tag operations. Direct requests bootstrap from the repository root rather than relying on the caller's current working directory. The existing core XHR gate and session validation are used. Protected handlers require a logged-in session user; they do not assume any parent include sanitized POST/GET. This is not a rewrite of the existing session/authentication classes.

All data is bound through `Database` with positional `?` parameters. Batch-1 files have no `FilterText`, legacy fetch/result/num_rows methods, `_sql` classes, `$data->` calls, `PREFIX` SQL, or raw SQL interpolation. Output uses `HoloText`/HTML escaping or JSON encoding, as appropriate. The old global escaping pattern is not retained.

Dynamic query-shape review: `proxy.hid` and `quickmenu.key` select only fixed query branches. Friend page sizes are allowlisted to 30/50/100; all page numbers are bounded integers. LIMIT/OFFSET values are bound, never spliced into SQL. No user-selected identifier or ORDER BY expression is accepted. Existing username-search `%`/`_` wildcard behavior is retained as bound data. Tag matching uses a bound complete delimiter-wrapped tag, not LIKE wildcards.

CSRF retrofitting is still phase 7; this batch does not claim to complete it. No mail was sent during implementation or testing.

## Validation

- PHP **8.5.10**: **274 PHP files linted, zero failures** (256 application/test files plus 18 reference PHP files).
- `tests/phase6_habblet_batch1_test.php`: **62 assertions pass**. All 37 endpoints are included against native PDO/MariaDB with a disposable, randomly named database built from checked-in CREATE statements. Tests cover friend direction/duplicates/blocked requests/malformed targets, removal ownership, literal motto persistence, escaped names, pagination, missing users, real event expiry, every proxy/menu branch, tag boundaries/intersection, wardrobe insert/update/invalid slots, secure recipient JSON, and every unavailable handler. Unavailable purchase endpoints leave balances unchanged. The scratch database is dropped in `finally`; production records/schema are not changed.
- The test uses a session-user fixture (avatar URL generation is also a fixture) and the real input, locale, session-check and figure-validator code. It does **not** prove the existing full login/session serialization flow or live emulator notification behavior.
- HTTP smoke with PHP's built-in server, native bootstrap and local MariaDB: password/email/name checks, tag fight, avatar info, room proxy and own-tags widget return 200 with no PHP warnings/fatals/deprecations. Password X-JSON is `"charOk"`. An unauthenticated friend mutation returns the expected login redirect (302); a request without the XHR header is also redirected. The temporary server was stopped after the checks.
- `git diff --check` passes. Baseline inventory is exhaustive and disjoint (37+39+34=110); all 73 files assigned to batches 2/3 remain unchanged.

Run the integration test from the repository root with `DB_DSN`, `DB_USER`, `DB_PASS` set for a local MariaDB account that can create/drop a disposable database:

```sh
php tests/phase6_habblet_batch1_test.php
```

The test connects without selecting the application database, creates only `phpretro_phase6_test_<random>` and drops that exact database. It does not import CleanDB's destructive DROP statements or its seed data.

## Frozen three-way file grouping

### Batch 1 — Messaging, friends, account and miscellaneous AJAX (37 files)

- `habblet/ajax_addFriend.php`
- `habblet/ajax_collectiblesConfirm.php`
- `habblet/ajax_collectiblesPurchase.php`
- `habblet/ajax_confirmAddFriend.php`
- `habblet/ajax_emailcheck.php`
- `habblet/ajax_habboclub_gift.php`
- `habblet/ajax_load_events.php`
- `habblet/ajax_namecheck.php`
- `habblet/ajax_password.php`
- `habblet/ajax_redeemvoucher.php`
- `habblet/ajax_removeFeedItem.php`
- `habblet/ajax_tagfight.php`
- `habblet/ajax_tagmatch.php`
- `habblet/ajax_tagsearch.php`
- `habblet/ajax_updatemotto.php`
- `habblet/friendmanagement_deletefriends.php`
- `habblet/friendmanagement_viewcategory.php`
- `habblet/habboclub_habboclub_reminder_remove.php`
- `habblet/habboclub_habboclub_subscribe.php`
- `habblet/habbosearchcontent.php`
- `habblet/minimail_confirmReport.php`
- `habblet/minimail_deleteMessage.php`
- `habblet/minimail_emptyTrash.php`
- `habblet/minimail_loadMessage.php`
- `habblet/minimail_loadMessages.php`
- `habblet/minimail_recipients.php`
- `habblet/minimail_report.php`
- `habblet/minimail_sendMessage.php`
- `habblet/minimail_undeleteMessage.php`
- `habblet/mod_add_report.php`
- `habblet/myhabbo_avatarlist_avatarinfo.php`
- `habblet/myhabbo_avatarlist_friendsearchpaging.php`
- `habblet/myhabbo_friends_add.php`
- `habblet/mytagslist.php`
- `habblet/proxy.php`
- `habblet/quickmenu.php`
- `habblet/wardrobeStore.php`

### Batch 2 — Discussions, groups and member management (39 files)

- `habblet/discussions_actions_deletepost.php`
- `habblet/discussions_actions_deletetopic.php`
- `habblet/discussions_actions_newtopic.php`
- `habblet/discussions_actions_opentopicsettings.php`
- `habblet/discussions_actions_previewpost.php`
- `habblet/discussions_actions_previewtopic.php`
- `habblet/discussions_actions_savepost.php`
- `habblet/discussions_actions_savetopic.php`
- `habblet/discussions_actions_savetopicsettings.php`
- `habblet/discussions_actions_updatepost.php`
- `habblet/grouppurchase_purchase_ajax.php`
- `habblet/groups_actions_cancelEditingSession.php`
- `habblet/groups_actions_check_group_url.php`
- `habblet/groups_actions_confirm_delete_group.php`
- `habblet/groups_actions_confirm_select_favorite.php`
- `habblet/groups_actions_delete_group.php`
- `habblet/groups_actions_deselect_favorite.php`
- `habblet/groups_actions_group_settings.php`
- `habblet/groups_actions_join.php`
- `habblet/groups_actions_leave.php`
- `habblet/groups_actions_saveEditingSession.php`
- `habblet/groups_actions_select_favorite.php`
- `habblet/groups_actions_show_badge_editor.php`
- `habblet/groups_actions_startEditingSession.php`
- `habblet/groups_actions_update_group_badge.php`
- `habblet/groups_actions_update_group_settings.php`
- `habblet/myhabbo_avatarlist_membersearchpaging.php`
- `habblet/myhabbo_groups_batch_accept.php`
- `habblet/myhabbo_groups_batch_confirm_accept.php`
- `habblet/myhabbo_groups_batch_confirm_decline.php`
- `habblet/myhabbo_groups_batch_confirm_give_rights.php`
- `habblet/myhabbo_groups_batch_confirm_remove.php`
- `habblet/myhabbo_groups_batch_confirm_revoke_rights.php`
- `habblet/myhabbo_groups_batch_decline.php`
- `habblet/myhabbo_groups_batch_give_rights.php`
- `habblet/myhabbo_groups_batch_remove.php`
- `habblet/myhabbo_groups_batch_revoke_rights.php`
- `habblet/myhabbo_groups_groupinfo.php`
- `habblet/myhabbo_groups_memberlist.php`

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

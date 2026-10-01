# Phase 6 — habblet batch 2 of 3

## Result and audit baseline

Branch: `feature/phase6-habblet-batch2`. Base: `c3d7d703f101e3b4df0623445b81d4c3cfecf013` (`feature/phase6-habblet-batch1`, PR #19 still open). This PR is stacked on batch 1 and is not merged or deployed.

The frozen three-way inventory from batch 1 is unchanged: 37 + 39 + 34 = 110 files. This batch migrates the 39 discussions/groups/member-management habblets. The original audit pattern now finds exactly 34 remaining habblets, corresponding to batch 3. Zero legacy `FilterText` / old-database-call matches remain in the batch-2 files.

| Batch | Category | Files | State |
| --- | --- | ---: | --- |
| 1 | Messaging, friends, account and miscellaneous AJAX | 37 | PR #19; unchanged here |
| 2 | Discussions, group actions/purchase/member management | 39 | This PR: 31 migrated/partially supported; 8 explicitly unavailable |
| 3 | MyHabbo profile widgets, home editing, store and trax | 34 | Unchanged; final batch |

All 39 files dispatch through `includes/habblet_groups_actions.php` and `includes/habblet_groups.php`. Original HTML was extracted into `includes/habblet-templates/`. Batch 1 and batch 3 handlers are unchanged. No schema migrations, invented columns, or Polaris schema alterations.

## Batch 2 behavior, file by file

All paths below are relative to `habblet/`.

| File | Result |
| --- | --- |
| `discussions_actions_deletepost.php` | **Unavailable (501)** after authentication and scoped post lookup. ForumThreadState labels 10 staff-hidden and 20 guild-admin-hidden, while GuildForumModerateMessageEvent restricts 20 to staff. No guessed comment state is written. |
| `discussions_actions_deletetopic.php` | Permanent topic deletion for `mod_forum`, following GuildForumModerateThreadEvent.deleteThread: comments then thread, scoped to guild. Returns `SUCCESS`. Lifetime `users_settings.forums_post_count` is retained, matching the emulator. |
| `discussions_actions_newtopic.php` | New-topic form when `post_threads` allows it. Original DOM/IDs retained. |
| `discussions_actions_opentopicsettings.php` | Topic settings form for opener or `mod_forum`. Non-moderators see lock/pin radios disabled. |
| `discussions_actions_previewpost.php` | Reply preview with BBCode formatting and escaped HTML. Requires `canReply`. Hidden topics (state 10/20) are not loaded. |
| `discussions_actions_previewtopic.php` | New-topic preview. Requires `post_threads`. |
| `discussions_actions_savepost.php` | Verified reply insert: captcha, email verification, existing `users_settings` row, thread/account counters, then original post-list DOM. |
| `discussions_actions_savetopic.php` | Creates thread + first comment in a transaction. Returns the numeric group topic URL. |
| `discussions_actions_savetopicsettings.php` | Subject always writable by opener/moderator; lock/pin only written for `mod_forum`. Re-renders the post list. |
| `discussions_actions_updatepost.php` | Author or `mod_forum` may edit a visible comment. No fabricated edit timestamp. Cross-topic/post IDs 404. |
| `grouppurchase_purchase_ajax.php` | **Unavailable (501)** — no native required room, colours, badge parts or club/price policy. Does not charge or create a group. Use the game client. |
| `groups_actions_cancelEditingSession.php` | **Unavailable (501)** after authentication. `no_ajax` is set so the legacy full-page GET is not bounced by the habblet XHR gate. |
| `groups_actions_check_group_url.php` | **Unavailable (501)** for the owner. Custom group URL aliases have no Polaris schema equivalent. |
| `groups_actions_confirm_delete_group.php` | Owner-only confirmation; group name escaped. |
| `groups_actions_confirm_select_favorite.php` | Confirmation only for the signed-in accepted member/owner. |
| `groups_actions_delete_group.php` | Owner-only deletion with the verified GuildManager.deleteGuild cleanup. |
| `groups_actions_deselect_favorite.php` | Clears `users_settings.guild_id` only when it matches this group. |
| `groups_actions_group_settings.php` | Owner settings form. ADMINS-only reading, OWNER-only thread posting, and LARGE_CLOSED (state 4) return 501 rather than being downgraded. Room radios are disabled; a hidden current `roomId` is submitted. Native 50,000 member-limit copy replaces the legacy 5,000/unlimited labels. |
| `groups_actions_join.php` | Open join or exclusive request. Closed/LARGE_CLOSED rejected. Duplicate, blocked, 100-group, 50,000-member and 100-request limits match Polaris joinGuild. |
| `groups_actions_leave.php` | Member/admin/pending may leave; owner and blocked ranks cannot. Matching favorite is cleared. |
| `groups_actions_saveEditingSession.php` | **Unavailable (501)** after authentication. `no_ajax` is set for the legacy full-page POST. |
| `groups_actions_select_favorite.php` | Sets `users_settings.guild_id` for an accepted member/owner of this group only. Missing settings rows are not invented. |
| `groups_actions_show_badge_editor.php` | **Unavailable (501)** for the owner. Legacy Flash two-digit part IDs are not Polaris three-digit IDs. |
| `groups_actions_startEditingSession.php` | **Unavailable (501)** after authentication. `no_ajax` is set so `/groups/actions/startEditingSession/{id}` is a real GET instead of an XHR-gate redirect. Homes/layout placement has no native equivalent. |
| `groups_actions_update_group_badge.php` | **Unavailable (501)** for the owner. Badge edits belong in the game client. |
| `groups_actions_update_group_settings.php` | Owner save: name ≤ 30, description ≤ 250, latin1-representable, type 0–3, forum read EVERYONE/MEMBERS, thread posting EVERYONE/MEMBERS/ADMINS. Custom URL or changed `roomId` returns 501. `post_messages` is not overwritten. |
| `myhabbo_avatarlist_membersearchpaging.php` | Widget member paging. Group identity comes from `_groupspage.requested.group` (PHP normalizes dots to underscores). Widget ID is not used as a group id. Native LIMIT/OFFSET of 20. |
| `myhabbo_groups_batch_accept.php` | Admin-only accept of pending (level 3 → 2) with native join limits, transactional. |
| `myhabbo_groups_batch_confirm_accept.php` | Admin confirmation dialog. |
| `myhabbo_groups_batch_confirm_decline.php` | Admin confirmation dialog. |
| `myhabbo_groups_batch_confirm_give_rights.php` | Owner confirmation dialog. |
| `myhabbo_groups_batch_confirm_remove.php` | Admin confirmation dialog. |
| `myhabbo_groups_batch_confirm_revoke_rights.php` | Owner confirmation dialog. |
| `myhabbo_groups_batch_decline.php` | Admin-only decline/delete of pending requests. |
| `myhabbo_groups_batch_give_rights.php` | Owner-only member → admin (2 → 1). |
| `myhabbo_groups_batch_remove.php` | Admin may remove members (2); owner may also remove admins (1). Owner row protected. Matching favorite cleared. |
| `myhabbo_groups_batch_revoke_rights.php` | Owner-only admin → member (1 → 2). |
| `myhabbo_groups_groupinfo.php` | Profile-widget group info for a submitted owner. Generic group icon (incompatible badge images omitted). |
| `myhabbo_groups_memberlist.php` | Admin-only list. Pending uses 12-row pages; accepted members are unpaged as in the original. Rank icons/checkbox ids use native 0/1/2 so `homeview.js` still distinguishes admin vs member. `hide_online` is honoured. |

## Review follow-ups applied before opening the PR

- **GET / no_ajax layout actions.** Original `startEditingSession` and `cancelEditingSession` are full-page GETs (`$page['no_ajax'] = true`); `saveEditingSession` is a full-page POST. The shared habblet bootstrap was overwriting `$page`, so those clicks hit the XHR gate and redirected to `../`. Wrappers now set `no_ajax` before bootstrap, and `includes/habblet.php` preserves existing `$page` keys. The actions still return 501; they are not restored.
- **Forum author online visibility.** `HabbletGroups::author()` now applies `users_settings.hide_online` the same way as the member list and batch-1 friend presence. Hidden users render as offline.
- **Native large-group labels.** Polaris `joinGuild` uses a 50,000 accepted-member cap for every state, including LARGE (3). The settings form no longer claims a 5,000 regular cap or unlimited LARGE membership. CSS classes (`group-type-large`, radio values, ids) are unchanged.

## Verified schema and source

Required references read: `PHPRetro-Modernization-Plan.md`, `Polaris-Schema-Reference.md`, `references/schema/CleanDB.sql`, and `references/Custom-Schema-Additions.md` (the actual tracked custom-reference path).

| Table | Columns used |
| --- | --- |
| users | id, username, look, motto, online, mail_verified, account_created |
| users_settings | user_id, guild_id, hide_online, forums_post_count |
| users_badges | id, user_id, slot_id, badge_code |
| guilds | id, user_id, name, description, room_id, state, badge, date_created, forum, read_forum, post_messages, post_threads, mod_forum |
| guilds_members | id, guild_id, user_id, level_id, member_since |
| guilds_forums_threads | id, guild_id, opener_id, subject, posts_count, created_at, updated_at, state, pinned, locked, admin_id |
| guilds_forums_comments | id, thread_id, user_id, message, created_at, state |
| guild_forum_views | guild_id (cleanup); user_id and timestamp in test fixtures |
| rooms | id, owner_id, name, description, guild_id |
| items | guild_id (cleanup); id in test fixtures |

Semantics were verified in `duckietm/Polaris-Emulator` (`GuildRank`, `GuildState`, `GuildManager.joinGuild`/`deleteGuild`/`setAdmin`, `ForumThread`, `ForumThreadState`, `GuildForumPostThreadEvent`, `GuildForumModerateThreadEvent`, `GuildForumModerateMessageEvent`, `HabboStats.hideOnline`). Native ranks are owner 0, admin 1, member 2, requested 3, blocked/deleted 4. Authorization does not reuse legacy numeric comparisons. Topic and message permissions remain independent.

Thread states 0 (OPEN/new) and 1 (restore, named CLOSED in the enum but used as restored by GuildForumModerateThreadEvent) are visible. Hidden thread states 10 and 20 never leak. Permanent topic deletion is a separate verified path (state 20 on the thread moderate event).

## Gaps deliberately not invented

- **Homes/layout editing:** no native equivalent for item placement or editing-session ownership. The simplified PHPRetro layout table is not substituted. Start/save/cancel editing return 501.
- **Group URL aliases:** no equivalent; numeric group links are used. `check_group_url` and a non-empty `url` on save return 501.
- **Badges:** legacy Flash two-digit part IDs vs Polaris three-digit IDs. Editor and badge update return 501. Group-info/settings use the generic group icon. Forum badge containers remain but incompatible group badge images are omitted. Native avatar badges remain supported. No CSS/JS assets were changed.
- **Purchase:** lacks native required room, colours, badge parts and club/price policy. Does not charge or create a group.
- **Individual comment moderation:** ForumThreadState vs GuildForumModerateMessageEvent conflict on state 20. No guessed state is written. Both hidden values are redacted on read.
- **Comment edit history:** no timestamp/history column exists; message edits do not fabricate one.
- **Room transfer:** requires native room-rights effects; settings reject a changed `roomId`.
- **Unrepresentable native settings:** ADMINS-only reading, OWNER-only thread posting, and LARGE_CLOSED (state 4) return 501 rather than being downgraded.
- **Charset:** `guilds` is latin1 with a 250-character description; unsupported characters and excessive descriptions are rejected. Legacy 30-character group names and 32-character forum titles are retained.
- **Live emulator caches** are not synchronized by direct CMS database writes. No verified bridge was supplied. Do not claim instant client synchronization.
- **Out-of-batch pages:** root `groups.php`, `discussions.php` and other flows still need live testing. `discussions.php` contains reversed rank checks and legacy helper calls; it was not rewritten here. Full browser navigation is not claimed restored.
- **Authentication tests** use a session fixture because the existing HoloUser/PDO session-serialization flow is outside this batch. No full browser login or pixel-comparison validation has been performed.

## Input, authentication and query checks

Protected handlers require a logged-in session user via `habbletRequireUser()`. Direct requests bootstrap from the repository root. The existing core XHR gate is used, except the three legacy full-page editing actions which set `no_ajax`. CSRF retrofitting remains phase 7.

All data is bound through `Database` with positional `?` parameters. Batch-2 files have no `FilterText`, legacy fetch/result/num_rows methods, `_sql` classes, `$data->` calls, `PREFIX` SQL, or raw SQL interpolation. Search uses bound `LOCATE` (literal wildcards). LIMIT/OFFSET values are bound. Group/thread/post IDs are scoped together. Transactions protect multi-row writes. Membership removal clears only the affected matching favorite. No missing `users_settings` row is invented.

Unsafe BBCode parameters (`javascript:` URLs, broken room/group ids, CSS injection in colour) are stripped before the legacy formatter runs.

## Validation

- PHP **8.2.33** lint on resume: **293 PHP files, zero failures**. The original checkpoint was also linted on PHP 8.5.10 with the same result.
- `tests/phase6_habblet_batch2_test.php`: **171 assertions pass** against a disposable MariaDB database created from checked-in CREATE definitions, with PHP warnings treated as exceptions. Every batch-2 endpoint is exercised. Coverage includes native permissions, owner protection, cross-group/post attacks, malformed input, atomic rollback, favorite cleanup, real form parameter parsing, previews, counters, hidden-content redaction, captcha, native pagination, deletion cleanup, preserved HTML IDs/classes, `hide_online` on forum authors, and native 50,000 group-size copy.
- Batch-1 regression suite: 62 assertions pass.
- Frozen-list comparison: exactly 39 changed habblets, zero legacy audit matches in those files; 34 remaining matches.
- `git diff --check` against batch 1 passes.
- Authenticated tests use a session fixture. Full browser login, live emulator notification, and pixel-comparison validation remain unverified.

Run the integration test from the repository root with `DB_DSN`, `DB_USER`, `DB_PASS` set for a local MariaDB account that can create/drop a disposable database:

```sh
php tests/phase6_habblet_batch2_test.php
```

The test connects without selecting the application database, creates only `phpretro_phase6_batch2_test_<random>` and drops that exact database. It does not import CleanDB's destructive DROP statements or its seed data.

## Frozen batch 2 inventory

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

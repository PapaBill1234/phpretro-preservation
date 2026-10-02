# Polaris Real Schema Reference (verified, not guessed)
`# Polaris Real Schema Reference (verified, not guessed)`

`` Pulled directly from `duckietm/Polaris-Emulator`'s `Database/Default Database/CleanDB.sql` ``

`on 2026-09-06. This is the source of truth for the website rewrite — give this file to`

`any executor (Codex, DeepSeek, etc.) alongside every phase brief that touches SQL. Do not`

`let an executor invent table/column names "based on what seems logical" — if a table isn't`

``listed here, it must be looked up in `CleanDB.sql` directly before writing a query against it.``

`## users`

` ```sql `

``CREATE TABLE `users` (``

`  id, username, real_name, password, mail, mail_verified,`

`  account_created, account_day_of_birth, last_login, last_online,`

`  motto, look, gender, rank, credits, pixels, points,`

`  online enum('0','1','2'),`

`  auth_ticket, ip_register, ip_current, machine_id, home_room,`

`  secret_key, pincode, extra_rank,`

`  auth_ticket_expires_at, remember_token_hash, remember_token_expires_at,`

`  access_token_version, background_id, background_border_id,`

`  background_stand_id, background_overlay_id, background_card_id,`

`  last_username_change`

`)`

` ``` `

``Key differences from old PHPRetro schema: `username` not `name`, `mail` not `email`,``

`` `look` not `figure`. Password is bcrypt (compatible with PHP `password_hash()`/ ``

`` `PASSWORD_DEFAULT`). Remember-me expects a **hash** of the token in ``

`` `remember_token_hash`, not the raw token. `auth_ticket`/`auth_ticket_expires_at`/ ``

`` `access_token_version` are Polaris's own session/SSO handshake — use these instead of ``

`inventing a custom ticket system.`

`## bans`

` ```sql `

``CREATE TABLE `bans` (``

`  id, user_id, ip, machine_id, user_staff_id, timestamp,`

`  ban_expire, ban_reason,`

`  type enum('account','ip','machine','super'),`

`  cfh_topic`

`)`

` ``` `

``Real ban table. Columns are `ban_reason`/`ban_expire`, not `reason`/`expire`. Supports``

`banning by account, IP, machine ID, or all three ("super").`

`## guilds (replaces PHPRetro's "groups" concept)`

` ```sql `

``CREATE TABLE `guilds` (``

`  id, user_id, name, description, room_id, state, rights,`

`  color_one, color_two, badge, date_created,`

`  forum enum('0','1'),`

`  read_forum enum('EVERYONE','MEMBERS','ADMINS'),`

`  post_messages enum('EVERYONE','MEMBERS','ADMINS','OWNER'),`

`  post_threads enum('EVERYONE','MEMBERS','ADMINS','OWNER'),`

`  mod_forum enum('ADMINS','OWNER')`

`)`

` ``` `

`## guilds_members (replaces "user_groups"/"groups_memberships")`

` ```sql `

``CREATE TABLE `guilds_members` (``

`  id, guild_id, user_id, level_id, member_since`

`)`

` ``` `

`## guilds_forums_threads (replaces "forum_threads")`

` ```sql `

``CREATE TABLE `guilds_forums_threads` (``

`  id, guild_id, opener_id, subject, posts_count,`

`  created_at, updated_at, state, pinned, locked, admin_id`

`)`

` ``` `

``Note: `subject` not `title`; `opener_id` not `starterid`; `posts_count` is a``

`maintained counter column, not something to COUNT(*) every time.`

`## guilds_forums_comments (replaces "forum_posts")`

` ```sql `

``CREATE TABLE `guilds_forums_comments` (``

`  id, thread_id, user_id, message, created_at, state, admin_id`

`)`

` ``` `

``Note: no `title` column on individual comments (only threads have a subject);``

``no `edit_time` column visible — edit-tracking may not exist the same way.``

`## hotelview_news (replaces "news")`

` ```sql `

``CREATE TABLE `hotelview_news` (``

`  id, title, text, button_text,`

`  button_type enum('client','web'),`

`  button_link, image`

`)`

` ``` `

``Much simpler than PHPRetro's old news table — no `categories`, `summary`, `story`,``

`` `author`, or `time` columns. This is a lightweight "hotel view" announcement/banner ``

`system, not a full article/blog system. **Flag to the person:** if PHPRetro's`

`` `articles.php` (full articles with categories, archives, author bylines) is a feature ``

`you want to keep, it likely needs its own custom table added via a Polaris migration —`

`` Polaris's stock schema doesn't have an equivalent. There's also a separate `ui_news` ``

`table not yet inspected — check that before assuming a custom table is needed.`

`## Tables confirmed to exist (verified via grep, not yet fully inspected)`

`` `users_badges`, `rooms`, `room_votes`, `messenger_friendships` — pull full column ``

``definitions from `CleanDB.sql` before writing queries against these.``

`## Tables from old PHPRetro/Holograph that DO NOT exist in Polaris — do not use these names`

`` `users_bans` (→ use `bans`), `users_club` (→ check `catalog_club_offers` / subscription ``

``tables, not yet inspected), `forum_threads`/`forum_posts` (→ `guilds_forums_threads`/``

`` `guilds_forums_comments`), `groups_details`/`groups_memberships` (→ `guilds`/ ``

`` `guilds_members`), `news` (→ `hotelview_news`, but feature-scope is much smaller — ``

`see note above).`

`## How to look up anything not listed here`

``The full schema is at `Database/Default Database/CleanDB.sql` in the``

`` `duckietm/Polaris-Emulator` repo (55,908 lines, ~178 tables). Search it directly: ``

` ```bash `

``grep -n "CREATE TABLE IF NOT EXISTS \`table_name_guess\`" CleanDB.sql``

` ``` `

`If no match, list all tables matching a keyword before assuming a name:`

` ```bash `

``grep -oP "(?<=CREATE TABLE IF NOT EXISTS \`)[a-z_]*keyword[a-z_]*(?=\`)" CleanDB.sql``

` ``` `

`**Never write a query against a table name that hasn't been confirmed this way.**`

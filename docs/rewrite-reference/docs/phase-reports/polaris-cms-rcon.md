# PolarIS CMS/RCON wiring + remaining-501 reality check

## Result

Branch: `feature/polaris-cms-rcon`. Base: `feature/restore-remaining-features` (`56f5e63`, PR #25 still open). Do not merge ahead of #22–#25.

This PR does two things:

1. Categorizes the 11 remaining 501 habblets against PolarIS source (not attachments).
2. Implements the **already-confirmed-safe** Voucher / Alerts / Reports RCON/CMS wiring. Nothing else is unblocked.

No PolarIS plugin, custom packet, or invented PolarIS column. `ajax_redeemvoucher.php` stays 501.

Env (optional; pages degrade when unset):

| Variable | Use |
| --- | --- |
| `POLARIS_CMS_URL` | Game-server base or full `/api/cms/command` URL |
| `POLARIS_CMS_KEY` | `X-Cms-Key` / `cms.api.keys` key id |
| `POLARIS_CMS_SECRET` | HMAC secret |
| `POLARIS_RCON_HOST` | TCP fallback |
| `POLARIS_RCON_PORT` | TCP fallback; PolarIS default `rcon.port` is `0` (disabled) |

HMAC (PolarIS `docs/cms-api-reference.md`): `HMAC-SHA256(secret, keyId + "\n" + timestamp + "\n" + nonce + "\n" + rawBody)`, lowercase hex. CMS HTTP is preferred; TCP RCON is used only when CMS env is incomplete.

## Remaining 11 — category

`(a)` buildable now, no PolarIS fork. `(b)` PolarIS-native but the safe entry needs an online user, same caveat as `createGuild`. `(c)` blocked until PolarIS/Nitro work. Website-only `phpretro_*` reconstruction is `(a)` when PolarIS has no equivalent, matching minimail/homes.

| # | Feature | PolarIS native? | Safe live entry | Category |
| --- | --- | --- | --- | --- |
| 1 | Homepage rating | No. `room_votes` / `rooms.score` are hotel-room thumbs-up | `RoomVoteEvent` requires `currentRoom` and `points == 1`. CMS write of `room_votes` is cache-unsafe (`HabboStats.votedRooms`, in-memory `Room.score`) | **(a)** website `phpretro_*` only. **Not** `room_votes`. |
| 2 | Guestbook privacy | No guestbook table/column in PolarIS | N/A | **(a)** missing CMS column + check. Posting already works. |
| 3 | Club subscribe | Yes in client catalog + RCON `modifysubscription` | Subscription grant is online **and** offline via `getHabboInfo` → `HabboStats.load`. Credit **debit** has no RCON (`givecredits` is `@Positive`). Legacy optionNumber 1/2/3 at 20/50/80 ≠ `catalog_club_offers` 1/2 at 50+50pts / 120+120pts; no 6-month row | **(c)** for the legacy habblet. Buy club in the hotel. Do not use `GiveHC` (`type='hc'`). |
| 4 | Club reminder | No PolarIS alerts/reminder table | N/A | **(a)** website dismissal (`phpretro_feed_dismissals` already stores `hc-reminder`). PolarIS never reads it. |
| 5 | Trax (MyHabbo player) | In-room jukebox/editor only (`room_trax`, `trax_playlist`, `soundtracks`, `users_soundtracks`) | No homepage widget / no Trax RCON | **(c)** for `traxplayerwidget` / `/trax/song/{id}`. `soundmachine_songs` does not exist. |
| 6 | Store | No `homes_catalogue` | Debiting PolarIS `users.credits` is cache-unsafe if online | **(a)** CMS catalogue/inventory. Credit charge is **(b)**/unsafe without take-credits RCON. |
| 7 | Stickers | No web stickers. PolarIS stickies are in-room `InteractionPostIt` | Do not write PolarIS `items` | **(a)** CMS layout items with x/y/z. |
| 8 | Notes / stickies | Same as stickers | Same | **(a)** CMS notes. Editor/preview already render; place stays 501. |
| 9 | Group homes | `guilds.room_id` is a hotel room | Do not reuse guild room as a website page | **(a)** CMS group-home rows keyed by `guild_id`. Unrelated to createGuild. |
| 10 | Room transfer | No. `Guild.roomId` is `private final`. No `GuildChangeRoom` packet/RCON. `Guild.run()` does not persist `room_id` | Cached Guild/Room ignore CMS `guilds.room_id` / `rooms.guild_id` | **(c)** PolarIS itself cannot move a guild room after create. |
| 11 | Website voucher redeem | In-game only. `CatalogManager.redeemVoucher(GameClient)`. No `redeemvoucher` RCON. Vouchers are RAM (`loadVouchers()` on `initialize()`) | Requires a connected client | **(c)** for `ajax_redeemvoucher.php`. Housekeeping CRUD + `updatecatalog` is **(a)** and is implemented here. |

Badge editor remains **(c)** (already confirmed).

### Source receipts (checked, not guessed)

**Rating ≠ `room_votes`**

```
PREFIX.ratings (install/install_functions.php:280): userid, rating, raterid — 1–5 homepage
PolarIS RoomVoteEvent.java:6–16: points must be 1, currentRoom required
room_votes (CleanDB.sql:54636): user_id, room_id — no rating value
RoomManager.voteForRoom: in-memory score + HabboStats.votedRooms, then INSERT room_votes
```

**Guestbook privacy is a missing CMS column**

```
PREFIX.guestbook (install_functions.php:196): id, message, time, userid, ownerid, owner — no privacy
Privacy lived on PREFIX.homes.variable for the guestbook widget
phpretro_myhabbo_guestbook: no privacy column
PolarIS Java/SQL: zero guestbook hits. users_settings has no guestbook field
```

**Club subscribe / reminder**

```
catalog_club_offers (V20260518000000:1511): id 1 = 31d / 50 credits + 50 points type 5 VIP
                                         id 2 = 93d / 120 credits + 120 points type 5 VIP
confirm.php optionNumber 1/2/3 = 20/50/80 credits, 1/3/6 months — no mapping
users_subscriptions: duration in seconds, type HABBO_CLUB (Subscription.java:13)
ModifyUserSubscription.java: getHabboInfo (online or offline) → createSubscription
GiveCredits.java: credits > 0 only
No PolarIS alerts table. PickMonthlyClubGiftNotificationComposer is in-game only
```

**Trax / store / stickers / notes / group homes / room transfer**

```
TraxEditorManager + users_soundtracks / soundtracks — in-game editor, not MyHabbo
PREFIX.homes location: -1 inventory, 0 user homepage, >1 group id page
PolarIS items: hotel furniture, room_id=0 inventory. No users_items. No homes_catalogue
Guild.java:21 private final int roomId — set only in RequestGuildBuyEvent / createGuild
Guild.run() UPDATE does not include room_id
```

**Voucher redeem vs housekeeping**

```
RedeemVoucherEvent.java:29 redeemVoucher(this.client, code) — GameClient required
CatalogManager.initialize() line 345 → loadVouchers() SELECT * FROM vouchers into RAM
UpdateCatalog.java:16 CatalogManager.initialize() — the documented reload
No redeemvoucher command in cms-api-reference.md
```

## What this PR implements

### Client: `includes/PhpretroPolarisCms.php`

Transport-neutral `{key, data}` sender. Empty `data` encodes as `{}` (PolarIS `JSONUpdateCatalog` is an empty object, not an array). Injectable HTTP/TCP senders for tests.

### Vouchers (housekeeping)

`housekeeping/vouchers.php` still writes PolarIS `vouchers` (`code` varchar(10), quoted `` `limit` ``). After a successful INSERT/UPDATE/DELETE it calls `updatecatalog` so `CatalogManager.vouchers` is rebuilt. Website redeem stays 501 — there is no redeem RCON, and faking `voucher_history` + `users.credits` would double-grant against the in-memory history.

### Alerts (housekeeping)

PolarIS has **no** `alerts` table. `AlertUser.getHabbo(user_id)` is online-only (`HABBO_NOT_FOUND` if offline). `HotelAlert` broadcasts to `getOnlineHabbos()`.

`housekeeping/alerts.php` no longer writes `PREFIX.alerts` or calls `SendMUSData`. Single → `alertuser`. Mass → `hotelalert` (one broadcast, not a per-user loop). Nothing is persisted. Unconfigured PolarIS is an error on this page because sending is the whole feature.

### Reports (user-targeted only)

`CreateModToolTicket` (`modticket`) requires `@Positive reported_id` and writes PolarIS `support_tickets` (offline OK). Wired after the CMS row is committed:

- `habblet/report_user.php`
- `PhpretroMinimail::report()`

Object/room reports (`phpretro_object_reports` / `mod_add_report.php`) do **not** call `modticket` — there is no honest `reported_id`. If PolarIS is down or unconfigured, the website report still succeeds.

## Tests

`tests/polaris_cms_rcon_test.php` on disposable MariaDB `127.0.0.1:3307`:

- HMAC matches PolarIS `keyId\ntimestamp\nnonce\nrawBody`
- CMS preferred over RCON; RCON used when CMS env is incomplete
- `updatecatalog` body is `{"key":"updatecatalog","data":{}}`
- Minimail report + `report_user.php` fire `modticket` with usernames and `reported_room_id=0`
- Object reports do not fire `modticket`
- Unconfigured PolarIS still stores `phpretro_user_reports`
- `ajax_redeemvoucher.php` remains 501
- `alerts.php` has no `PREFIX` / `SendMUSData` persist path

Existing minimail / restore-remaining tests still pass: unconfigured `tryCommand` is a no-op.

## Not in this PR

Rating, guestbook privacy, club subscribe, club reminder habblet, Trax, store, stickers, notes, group homes, room transfer, badge editor, PolarIS plugins, `cms_*` schema, website voucher redeem, take-credits, `GiveHC`.

# Club / voucher / badge client-handoff

## Result

Branch: `feature/client-handoff`. Base: current `master` (PR #46 already merged). Honest HTTP 200 pages that tell the user to do the action in the hotel client.

This is the next remaining-501 slice after group tags: PHP-only copy and dialog HTML. No PolarIS writes, no fake 20/50/80 club prices, no `voucher_history` / credits grant, no Flash `BadgeEditor.swf`.

## Why not restore these on the website

| Feature | Why a website grant would be a lie |
| --- | --- |
| Club subscribe | Legacy `optionNumber` 1/2/3 at 20/50/80 coins is not PolarIS `catalog_club_offers` (CleanDB default: 31d/50cr+50pts and 93d/120cr+120pts, VIP). There is no take-credits RCON. `GiveHC()` writes `users_subscriptions.subscription_type = 'hc'`; PolarIS uses `HABBO_CLUB`. |
| Website voucher redeem | PolarIS `CatalogManager.redeemVoucher` needs a live `GameClient`. There is no `redeemvoucher` RCON. Writing `voucher_history` from PHP would double-grant against the in-memory catalogue. Looking up the code would leak whether it exists. |
| Flash badge editor | Flash part encoding ≠ PolarIS `guilds.badge` string. `update_group_badge` must not write `guilds.badge`. |

Trax, guild room transfer, and a native PolarIS Club buy stay PolarIS work and are **not** this slice.

## Behaviour

Handoff is HTTP **200** with `X-PHPRetro-Feature: client-handoff`. That is not `habbletUnavailable()` (HTTP 501 + `X-PHPRetro-Feature: unavailable`). Prototype dialogs dump `responseText` into the page; a 501 dump looked like a broken feature. 200 HTML with an Open hotel button is the honest contract.

Shared helpers in `includes/habblet.php`: `habbletClientOpenButton()` / `habbletClientHandoff()`. CSRF is unchanged: habblets include `habblet.php` then `habbletRequireUser()` → `Csrf::protectPost()`. Tests include via GET so the CSRF gate is skipped, same as the rest of Phase 6.

| File | Result |
| --- | --- |
| `habboclub_habboclub_confirm.php` | 200 handoff. No `optionNumber` 400, no fake 20/50/80, no `credits_sql`. |
| `habboclub_habboclub_subscribe.php` | 200 handoff. No `X-JSON daysLeft` (that would fake membership in `habboclub.js`). No `GiveHC()`, no credit debit. |
| `ajax_redeemvoucher.php` | 200. Re-renders the purse form (`#purse-habblet-redeemcode-string`, `#purse-redeemcode-button`) plus a handoff notice. `PurseHabblet` replaces `#voucher-form` innerHTML and rebinds the button. SELECT `users.credits` only. Does not touch `vouchers` / `voucher_history`. |
| `groups_actions_show_badge_editor` | Owner-only 200 handoff. `homeview.js` `openGroupBadgeEditor` puts the body in `#badge-editor-dialog-body`. Never embeds `BadgeEditor.swf`. |
| `groups_actions_update_group_badge` | Stays **501**. Never writes `guilds.badge`. |
| `club.php` | Membership status stays. Buy buttons / `habboclub.js` / fake 20/50/80 prices removed. Copy + Open hotel. |
| `credits.php` | Sample copy now says redeem the voucher in the hotel. |

Do not SELECT `catalog_club_offers` (tests often lack the table; hotels can change prices). Do not look up voucher codes.

## Still 501 after this

Trax (`traxplayerwidget`, `myhabbo_traxplayer_select_song.php`, `trax_song.php`), guild room transfer (`roomId` change in group settings), Flash `purchase_avatarsticker`, `update_group_badge`. Native Club buy stays in the PolarIS catalog.

## Validation

```sh
php -l includes/habblet.php includes/habblet_groups_actions.php \
  habblet/habboclub_habboclub_subscribe.php habblet/habboclub_habboclub_confirm.php \
  habblet/ajax_redeemvoucher.php club.php credits.php tests/client_handoff_test.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/client_handoff_test.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/restore_remaining_501s_test.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/phase6_habblet_batch1_test.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/phase6_habblet_batch2_test.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/polaris_cms_rcon_test.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/web_group_urls_test.php
DB_DSN='mysql:host=127.0.0.1;port=3307' DB_USER=root DB_PASS= \
  php tests/restore_remaining_features_test.php
```

No PolarIS plugin, custom packet, or `cms_*` schema. Do not merge a combined mega-PR with Trax/Nitro.

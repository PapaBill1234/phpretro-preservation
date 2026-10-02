# Website group URL aliases

## Result

Branch: `feature/web-group-urls`. Base: `feature/web-homes` (PR #23). Do not merge ahead of homes / minimail / batch 3.

Custom `/groups/{alias}` routes are restored as a **website-owned** table. PolarIS `guilds` is not given an alias column. Live-game notify is a separate no-op hook.

## Schema

| Source | Columns used |
| --- | --- |
| `migrations/005_web_group_urls.sql` — `phpretro_group_url_aliases` | `alias` PK, `guild_id` UNIQUE FK `guilds.id` ON DELETE CASCADE, `created_at`, `synced_at` |
| `migrations/003_web_minimail.sql` — `phpretro_emulator_outbox` | `groups.alias_claimed` pending rows |
| `CleanDB.sql:40776` `guilds` | `id`, `user_id` (owner check only). No `alias` / `name_seo` |

Verified absent:

```sh
python3 - <<'PY'
import re
text=open('references/schema/CleanDB.sql').read()
m=re.search(r'CREATE TABLE IF NOT EXISTS `guilds` \(.*?\) ENGINE=.*?;', text, re.S)
print('alias' in m.group(0), 'name_seo' in m.group(0))
PY
# False False
```

`synced_at` is NULL on every website write. Outbox rows stay `pending` because `PhpretroLiveSync::notifyLiveGame()` is empty.

## Behaviour

| File | Result |
| --- | --- |
| `groups_actions_check_group_url.php` | Owner-only validation. Valid URL returns confirmation + cannot-alter warning. Invalid/taken/reserved returns `ERROR …` (Habbo JS contract). Does not write. |
| `groups_actions_update_group_settings.php` | Owner may claim an alias once. Existing aliases are not changed. Invalid alias returns 400 and does not write `guilds`. Room-id changes stay **501**. |
| `groups_actions_group_settings.php` | No alias yet → enabled input (`noalias=true`). Claimed → read-only `/groups/{alias}` link. |
| `habbletGroupURL` / `groupURL` | Alias path when claimed, otherwise `/groups/{id}/id`. No longer queries the missing `groups.name_seo` column. |
| `groups.php` / `discussions.php` | `phpretroRequestGuildId()` resolves `?id=` or `?alias=`. `.htaccess` already routes `/groups/{alias}`. |
| Badge editor / room move / group homes | **501** unchanged |

Record vs notify: `claim()` calls `record()` then `notifyLiveGame()`. Step 2 is a no-op today.

Validation matches original PHPRetro: length ≤ 30, `stringToURL($alias, false, false)` identity, uniqueness, reserved `actions|id|discussions|home`, reject purely numeric (so `/groups/123` cannot collide with `/groups/123/id`).

## Gaps still 501 / not invented

- PolarIS `guilds` is not given an alias column.
- Room transfer and the Flash badge editor stay 501.
- Group homes stay 501.
- No PolarIS plugin / custom packet / Java consumer.

## Validation

```sh
php tests/web_group_urls_test.php
# PASS: 44 assertions
php tests/phase6_habblet_batch2_test.php
# Batch 2: 176 assertions passed.
php tests/web_homes_test.php
# PASS: 28 assertions
```

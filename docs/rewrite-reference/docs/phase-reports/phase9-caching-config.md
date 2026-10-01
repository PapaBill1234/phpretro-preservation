# Phase 9 — Caching + config/secrets

Branch: `feature/phase9-caching-config`. Base: `master` (`2a98cc7`, after PR #29). This PR is not merged or deployed.

Secrets stay out of source. Settings and language strings go through a `Cache` interface instead of a DB hit (or a full language-file parse) on every lookup.

PHP was not available in the implementation environment, so `php -l` and `php tests/cache_test.php` were not run here. `tests/cache_test.php` is a no-database unit test covering FileCache, RedisCache (injected client), factory fallback, and the config.php / `.env.example` acceptance checks.

## Secrets

**Acceptance:** `grep -rn "password\|secret" includes/config.php` — no matches. The file is only an `.env` loader (`putenv` / `$_ENV`). No literals.

| Secret | Where it lives now |
| --- | --- |
| DB DSN / user / password | `DB_DSN`, `DB_USER`, `DB_PASS` (already used by `includes/Database.php`) |
| Mail from / name / log | Optional `MAIL_FROM`, `MAIL_FROM_NAME`, `MAIL_LOG` — override `phpretro_site_settings` when set |
| PolarIS CMS / RCON | `POLARIS_CMS_URL`, `POLARIS_CMS_KEY`, `POLARIS_CMS_SECRET`, `POLARIS_RCON_HOST`, `POLARIS_RCON_PORT` (already used by `PhpretroPolarisCms::fromEnv()`) |
| Redis auth | `REDIS_PASSWORD` (optional; FileCache is the default driver) |

`.env` is gitignored. `.env.example` documents every variable with empty/safe placeholders. `install/polaris.php` writes `DB_*` plus `CACHE_DRIVER="file"` and still never writes a `config.php` full of passwords.

## Cache

`includes/Cache.php`:

| Type | Role |
| --- | --- |
| `Cache` | `get` / `set` / `delete` / `clear` |
| `FileCache` | Default. JSON files under `CACHE_PATH` or `./cache/*.cache`. Key is sha256. Atomic write. |
| `RedisCache` | `CACHE_DRIVER=redis`. ext-redis, else Predis. JSON values. Falls back to FileCache if neither client is loaded. |
| `CacheFactory` | `CACHE_DRIVER` selects the implementation. `activeDriver()` is `file` or `redis`. |

`./cache/.htaccess` denies `.ret`, `.php`, and `.cache`. Generated cache files are gitignored.

PHP sessions stay on the default session handler. The cache is for settings, language, and hotel-status — not a session store.

## Wiring

| Lookup | Before | After |
| --- | --- | --- |
| `$settings->find(...)` | `SELECT` of all `phpretro_site_settings` on every request | Read `settings:all` from Cache; DB only on miss or `generateCache()` |
| `$lang->addLocale(...)` | `require` of `includes/languages/{lang}.php` on every call | Read `locale:{lang}:{key}` from Cache; `require` only on miss |
| Maintenance flag in `core.php` | Extra `SELECT` of `maintenance_mode` every request | `$settings->find('maintenance_mode')` (cached) |
| `HotelStatus()` | Wrote executable PHP to `./cache/status.ret` | `hotel:status` cache key, 30-minute TTL |

`HoloSettings::generateCache()` rebuilds `settings:all` from the DB. Housekeeping settings save still calls it. Maintenance mode POST also calls it so the lock is not stuck on a stale value.

Env mail overrides are applied after cache/DB load so a changed `MAIL_FROM` does not wait on a cache bust.

## Files touched

| File | Change |
| --- | --- |
| `includes/Cache.php` | New. Interface + FileCache + RedisCache + CacheFactory |
| `includes/config.php` | Comment only: loader, no credentials |
| `includes/classes.php` | Require Cache.php; HoloSettings and HoloLocale go through Cache |
| `includes/core.php` | Maintenance flag from `$settings->find()`, not a second SELECT |
| `includes/functions.php` | `HotelStatus()` uses Cache instead of `status.ret` |
| `housekeeping/cache.php` | Status page reports driver + rebuilds a missing settings cache |
| `housekeeping/maintenance.php` | `generateCache()` after writing `maintenance_mode` |
| `install/polaris.php` | Writes `CACHE_DRIVER="file"` into `.env` |
| `.env.example` | Full variable list |
| `.gitignore` | `.env`, generated cache files |
| `cache/.htaccess` | Deny `.cache` |
| `tests/cache_test.php` | No-DB unit tests |
| `docs/phase-reports/phase9-caching-config.md` | This report |

## Reviewer checks

1. `grep -rn "password\|secret" includes/config.php` — empty.
2. `includes/config.php` has no `DB_PASS="..."`, `MAIL_...="..."`, or API key literals.
3. `.env.example` lists DB, mail, PolarIS, and cache/Redis vars.
4. `HoloSettings::find()` does not query inside `find()`; the constructor reads Cache and only SELECT-s on miss.
5. `HoloLocale::addLocale()` does not `require` the language file when the locale key is already cached.

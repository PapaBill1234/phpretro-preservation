# Restore Phase 4 features

## Summary

Restored the Phase 4-batch-1 feature reductions that now have project-owned schema:

- `articles.php` reads full articles, category links/filtering, paginated archives, author bylines, summaries, stories, and image galleries from `phpretro_news`.
- `collectables.php` displays the current month and historical showroom from `phpretro_collectibles`.
- `clientutils.php` persists generic client-error telemetry to `phpretro_client_errors` only when `client_log_errors` is enabled.
- `migrations/001_custom_tables.sql` creates all three project-owned tables.

## Files changed

- `articles.php`
- `collectables.php`
- `clientutils.php`
- `migrations/001_custom_tables.sql`
- `docs/phase-reports/restore-phase4-features.md`

## Tables and columns used

All SQL tables below were verified against `references/Custom-Schema-Additions.md`, the project-owned custom-schema source. No stock Polaris table was queried by this task, so no `CleanDB.sql` table or column lookup was required.

| File | Table | Columns |
| --- | --- | --- |
| `articles.php` | `phpretro_news` | `id`, `title`, `summary`, `story`, `author`, `categories`, `images`, `time` |
| `collectables.php` | `phpretro_collectibles` | `name`, `description`, `image`, `time` |
| `clientutils.php` | `phpretro_client_errors` | `user_id`, `ip`, `error_type`, `message`, `stack_trace`, `user_agent`, `url`, `client_version`, `created_at` |
| `migrations/001_custom_tables.sql` | all three tables | Matches the documented CREATE TABLE statements exactly |

Verification source: `references/Custom-Schema-Additions.md` (retrieved from GitHub at blob `af38e4cd1b294e6389f156196eb48e9cf62bb5c1`).

## Nitro client-error convention

Investigated the actual Habbo HTML5 client repository, [HabForge/Nitro](https://github.com/HabForge/Nitro), rather than unrelated projects named Nitro.

Source searches performed against its `main` branch:

```text
window.onerror                → no matches
addEventListener('error'      → no matches
unhandledrejection            → no matches
reportError                   → no matches
```

No existing client-to-backend error-reporting endpoint or payload convention was found. This implementation therefore uses the documented `phpretro_client_errors` fallback design. It accepts generic optional request fields (`error_type`, `message`, `stack_trace`, `url`, `client_version`) and supports the legacy `error`, `error_message`, and `hookmsga` values as fallback inputs. It does not claim Nitro already sends those parameters.

## Assumptions

- News categories retain the documented legacy comma-separated format. Filtering uses `FIND_IN_SET` after normalizing a comma-plus-space separator.
- The existing collectables purchase JavaScript remains untouched. This task restores page data only; it does not invent an ownership or purchase table because no such custom or Polaris schema was specified.
- Logging remains opt-in through the existing `client_log_errors` setting.

## Flagged / unresolved

- Nitro does not currently provide a server-error telemetry convention to match. A future Nitro integration must explicitly call this endpoint with the documented generic fields before browser-side errors will arrive here.
- PHP lint must be run in the target deployment/CI environment because this task was performed GitHub-only at the requested workflow boundary; no source files were saved or executed locally.

## php -l results

Not run: the available execution environment has no PHP executable. The attempted command, `php -l -`, returned:

```text
The term 'php' is not recognized as a name of a cmdlet, function, script file, or executable program.
```

No repository checkout or source file was saved locally. Run the following in CI or the target deployment environment before merge:

```bash
php -l articles.php
php -l collectables.php
php -l clientutils.php
```

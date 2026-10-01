# Reference-work reorganization report

## Scope and archive handling

This change places the uploaded work from `references/` (the repository's archive
directory; referred to as `/reference/` in the task) into its intended project
locations.  The archive was deliberately left unchanged so it remains a complete
paper trail.

The placement order follows the modernization plan: when the archive contains
multiple versions of a file, the latest numbered phase wins.  There were no
ambiguous version-order decisions.

## Placed files

| Archive source | Project destination | Selection rationale |
| --- | --- | --- |
| `references/PHPRetro-Modernization-Plan.md` | `PHPRetro-Modernization-Plan.md` | Replaced the earlier root-level task template with the full modernization plan supplied in the archive. |
| `references/PHPRetro-Plain-English-Guide.md` | `docs/PHPRetro-Plain-English-Guide.md` | Documentation belongs under `docs/`; no prior project destination existed. |
| `references/includes/core.txt` | `includes/core.php` | Phase 1 compatibility version; the `.txt` extension is archival only. |
| `references/includes/phase 3/includes/Database.php` | `includes/Database.php` | Latest supplied `Database` version. |
| `references/includes/phase 2/includes/db_smoke_test.php` | `tests/db_smoke_test.php` | The file declares this intended destination and the plan specifies the same test path. |
| `references/includes/phase 3/includes/classes.php` | `includes/classes.php` | Latest Phase 3 auth/session version supersedes the loose Phase 1 copy. |
| `references/includes/phase 3/includes/functions.php` | `includes/functions.php` | Latest Phase 3 version supersedes the loose Phase 1 copy. |
| `references/includes/phase 3/login_popup.php` | `login_popup.php` | Root-level authentication page. |
| `references/includes/phase 3/logout.php` | `logout.php` | Root-level authentication page. |
| `references/includes/phase 3/reauthenticate.php` | `reauthenticate.php` | Root-level authentication page. |
| `references/includes/phase 3/security_check.php` | `security_check.php` | Root-level authentication page. |
| `references/includes/phase 4/account.php` | `account.php` | Root-level page. **Schema rework required; see below.** |
| `references/includes/phase 4/articles.php` | `articles.php` | Root-level page. **Schema rework required; see below.** |
| `references/includes/phase 4/client.php` | `client.php` | Root-level page. **Schema rework required; see below.** |
| `references/includes/phase 4/clientutls.php` | `clientutils.php` | The archive filename has a typo, but its `// FILE:` declaration and application routes identify the intended `clientutils.php` destination. **Schema rework required; see below.** |
| `references/includes/phase 4/club.php` | `club.php` | Root-level page. **Schema rework required; see below.** |
| `references/includes/phase 4/collectables.php` | `collectables.php` | Root-level page. **Schema rework required; see below.** |
| `references/includes/phase 4/community.php` | `community.php` | Root-level page. **Schema rework required; see below.** |
| `references/includes/phase 4/credits.php` | `credits.php` | Root-level page. **Schema rework required; see below.** |
| `references/includes/phase 4/discussions.php` | `discussions.php` | Root-level page. **Schema rework required; see below.** |

## Skipped archive files

| Archive source | Why it was not copied |
| --- | --- |
| `references/includes/classes.txt` | Superseded by `references/includes/phase 3/includes/classes.php`, which is the latest version of this file. |
| `references/includes/functions.txt` | Superseded by `references/includes/phase 3/includes/functions.php`, which is the latest version of this file. |
| `references/includes/phase 2/includes/Database.php` | Superseded by the Phase 3 copy. The two copies are byte-identical, but Phase 3 remains the latest source. |
| `references/includes/phase one thinking notes.txt` | Working notes, not a project source file; retained only in the archive. |
| `references/includes/phase 4/phase 4 notes.txt` | Phase deliverable/working notes, not a project source file; its relevant cautions are captured in this report. |

## Required follow-up: Phase 4 Polaris schema rework

**Every Phase 4 file was placed as requested, but none should be considered
production-ready until its SQL receives a Polaris schema rework pass.**  These
files were written for the old PHPRetro/Holograph schema and were intentionally
not corrected during this reorganization.

The confirmed incompatibilities include:

- `articles.php` and `community.php` query the old `news` table and columns such
  as `time`, `summary`, and `header_image`; Polaris documents `hotelview_news`
  with a materially different, smaller column set.
- `community.php` and `discussions.php` query old `forum_threads` and
  `forum_posts`; Polaris uses `guilds_forums_threads` and
  `guilds_forums_comments`, with different column names and semantics.
- `discussions.php` queries old `groups` and `user_groups`; Polaris uses
  `guilds` and `guilds_members`.
- `collectables.php` assumes a `collectibles` table and `time`, `name`, `desc`,
  and `image` columns that are not confirmed by the supplied Polaris reference.

Before deploying or testing Phase 4 against a database, validate every table and
column against Polaris's `CleanDB.sql` as required by
`Polaris-Schema-Reference.md`, then make the schema-specific corrections in a
separate reviewable change.  No Phase 4 SQL was silently changed here.

## Checks performed

- Confirmed that the Phase 2 and Phase 3 `Database.php` copies are byte-identical.
- Confirmed the archive itself has no modified, deleted, or added files.
- Linted all PHP files after placement.  The database smoke test is linted but
  was not executed because it requires configured database credentials and a
  disposable MySQL instance.

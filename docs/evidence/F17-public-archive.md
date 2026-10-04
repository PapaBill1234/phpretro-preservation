# F17 public archive route evidence

Status: source-backed evidence and synthetic golden test only. No production route or handler is implemented here.

## Verified original source

The original Stage 3 checkout was read-only for this verification. Its bytes match `docs/stage3-original-phpretro-sha256.csv`:

| File | Manifest SHA-256 | Verified SHA-256 | Result |
| --- | --- | --- | --- |
| `stage3-original-phpretro/.htaccess` | `c714a08718a6e032488bb1a7c10fe253eec12b12c3682adce73e22d5e68684bd` | `c714a08718a6e032488bb1a7c10fe253eec12b12c3682adce73e22d5e68684bd` | match |
| `stage3-original-phpretro/articles.php` | `041fd442b696c12d0f3ce2bdfdd2312fb7fe44ac4d94c8244cafe74ccb02a893` | `041fd442b696c12d0f3ce2bdfdd2312fb7fe44ac4d94c8244cafe74ccb02a893` | match |

Relevant source citations, using the verified files and `nl -ba` line numbering:

- `.htaccess:46` maps `GET /articles/archive` to `articles.php?archive=true [QSA]`.
- `.htaccess:47` defines the archive page-number form.
- `articles.php:18` sets `allow_guests=true`.
- `articles.php:19-22` loads core/session/community setup.
- `articles.php:24-32` reads request parameters and performs the initial news lookup.
- `articles.php:53-60` emits the archive and paging sections.
- `articles.php:139-150` selects archive rows with `SELECT * FROM PREFIX_news ORDER BY time DESC LIMIT 20`, with an optional page offset.
- `articles.php:188-201` renders the article wrapper/detail content branch.

These facts establish original-source behavior only. They do not authorize a CMS schema, a Go product contract, row contents or provenance, or runtime/database behavior not directly observed.

## Captured response provenance

The disposable capture authority is `C:\Users\Karim\AppData\Local\hermes-phpretro\capture-evidence\F17-public-archive-20261004\capture-manifest.json`. Its manifest hash and the declared hashes of `content_read.body` and `content_read.headers` were verified before recording these facts. The helper sequence captures `/articles/archive` after `public_root` and `login_page` and before `login_submit`; it follows redirects and stores headers and body separately.

| Artifact | Manifest value | Verified value | Result |
| --- | --- | --- | --- |
| `content_read.body` bytes | `10296` | `10296` | match |
| `content_read.body` SHA-256 | `4086e3ddfe758ecb82f90a3dc6c46c9fbdb1c51ddcee5d513d970ea5e31f9886` | `4086e3ddfe758ecb82f90a3dc6c46c9fbdb1c51ddcee5d513d970ea5e31f9886` | match |
| `content_read.headers` SHA-256 | `a935af6c45f2c58111589e3a47f141eb2cfd436b2ee70acba193e7e9b1ae541d` | `a935af6c45f2c58111589e3a47f141eb2cfd436b2ee70acba193e7e9b1ae541d` | match |

Observed final response: `200 OK`; no `Location` header; no `Set-Cookie` header; `Content-Type: text/html; charset=UTF-8`; `Cache-Control: no-store, no-cache, must-revalidate, post-check=0, pre-check=0`. Observed body markers are `article-archive`, `article-paging`, and `article-wrapper`.

The installer literals `stage3admin`, `Stage3Pass!`, `stage3@example.invalid`, and `wrong-stage3-password` are absent from the captured body. Generic words such as `password` or `login` may occur; this record makes no broader credential-string claim.

The real body and header hashes above are provenance only, not synthetic expected hashes. Raw third-party capture files remain local and are not copied into tracked evidence. Because the request used a pre-existing cookie jar, no `Set-Cookie` response does not prove that a fresh session was absent.

## Explicit unknowns

The following remain UNKNOWN:

- CMS `news` table schema;
- row provenance and content;
- runtime and database semantics beyond the observed response;
- request-cookie and session provenance;
- any behavior not represented by the cited source or observed capture facts.

## Synthetic test boundary

`tests/golden/archive_route_test.go` uses self-contained synthetic response bytes and `tests/golden.Compare`. Its expected body hash is computed from the synthetic fixture, not copied from the capture. It checks acceptance and rejects mismatches for method, status, redirect/`Location`, selected header, cookie, required marker, and synthetic body hash. It does not read local capture files or require Docker, production data, or a live database.

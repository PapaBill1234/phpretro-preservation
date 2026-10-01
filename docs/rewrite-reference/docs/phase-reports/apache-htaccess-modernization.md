# Apache `.htaccess` modernization

## Scope

Modernizes the root Apache configuration for the PHP 8.5/XAMPP deployment while preserving the application's legacy public URL patterns. This change does not alter PHP page logic, database schema, Polaris tables, or Nitro integration.

## Verified deployment facts

- XAMPP Apache has `mod_rewrite`, `mod_authz_core`, `mod_headers` and the legacy compatibility module loaded.
- The root `DocumentRoot` is `C:/xampp/htdocs` and permits `.htaccess` overrides.
- Apache is version-2.4-style, so `Require all denied` is the supported authorization directive.

## Changes

1. Replaces Apache 2.2 `Order`/`Deny` rules with Apache 2.4 `Require all denied` rules.
2. Blocks dotfiles and deployment/configuration extensions such as `.env`, `.ini`, `.sql`, `.log`, backup files and YAML files.
3. Removes the obsolete `mod_php5` configuration block. PHP 8 settings belong in XAMPP `php.ini`.
4. Disables directory indexes and uses `SymLinksIfOwnerMatch` rather than unrestricted symlink following.
5. Makes rewrite rules terminal with Apache 2.4's `END` flag, preventing later rules from rewriting an already-resolved route.
6. Corrects the tag-search route, which previously attempted to match a query string in a `RewriteRule` path pattern.
7. Places the specific `/credits/habboclub` route before the generic `/credits/*` route so it can be reached.
8. Removes unbound `$1` substitutions from the MyHabbo save and purchase-confirm routes.
9. Escapes literal dots in URL patterns and removes the duplicate archive-with-query rule; `QSA` on the archive route preserves `pageNumber`.

## Validation

- `httpd -M` confirmed the required Apache modules.
- `http://127.0.0.1/no-such-page` remains a 404 through `ErrorDocument /error.php`.
- Existing public routes were probed before and after the change: error page, tag search, cache check and credits page.
- Sensitive file paths such as `/.env` and `/*.sql` must return 403 or 404 and never their contents.
- Apache configuration is checked with `httpd -t` and the affected PHP pages are linted separately by the existing full-tree PHP lint check.

## Follow-up improvements intentionally deferred

- Move this configuration into the Apache virtual-host configuration for production, then set `AllowOverride None`. The current deployment relies on root `.htaccess` and must retain it for now.
- Add HTTPS/HSTS, CSP, compression and cache headers only after the production hostname, TLS termination and Nitro asset/CDN policy are known. These are host-level security/performance decisions.
- Retire or redirect legacy Flash routes such as `/trax/song/*` in the combined Polaris/Nitro remaining-501 implementation. They remain routed to their current 501 handler until that feature ships.
- Replace broad legacy route captures with named, documented route tests as pages are rebuilt. This PR preserves their compatibility instead of changing URL semantics broadly.

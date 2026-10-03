# F8 localization and cache evidence

## Scope

F8 adds a synthetic localization contract and locale-aware cache identity. Changes are limited to `internal/localization/**` and the locale-key helper/tests in `internal/cache/**`. No frontend, production data, credentials, CMS, or schema ownership is involved.

## Localization contract

Catalogs use version `catalog.v1`, a supported BCP-47-style locale set (`en-US`, `en-GB`, `fr-FR`, `fr-CA`), and the known synthetic message keys `home.title` and `home.welcome`. `ValidateCatalog` rejects unsupported versions/locales, unknown keys, and blank values. `ResolveLocale` produces a deterministic, duplicate-free chain: exact locale, the first configured sibling locale for the language, then `en-US`; an empty request uses `en-US`. Malformed locale strings are rejected. `Translate` searches that chain and returns `(value, true)` only for an explicitly supplied non-empty message; unknown or missing keys return `(empty, false)`.

## Cache contract

`LocalizedKey` validates the locale through the localization contract and adds `locale:<locale>:` to the existing approved namespace/id key. Thus `en-US`, `fr-FR`, and the non-localized key cannot collide. Unsupported, blank, or malformed locales return `ErrNamespace`. Existing cache behavior remains cache-only: MariaDB is authoritative, expiry/outage reads are misses, and writes/invalidation do not claim success during outage.

## Tests and synthetic fixtures

`internal/localization/localization_test.go` covers deterministic regional fallback, default locale, invalid catalogs, malformed locale requests, and missing-key behavior. `internal/cache/localized_test.go` proves locale-varying keys and rejects invalid locales. Fixtures contain only synthetic strings and identifiers.

## Verification

- `go test ./internal/localization ./internal/cache`: not runnable in this environment because Go is not installed or on PATH (`go: command not found`).
- File writes were verified by the workspace tool; no external systems were changed.
- Required Go verification remains to be run in a Go 1.24+/1.25.13 environment: `gofmt`, focused tests, `go test -race`, and `go vet`.

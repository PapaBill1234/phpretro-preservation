# F12 backend localization and cache regression evidence

## Scope and boundary

This synthetic-only slice adds regression coverage under `internal/localization/` and `internal/cache/`, plus this evidence file. It does not change production code, schemas, routes, authentication, dependencies, network behavior, or real rows.

## Regression coverage

- `ValidateCatalog` rejects an unsupported `catalog.v1` version, unsupported locale, unknown message key, and blank message.
- `ValidateLocale` rejects empty, language-only, whitespace-containing, newline-containing, and unsupported locales.
- `ResolveLocale` and `Translate` retain exact locale, deterministic sibling fallback, default fallback, and explicit missing-key behavior.
- Repeated fallback resolution remains stable and does not mutate `SupportedLocales`.
- The canonical plain cache key remains `namespace + id`; localized identity is `namespace + id + locale:<locale>:` and cannot collide with the plain key.
- Invalid localized locales continue to return `ErrNamespace`.

## Verification

Run from the repository root with the pinned toolchain image:

    docker run --rm -v "$PWD:/src" -w /src golang:1.24.6 gofmt -d internal/localization internal/cache
    docker run --rm -v "$PWD:/src" -w /src golang:1.24.6 go test ./...
    docker run --rm -v "$PWD:/src" -w /src golang:1.24.6 go test -race ./...
    docker run --rm -v "$PWD:/src" -w /src golang:1.24.6 go vet ./...
    git diff --check

Results:

- Docker-pinned `golang:1.24.6` `gofmt -w internal/localization/*.go internal/cache/*.go`: passed.
- Docker-pinned `golang:1.24.6` `go test ./...`: passed for all packages.
- Docker-pinned `golang:1.24.6` `go test -race ./...`: passed for all packages.
- Docker-pinned `golang:1.24.6` `go vet ./...`: passed.
- `git diff --check`: passed.

Exact changed paths: `internal/localization/localization_test.go`, `internal/cache/localized_test.go`, and `docs/evidence/F12-backend-localization-cache.md`. Unknowns: no production integration or real catalog/cache rows were exercised by design; this is synthetic contract evidence only. All fixtures are synthetic.
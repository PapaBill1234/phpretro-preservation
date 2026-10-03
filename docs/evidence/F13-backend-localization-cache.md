# F13 backend localization and cache boundary evidence

## Scope and boundary

This synthetic-only slice adds regression coverage under `internal/localization/` and `internal/cache/`, plus this evidence file. It does not change production code, schemas, routes, authentication, dependencies, network behavior, or real rows.

## Regression coverage

- Canonical locale spellings remain distinct from case variants and extended region variants; unsupported variants resolve only through the stable default fallback.
- Supported sibling-region fallback chains remain deterministic and duplicate-free.
- Catalog validation rejects language-only, malformed, case-variant, extended-region, and control-character locale values.
- Localized cache identities remain distinct for every supported canonical locale and reject non-canonical locale input.
- Existing tests retain plain-versus-localized separation, malformed serialization rejection, expiry, invalidation, and outage behavior.

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

Exact changed paths: `internal/localization/localization_test.go`, `internal/cache/localized_test.go`, and `docs/evidence/F13-backend-localization-cache.md`. Unknowns: no production integration or real catalog/cache rows were exercised by design; all fixtures are synthetic. The tests preserve the existing boundary that locale normalization is strict rather than silently accepting case or extended-region variants.
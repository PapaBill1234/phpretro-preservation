# F14 backend localization and cache regression evidence

## Scope and boundary

This synthetic-only slice adds deterministic regression coverage under `internal/localization/` and `internal/cache/`, plus this evidence file. It does not change production code, schemas, routes, authentication, dependencies, network behavior, or real rows.

Base SHA: `126f6aa` (authoritative F13 recovery from accepted origin/main).

## Exact synthetic fixtures and coverage

- Canonical locale fixtures: `en-US`, `en-GB`, `fr-FR`, `fr-CA`, empty locale, and unsupported `de-DE`.
- Fallback edge cases verify exact identity, sibling fallback, default fallback, and stable empty-request behavior.
- Malformed locale fixtures contain spaces, tabs, and newlines; validation and resolution reject them.
- Cache identity fixtures vary locale and identifier, including an identifier containing locale-like text; all localized identities remain distinct.

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

Unknowns: no production integration or real catalog/cache rows were exercised by design; all fixtures are synthetic. Locale-shaped strings without whitespace are intentionally outside this slice because the existing resolver contract treats unsupported shapes as default-fallback candidates.

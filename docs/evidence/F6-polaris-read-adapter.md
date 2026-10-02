# F6 PolarIS disposable read adapter evidence

Status: implemented in `internal/polaris`; synthetic-only tests; no production connection or rows.

## Scope and source citations

- Profile mapping follows `docs/evidence/F3-profile-schema.md`: `users.id`, `username`, `motto`, `look`, `gender`, and `account_created` only. Credential, authorization, contact, network, room, and token columns are not selected.
- Account password verifier input follows `docs/evidence/F1-password-scheme.md`: only `users.id`, `username`, and `password` are selected for the existing account contract.
- News mapping follows `docs/evidence/F5-content-schema.md`: `hotelview_news.id`, `title`, `text`, `button_text`, `button_type`, `button_link`, and `image`.
- Existing contracts are unchanged: `internal/account.Store`, `internal/profile.Store`, and `internal/content.Store`.

## Query contracts

`Store` receives an injected `*sql.DB` and performs reads only. Every query has an explicit column list. Account and profile lookups use bound `?` arguments and `LIMIT 1`; news uses the fixed, non-parameterized contract `ORDER BY id DESC LIMIT 10`, regardless of caller input. Database errors are wrapped with operation context. Profile `sql.ErrNoRows` becomes `profile.ErrNotFound`; account no-row behavior remains a wrapped database error because the existing account contract has no not-found sentinel.

## Synthetic evidence

`internal/polaris/store_test.go` registers a dependency-free in-process `database/sql/driver` fixture. It records SQL and bound values, returns deterministic synthetic rows, asserts exact query strings and mappings, and exercises profile `sql.ErrNoRows` mapping plus wrapped account database errors. No network, external driver, real rows, credentials, migration, or write path is used.

## UNKNOWNs and boundaries

The adapter does not infer columns beyond the cited evidence, does not interpret unknown enum values (existing `content.Service` validates them), and does not add handlers, configuration, migrations, or production wiring. The disposable fixture does not establish deployed-row characteristics.

## Verification

- `gofmt -w internal/polaris/store.go internal/polaris/store_test.go`: passed.
- `go test ./...`: passed for account, content, foundation, polaris, profile, session, and golden packages.
- `go test -race ./...`: passed for all packages.
- `go vet ./...`: passed.

The host Go toolchain remains unavailable; Docker is the reproducible execution path. The first adapter test run exposed only an incomplete expected argument list for the three-query fixture; the expectation was corrected, and later runs also added nil-database, profile-not-found, database-error, and exact-query assertions.

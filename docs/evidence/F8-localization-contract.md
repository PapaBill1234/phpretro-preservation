# F8 localization contract evidence

## Scope and synthetic fixtures

Implemented only the approved localization boundary. Catalog fixtures are in-memory synthetic values (`en-US`, `fr-FR`, and requested `fr-CA` fallback). No production data, Redis, CMS writes, credentials, or runtime catalog execution are used.

## Contract

- Catalog version is `catalog.v1`; unsupported versions/locales and unknown message keys are rejected.
- Supported locales are `en-US`, `en-GB`, `fr-FR`, and `fr-CA`.
- Fallback order is deterministic: exact supported locale, first supported locale sharing the language, then `en-US`, with duplicates removed.
- Missing keys return an explicit `{ missing: true, value: undefined }` (TypeScript) or `(value, false)` (Go); no unrelated locale is silently substituted.
- Localized React view-model fields retain the translation result and missing state.
- Cache keys include `locale:<locale>:` and are tested against both another locale and the existing non-locale key.
- Catalogs are data-only maps; no code/template evaluation is performed. Locale is presentation metadata and does not affect authorization, routing, CSRF, audit, or database ownership.

## Verification commands and results

- `git diff --check`: passed.
- `npm test` (frontend): unavailable in this checkout because the configured `tsc` executable is missing from `frontend/node_modules/.bin`; the command exits before compilation with `'tsc' is not recognized`.
- `npm install --ignore-scripts --no-audit --no-fund`: completed but did not provide the missing executable; no package/dependency changes were requested or made.
- Go host checks: unavailable because `go` is not installed.
- Docker Go check: not completed; the repository's Docker files are the legacy PHP/MariaDB stage3 setup and do not define a Go test image. A Go image would be an unreviewed dependency for this bounded task.

## Unknowns

- Full frontend typecheck/test and Go test/race checks remain unverified until the project toolchains are available.
- No production catalog schema, locale inventory, cache deployment, or integration behavior was inspected by design.

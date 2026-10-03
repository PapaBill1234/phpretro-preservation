F12 frontend localization presentation regression

Scope

- Synthetic frontend localization only.
- Catalogs require catalog.v1, a supported message set, and a non-empty locale.
- Locale selection is deterministic: regional locale, language locale, then configured default.
- Localized presentation emits the typed home.v1 view model.
- Missing keys remain explicit as placeholders or throw when requested.

Coverage

- frontend/src/localization/index.ts
- frontend/tests/localization.test.ts

Verification

- npm ci --include=dev --ignore-scripts: pass (6 packages, 0 vulnerabilities).
- npm run typecheck: pass.
- npm test: pass (9 tests, 0 failures).
- git diff --check: pass (line-ending warnings only).

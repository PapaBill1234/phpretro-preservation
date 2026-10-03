F13 frontend localization view-model regressions

Scope

- Synthetic frontend localization only; no routes, runtime loading, storage, network, or production data.
- Catalog validation rejects unsupported versions, malformed locales, missing messages, and unknown message keys.
- Locale selection is case-insensitive and deterministic: regional locale, language locale, then configured default.
- Localized presentation emits the stable typed home.v1 shape and preserves the selected catalog locale for display state.
- Missing keys remain explicit as placeholders or throw when requested.

Coverage

- frontend/src/localization/index.ts
- frontend/tests/localization.test.ts

Verification

- npm ci --include=dev --ignore-scripts: pass (6 packages, 0 vulnerabilities).
- npm run typecheck: pass.
- npm test: pass (11 tests, 0 failures).
- git diff --check: pass (line-ending warnings only).

Boundary evidence: all fixtures are synthetic and changes are limited to the exact F13 frontend localization paths.
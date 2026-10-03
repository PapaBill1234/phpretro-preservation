F14 frontend localization regression hardening

Scope

- Synthetic frontend localization only; no runtime loading, routes, auth, persistence, dependencies, or production data.
- Catalog validation rejects arrays, whitespace-padded or malformed locale tags, missing keys, and extra keys.
- Locale selection is deterministic and case-insensitive, with regional, language, then configured-default fallback.
- Ambiguous catalogs whose locale tags normalize to the same value are rejected explicitly.
- Localized presentation preserves the typed home.v1 view-model shape and stable navigation href.

Fixtures

- Existing synthetic en and fr catalog.v1 fixtures.
- Invalid whitespace locale, invalid underscore locale, malformed requested locale, and duplicate en/EN catalog fixtures.
- FR-ca request fixture verifies normalized regional fallback to fr and exact typed output.

Verification

- Base SHA: 031a336 (accepted origin/main).
- npm ci --include=dev --ignore-scripts: pass (6 packages, 0 vulnerabilities).
- npm run typecheck: pass.
- npm test: pass (15 tests, 0 failures).
- Focused localization test: pass (7 tests, 0 failures).
- Visual-focused test: pass (5 tests, 0 failures).
- npm run build: pass.
- git diff --check: pass.

Unknowns

- No runtime catalog loading or production catalog semantics were introduced.

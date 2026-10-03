# F12 visual localization boundary evidence

Scope: synthetic presentation-only locale display states. No assets, routes,
schemas, authentication, persistence, credentials, or production data are used.

Evidence paths:

- `frontend/tests/localization.test.ts`
- `frontend/src/localization/index.ts` (read-only contract under test)
- `frontend/src/viewModel.ts` (read-only `home.v1` contract under test)

The focused tests establish that:

- `en-US` and `fr-FR` resolve to the synthetic `en` and `fr` catalogs.
- Both display states expose exactly the fixed `home.v1` keys: `version`,
  `locale`, `siteTitle`, `welcome`, and `navigation`.
- Locale-specific presentation strings change, while the navigation target stays
  `/` and the view-model version stays `home.v1`.
- Unknown locales use the same deterministic `en` fallback regardless of case.
- Catalog validation rejects missing and extra keys; no capability is added.

Verification from the assigned worktree:

- `npm ci --include=dev --ignore-scripts` — passed.
- `npm run typecheck` — passed.
- `npm run build && node --test dist/tests/localization.test.js` — passed;
  9 tests passed.
- `git diff --check` — passed.

# F14 visual localization presentation boundaries

Base SHA: `126f6aa` (authoritative F13 recovery from accepted origin/main).

Scope: synthetic, presentation-only regression coverage. The fixture uses the
existing `syntheticCatalogs` English and French catalogs and the read-only
`createLocalizedHomeViewModel` / `acceptHomeViewModel` contracts. No source
behavior, routes, schemas, authentication, credentials, dependencies, assets,
persistence, capability data, or production data are changed.

The focused fixture in `frontend/tests/visual-localization.test.ts` verifies:

- `en-US` and `fr-FR` render deterministic `en` and `fr` display states.
- Unknown `zz-ZZ` and `ZZ-zz` requests produce the same English fallback labels.
- Every state exposes exactly `version`, `locale`, `siteTitle`, `welcome`, and
  `navigation`, with `version` fixed to `home.v1` and accepted by the typed
  home view-model boundary.
- Locale display strings vary without changing the stable navigation target `/`.
- No route, auth, authentication, session, persistence, storage, capability,
  token, user, or permission fields appear in the output; navigation remains
  limited to `label` and `href`.

Unknowns and explicit non-claims: this is synthetic display-state coverage only;
it does not test a browser, server, login flow, session store, persistence layer,
route registration, or capability enforcement.

Verification from this worktree:

- `npm ci --include=dev --ignore-scripts` — passed.
- `npm run typecheck` — passed.
- `npm run build` — passed.
- `node --test dist/tests/visual-localization.test.js` — passed; 5 tests passed.
- `git diff --check` — passed.

Allowed changed files: `frontend/tests/visual-localization.test.ts` (new) and
this evidence document only.

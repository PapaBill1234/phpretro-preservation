# F46-F60 Candidate Design

Status: provisional design only. This document does not authorize implementation, schema changes, CMS writes, production enablement, authentication or authorization changes, security exceptions, runner changes, asset import, or feature scope approval. The current queue still defers F9+ implementation. All identifiers are reserved for this document's planning horizon and must be reconciled by the F31-F60 synthesis coordinator against the live board before acceptance.

## Shared decision record

- Accepted design base checked in this worktree: `473e1206c4dd63bdbb4a9da914bdc43b1a1bdb9b`.
- Current presentation authority is the synthetic React boundary in `frontend/src/themeManifest.ts:1-33`, `frontend/src/viewModel.ts:1-24`, and `frontend/src/StarterShell.tsx:1-6`; F7 evidence requires typed view models and a presentation-only capability. F8 requires data-only catalogs, deterministic fallback, locale-varying cache keys, and no route/auth/CSRF/audit/schema effects.
- Original-source claims below rely on the read-only F18-F30 research result. Verified source hashes: `housekeeping/index.php` `35437309c6d55af4893034db5ae329b51000836bdff9b3b1c2fe3e086a4cb905`; `housekeeping/news.php` `685f147ec6db963d6bb8796c291d72a2bdd0e84c64ba804f40637108beacdaf7`; `housekeeping/settings.php` `3307a95980161774ee746d038efca3f96f4adc6bfd9382de9856aed5de77a2cf`; `housekeeping/logs.php` `b57ed095c7fd37f43e3da21a6081b93e7d91ec37cc502c63f69f4667bde34d35`; `templates/community_header.php` `131991d4d5db23d3cb537ddcb07931efc2191c04e4aa2ef46d46ae88efa5cd17`; `templates/housekeeping_header.php` `4c7c34ce1d190c58e0590c0eac70438af6dacb21a4a488d42d97d0242454a092`.
- `community.php` (`113fcfcbf177f357bc6a4204bf1db31c473319db4c6c79b8bf14b9b326d16ef0`) and `articles.php` (`041fd442b696c12d0f3ce2bdfdd2312fb7fe44ac4d94c8244cafe74ccb02a893`) are cross-reference only and do not duplicate F17 archive evidence.
- No housekeeping/admin/theme-production browser capture is retained. CMS schema, row provenance, staff permissions, locale storage, asset provenance, publication/rollback semantics, and production rendering are UNKNOWN unless explicitly marked below.
- Owner: `visual` owns presentation-only synthetic fixture work after scope approval. `frontend` owns approved React implementation. `coordinator` owns roadmap numbering, schema/ownership/security/production decisions. Independent reviewer: `reviewer` for every implementation or evidence candidate.
- Per-unit provisional cap: 20,000 uncached input tokens, 10,000 cached input tokens, 6,000 output tokens, 60 minutes. Stop on missing evidence, hash mismatch, secret, guessed schema/ownership, unsafe asset path, authorization/CSRF/audit uncertainty, provider failure, or request outside the exact paths.

## Candidate units

### F46 - Typed website view-model envelope

- Observable contract: an approved website presentation model is versioned, strictly typed, escaped, and contains only fields declared by its view-model version; unsupported versions and malformed values are rejected.
- Authority: new website-owned design authority constrained by `viewModel.ts:1-24` and F7 evidence; no original source claim.
- Proposed paths: `frontend/src/viewModel.ts`, `frontend/tests/contracts.test.ts`, `docs/evidence/F46-typed-view-model.md`.
- Missing decisions: final API schema, field ownership, HTML/URL sanitization policy, and approval of any fields beyond `home.v1`.
- Negative tests: reject unknown version, missing required field, route/auth/session/permission/token/storage fields, unsafe URL or HTML; prove presentation cannot grant capability.
- Readiness: proposal-ready synthetic boundary, not code-ready. Owner `frontend`; reviewer `reviewer`.
- Acceptance: typed fixture tests pass, forbidden capability fields are rejected, and schema authority is recorded before implementation. Stop if the contract needs backend schema or identity decisions.

### F47 - PHPRetro-compatible React theme package

- Observable contract: a versioned React theme consumes the approved view model and changes presentation only; selecting it cannot alter route, identity, session, authorization, CSRF, audit, or persistence behavior.
- Authority: new website-owned design authority constrained by `themeManifest.ts:1-33`, `StarterShell.tsx:1-6`, and F7 evidence.
- Proposed paths: `frontend/src/themes/phpretro/**`, `frontend/src/themeManifest.ts`, `frontend/tests/theme-contract.test.ts`, `docs/evidence/F47-phpretro-theme.md`.
- Missing decisions: measured original markup/golden markers, final component inventory, CSS/asset provenance, and browser baseline.
- Negative tests: reject non-React entry, extra capability, unsupported view model, database/network/process imports, route-changing theme output, and unvalidated HTML/assets.
- Distinctness: this is the validated, versioned package/manifest boundary after the unresolved F30 theme/CMS slot; it does not claim F30's broad theme/localization/CMS scope or public content behavior.
- Readiness: proposal-ready synthetic boundary; original parity is evidence-needed. Owner `visual` then `frontend`; reviewer `reviewer`.
- Acceptance: manifest and fixture tests prove capability boundary; no original template is copied without provenance and golden evidence. Stop on missing browser capture or asset rights.

### F48 - Modern theme package and provenance-checked assets

- Observable contract: an optional modern theme may render only reviewed, provenance-recorded assets through a validated manifest; it cannot execute reference application code or access arbitrary paths.
- Authority: new website-owned design authority. The modernization draft names a modern-assets directory but does not prove license, compatibility, or permission; Atom/Pixel63/SWF remain outside authorization.
- Proposed paths: `frontend/src/themes/modern/**`, `frontend/src/assets/provenance/**`, `frontend/tests/theme-assets.test.ts`, `docs/evidence/F48-modern-theme-assets.md`.
- Missing decisions: asset inventory, creator/license/terms, hashes, dimensions, allowed URLs, visual captures, and owner approval. No asset path is currently code-ready.
- Negative tests: reject missing provenance, path traversal, executable uploads, external/unallowlisted URLs, capability expansion, and reference application code.
- Readiness: evidence-needed and owner gate. Owner `visual`; reviewer `reviewer`.
- Acceptance: every selected asset has source, retrieval date, hash, creator/terms and a synthetic render fixture; otherwise leave unfilled. Stop on unresolved rights or Atom/Pixel63/SWF dependency.

### F49 - Versioned locale catalog package boundary

- Observable contract: a versioned, data-only catalog package is validated as a complete release artifact before activation, including locale metadata, declared key inventory, fallback declarations, and catalog/content compatibility; this is a package/schema-validation boundary, not F8's already-accepted in-memory lookup and fallback behavior.
- Authority: F8 evidence and `frontend/src/localization/**` establish the existing lookup baseline; the package manifest, completeness checks, and activation handoff are new website-owned design authority and remain unapproved.
- Proposed paths: `frontend/src/localization/catalogPackage.ts`, `frontend/tests/localization-package.test.ts`, `docs/evidence/F49-locale-catalog.md`.
- Missing decisions: production locale inventory, catalog storage/ownership, package signing or hash policy, activation permissions, translated content scope, and compatibility policy for content versions.
- Negative tests: reject unsupported package/catalog versions, incomplete declared keys, executable values, duplicate locale/key entries, incompatible content version, and locale-dependent route/auth fields.
- Readiness: proposal-ready synthetic package boundary; production catalog activation is gated. Owner `visual`/`frontend`; reviewer `reviewer`.
- Acceptance: synthetic package fixtures prove manifest validation and compatibility checks beyond F8's lookup tests, while preserving fixed `home.v1` keys and explicit missing state. Stop if persistence, signing, or activation requires schema/security decisions.

### F50 - Locale-aware cache integration and invalidation

- Observable contract: an approved locale-aware presentation response is stored and retrieved under a normalized locale-varying cache key, with explicit TTL and invalidation on catalog/package activation; a stale or unavailable cache cannot be reported as an authoritative publication.
- Authority: F8 evidence lines 9-15 establishes that locale must vary cache keys; F7 evidence lines 11-13 establishes the injected cache outage, expiry, namespace, serialization, and invalidation boundary. The integration of those contracts for catalog-backed presentation is new and is not authorized here.
- Proposed paths: `internal/cache/**`, `internal/localization/**`, `frontend/tests/localization-cache-contract.test.ts`, `docs/evidence/F50-locale-cache-invalidation.md`.
- Missing decisions: supported production locale list, cache namespace and authority, TTL per response/package, invalidation trigger and ordering, stale-while-revalidate policy, and outage behavior at the API boundary.
- Negative tests: cross-locale key collision, wrong namespace, expired entry, catalog activation without invalidation, invalidation failure, cache outage, and a cache hit changing route/auth/capability fields. F8 fallback behavior is dependency context, not this unit's acceptance criterion.
- Readiness: evidence-needed integration contract; ownership/TTL/invalidation gate. Owner `backend` with `visual` fixture support; reviewer `reviewer`.
- Acceptance: synthetic tests prove distinct normalized locale keys, explicit TTL, activation invalidation, and outage-as-miss/failure semantics using the F7 cache double; no production Redis or catalog write. Stop on unspecified TTL, cache authority, or invalidation ordering.

### F51 - Housekeeping capability shell

- Observable contract: an authenticated housekeeping React shell displays only server-authorized capabilities, uses a dedicated housekeeping style within the same theme architecture, and cannot grant permissions by UI visibility.
- Authority: original `housekeeping/index.php:18-59` (rank/session/login boundary), hash above; `templates/housekeeping_header.php:18-20,27-56,72-115` shows legacy navigation coupling. Source is behavior evidence, not code to copy.
- Proposed paths: `frontend/src/housekeeping/**`, `frontend/tests/housekeeping-capabilities.test.ts`, `docs/evidence/F51-housekeeping-shell.md`.
- Missing decisions: staff identity/session contract, capability registry, rank semantics, API schema, browser capture, and CSRF/audit ownership.
- Negative tests: unauthenticated access, insufficient rank, hidden-control bypass, forged capability, missing CSRF, and audit failure must all fail closed.
- Readiness: evidence-needed; owner/security/schema gate. Owner `coordinator` plus `frontend`; reviewer `reviewer`.
- Acceptance: only after an approved capability contract and negative browser tests; no staff implementation or production enablement from this design. Stop on rank-to-permission ambiguity.

### F52 - Website-owned pages and safe slugs

- Observable contract: an approved website-owned page model has stable identifiers, validated route-safe slugs, locale variants, draft/published state, and presentation metadata without arbitrary template execution.
- Authority: new website-owned design authority; no retained CMS schema or admin capture. Original `housekeeping/news.php:55-135` is adjacent field evidence only, not proof of page schema.
- Proposed paths: `frontend/src/content/pages/**`, `internal/content/**` only after scope approval, `frontend/tests/pages-contract.test.ts`, `docs/evidence/F52-pages.md`.
- Missing decisions: schema ownership, slug collision/redirect rules, editor permissions, publication semantics, and API contract.
- Negative tests: reject traversal, duplicate/conflicting slugs, executable markup, unauthorized draft access/edit/delete, CSRF failure, and partial audit.
- Readiness: owner/security/schema gate. Owner `coordinator`; reviewer `reviewer`.
- Acceptance: explicit website-owned schema and atomic audited mutation contract approved before any implementation card. Stop on PolarIS ownership overlap.

### F53 - Navigation and button management

- Observable contract: approved navigation entries render stable labels, destinations, visibility, ordering, locale variants, and theme-compatible metadata while route behavior remains server-owned.
- Authority: `templates/community_header.php:228-338,344+` and `templates/housekeeping_header.php:72-115` show legacy navigation coupling; exact modern schema is UNKNOWN.
- Proposed paths: `frontend/src/content/navigation/**`, `frontend/tests/navigation-contract.test.ts`, `docs/evidence/F53-navigation.md`.
- Missing decisions: source-of-truth schema, destination allowlist, role/locale visibility policy, ordering conflict resolution, and mutation audit.
- Negative tests: reject external/unallowlisted destinations, duplicate order, hidden-route leakage, unauthorized writes, CSRF failure, and non-atomic audit.
- Readiness: evidence-needed and owner/security/schema gate. Owner `coordinator`; reviewer `reviewer`.
- Acceptance: synthetic read fixture may be proposed; writes require approved schema, authorization, CSRF, prepared SQL, same-transaction audit, and browser contract.

### F54 - Website-owned FAQ, banner, and landing composition models

- Observable contract: website-owned view models expose only approved escaped fields and stable ordering for FAQ, banner, and landing compositions; this excludes the F24 community projection and F29 article/category projection. Public display does not imply editor or publication authority.
- Authority: new website-owned design authority, with `community.php:369-428` and `articles.php:188-209` retained only as adjacent legacy rendering context; hashes above. F17 owns archive evidence, F24 owns community reads, and F29 owns article/category projection.
- Proposed paths: `frontend/src/content/public/**`, `frontend/tests/public-content-contract.test.ts`, `docs/evidence/F54-public-content.md`.
- Missing decisions: exact website-owned schema, row provenance, rich-text policy, image ownership, pagination/order, browser captures, and relation to F17.
- Negative tests: reject unescaped HTML/script, unknown columns, arbitrary image paths, private/draft leakage, and unauthorized mutation.
- Readiness: evidence-needed; owner/schema gate, with explicit non-overlap review against F24/F29. Owner `frontend` for synthetic read model, `coordinator` for schema; reviewer `reviewer`.
- Acceptance: no duplicate F17 archive, F24 community, or F29 article/category contract; synthetic fixtures must identify fields and unknowns. Stop on missing response facts or schema inference.

### F55 - Publication, preview, and rollback boundary

- Observable contract: a future approved publication operation activates one validated version atomically, preserves the prior version for rollback, and never partially activates a locale, page, navigation, theme, or catalog.
- Authority: new website-owned design authority only. No production CMS/admin capture or publication/rollback evidence exists.
- Proposed paths: `frontend/src/content/publication/**`, `internal/content/publication/**`, `frontend/tests/publication-contract.test.ts`, `docs/evidence/F55-publication-rollback.md`.
- Missing decisions: version schema, approver roles, transaction boundary, cache invalidation, audit event, preview isolation, and operational recovery.
- Negative tests: unauthorized publish/rollback, CSRF failure, stale version, partial write, audit failure, cache stale read, and cross-locale activation.
- Readiness: blocked pending owner/security/schema/production decisions. Owner `coordinator`; reviewer `reviewer`.
- Acceptance: only a design review may proceed until atomicity and audit semantics are source-backed or explicitly approved. Stop on any best-effort publication behavior.

### F56 - Media metadata and safe asset selection

- Observable contract: content references media by validated website-owned metadata and allowlisted identifiers, never arbitrary filesystem paths, executable uploads, or unverified external URLs.
- Authority: new website-owned design authority; `housekeeping/news.php:55-135` exposes legacy image fields but does not establish safe upload semantics or schema ownership.
- Proposed paths: `frontend/src/media/**`, `frontend/tests/media-contract.test.ts`, `docs/evidence/F56-media-metadata.md`.
- Missing decisions: storage authority, upload policy, MIME/content inspection, size limits, provenance/license fields, retention, and access control.
- Negative tests: reject traversal, spoofed MIME, executable content, oversized payload, unverified provenance, unauthorized replacement/delete, CSRF failure, and missing audit.
- Readiness: blocked by owner/security/schema gate. Owner `coordinator`; reviewer `reviewer`.
- Acceptance: metadata-only synthetic fixture can be designed; no upload or storage implementation without explicit safe-upload contract and review.

### F57 - Status, maintenance, cache invalidation, and audit views

- Observable contract: an approved housekeeping view displays status/maintenance state, records explicit cache invalidation outcomes, and exposes immutable audit history without treating presentation state as authority.
- Authority: `housekeeping/settings.php:18-110` (rank 7, settings save/cache regeneration) and `housekeeping/logs.php:18-72` (rank 5, log search/list), hashes above; unsafe arbitrary settings behavior is not a recommended contract.
- Proposed paths: `frontend/src/housekeeping/operations/**`, `frontend/tests/operations-contract.test.ts`, `docs/evidence/F57-status-audit.md`.
- Missing decisions: settings metadata/schema, status ownership, cache namespace/TTL, audit schema/retention, operator permissions, and outage semantics.
- Negative tests: unauthorized status change/invalidation, CSRF, cache outage, audit-write failure, arbitrary setting key, log tampering, and sensitive-data disclosure.
- Readiness: evidence-needed and owner/security/schema gate. Owner `coordinator`; reviewer `reviewer`.
- Acceptance: synthetic read-only fixture may record UNKNOWNs; mutation requires same-transaction audit and explicit cache contract. Stop on arbitrary settings or production operations.

### F58 - Browser contracts for themes and housekeeping

- Observable contract: browser tests verify initial rendering, navigation, locale display, failure states, keyboard/accessible names, and housekeeping authorization without allowing theme or locale selection to change security behavior.
- Authority: F7/F8 synthetic contracts, `StarterShell.tsx:4-5`, `frontend/tests/visual-localization.test.ts:8-71`; no approved CMS browser capture exists.
- Proposed paths: `frontend/tests/browser/**`, `docs/evidence/F58-browser-contracts.md`.
- Missing decisions: approved browser runner, viewport matrix, golden markers, real route/API fixtures, accessibility baseline, and housekeeping capture.
- Negative tests: unsupported model/theme, forbidden capability, locale route drift, unauthorized housekeeping deep link, CSRF failure, and private/draft leakage.
- Readiness: proposal-ready for synthetic presentation only; evidence-needed for production/CMS flows. Owner `visual`/`frontend`; reviewer `reviewer`.
- Acceptance: use only configured runner and synthetic fixtures; record exact viewport/method. Stop if no approved runner or capture baseline exists; do not claim visual regression coverage otherwise.

### F59 - Release candidate verification matrix

- Observable contract: a release candidate is accepted only when typed view-model, theme manifest, locale, asset provenance, browser, cache, audit, and golden-contract checks report explicit pass/blocked/UNKNOWN states.
- Authority: new website-owned release design constrained by F4/F7/F8 evidence and repository CI policy; not a production release approval.
- Proposed paths: `docs/evidence/F59-release-verification.md`, `frontend/tests/**` only after each prerequisite is approved, existing CI configuration only through a separate coordinator decision.
- Missing decisions: exact CI matrix, browser runner, asset/license scan, cache integration, CMS schema, production gates, and review sign-off policy.
- Negative tests: fail closed on missing artifact, stale provenance, unsupported capability, failed audit, cache invalidation error, red browser/golden check, or secret detection.
- Readiness: proposal-ready as a checklist; implementation/release enablement gated. Owner `coordinator`; reviewer `reviewer`.
- Acceptance: list base/head SHA, changed paths, test output, unresolved UNKNOWNs, and no production claims. Stop on unexplained red CI or missing required evidence.

### F60 - First-release presentation and CMS readiness gate

- Observable contract: the first-release decision packet distinguishes synthetic presentation contracts, source-backed public behavior, gated CMS design, and production enablement; no design label silently grants implementation authority.
- Authority: new website-owned governance document constrained by `DECISIONS.md:23-24,33-35`, `tasks/queue.md:23-30`, and `docs/ai-run-state.md:5-15`.
- Proposed paths: `docs/roadmap/F46-F60-candidate-design.md` (this document), later synthesis `docs/roadmap/F18-F60-readiness-summary.md`; no product paths.
- Missing decisions: owner approval of feature batch, F16/F17 integration, independent synthesis review, schema/security decisions, and exact first-release total-F range.
- Negative tests: reject implementation dispatch from a design-only document, duplicate F number, unreviewed path, unsupported asset/optional profile, and a proposal that labels gated work code-ready.
- Readiness: proposal-ready governance boundary; not a release approval. Owner `coordinator`; reviewer `reviewer`.
- Acceptance: synthesis must reconcile numbering against F18-F45, count distinct defensible units, preserve missing gates, and create no implementation cards until the owner accepts scope. Stop on unresolved numbering or absent independent review.

## Numbering and release conclusion

F46-F60 are fifteen distinct provisional design units, not fifteen authorized implementation units. F24, F29, and the broad unresolved F30 theme/CMS slot remain owned by the F18-F30 proposal; this lane narrows F47 to package validation and F54 to non-article composition models rather than rebranding those behaviors. The practical first-release candidate range cannot be finalized here because F18-F45 synthesis, F16/F17 delivery, CMS schema ownership, security review, browser captures, and publication/media decisions remain open. The defensible near-term boundary is the existing F0-F8/F14-F17 evidence foundation plus only separately approved synthetic presentation contracts; broad parity including housekeeping mutation, publication/rollback, safe uploads, optional modern assets, Atom, Pixel63, or SWF is uncertain and remains outside current authorization.

No slots are silently converted into implementation work. The synthesis coordinator must reconcile this file with F31-F45 and F18-F30, verify all cited hashes and source lines, preserve explicit gaps, run scope/secret/diff checks, and obtain independent review before any design-only delivery. No production CMS/admin capture, schema, credential, real-data, or runner material is included here.

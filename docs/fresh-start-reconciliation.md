# Fresh-start reconciliation

Status: approved read-only foundation; no Go spike or C++ changes.

## Authorities

- **Behavior and routes:** original `Quackster/PHPRetro`, captured by observation and disposable golden runs.
- **Security ideas only:** PHPRetro-PDO for CSRF, prepared statements, durable audit, and enrolled-secret TOTP. Its behavior, routes, schema adaptations, and C++ port are not golden references; the PDO and PolarIS changes broke features and the C++ port inherited those breaks.
- **Hotel storage:** PolarIS only. Holograph is dropped.
- **Pixel63:** separate identity, schema, currencies, permissions, credentials, and client protocol; no shared assumptions.

## Mapping rule

Map only fields proved by original source, `CleanDB.sql`, or a golden capture. Preserve `UNKNOWN` otherwise. For the first-release account/profile/session slices, `CleanDB.sql` proves these `users` columns: `id`, `username`, `password`, `mail`, `mail_verified`, `account_created`, `last_login`, `last_online`, `motto`, `look`, `gender`, `rank`, `credits`, `pixels`, `points`, `online`, `auth_ticket`, `ip_current`, `home_room`, `auth_ticket_expires_at`, `remember_token_hash`, `remember_token_expires_at`, and `access_token_version`. Their exact PHPRetro route semantics, write rules, and session lifecycle remain UNKNOWN until golden capture. `real_name`, `account_day_of_birth`, `ip_register`, `machine_id`, `secret_key`, `pincode`, `extra_rank`, background fields, and `last_username_change` are schema facts but not approved first-release mappings. For the one content-read slice, `CleanDB.sql` proves `hotelview_news` with `id`, `title`, `text`, `button_text`, `button_type`, `button_link`, and `image`; whether the original PHPRetro content route maps to this table remains UNKNOWN. Website-only records remain in explicitly owned `phpretro_*` tables. CleanDB.sql does not prove the first-release guestbook, durable audit, TOTP, or privacy schemas, so those mappings remain UNKNOWN. Never revive Holograph names such as `users_bans`, `groups_details`, or `groups_memberships`. Presence in CleanDB.sql does not prove ownership, route behavior, or safe use.

## First release

1. Public/account foundation: public pages, login, logout, sessions, guest behavior, and PolarIS user lookup.
2. Existing-user profile read using verified fields only.
3. One website-owned content read (news or FAQ) after behavior and schema verification.
4. One authorized website-owned write with durable audit in the same transaction and injected audit failure.
5. Staff enrollment and per-staff TOTP verification with missing, disabled, malformed, wrong, expired, wrong-user, and database-error failures.
6. Personal guestbook read with owner/friend privacy enforcement.

Homes editing, group Homes, purchases, placement, asset import, full client handoff, and broad parity remain deferred.

## Localization and housekeeping CMS

Localization is a first-class website contract. Housekeeping selects and manages supported locales, translation catalogs, fallback order, locale-specific content variants, and activation state. React themes consume typed localized view models; locale selection must not bypass authorization or alter route/security behavior. Cache keys must include the locale when the response varies by language.

Housekeeping uses the same React architecture with a dedicated housekeeping theme/style, not a separate unreviewed template runtime. It is the authenticated CMS and website-management surface: administrators can manage translations, new button pages, navigation/buttons, news, FAQs, banners, landing sections, presentation-only theme settings, safe media metadata, website status, maintenance messaging, cache invalidation, and audit history through separately tested capability slices. All writes require server-side authorization, CSRF, validation, prepared SQL, same-transaction audit, and safe publication/rollback semantics. Housekeeping may not silently write PolarIS-owned tables or execute uploaded code/assets.

## Theme contract

A theme is an immutable, versioned React package with a manifest declaring its API version, component entry points, assets, capabilities, and typed view-model compatibility. All supported themes use React; server-rendered Go templates are not the theme runtime. A theme may change presentation components, CSS, assets, typography, layout, and named variants. It may not access databases, identities, secrets, sessions, CSRF state, permissions, or audit mechanisms, alter route behavior, or use arbitrary filesystem, process, or network capabilities. Validate package paths, bundle capabilities, types, sizes, dependencies, and compatibility in CI and at install. Activate by configuration pointer, audit activation, and retain atomic rollback.

Redis is a required supporting service for approved cache and session-support workloads, while MariaDB remains the system of record. Each Redis-backed feature must document key namespaces, TTLs, serialization, invalidation, outage/fallback behavior, and whether Redis data is disposable cache or session-critical state. No feature may silently treat an unverified Redis value as authoritative.

## Atom findings

Atom CMS is MIT for its code and theme repositories, but its bundled Habbo-derived artwork has unclear provenance. Its themes are Blade templates inside a Laravel application, with no stable manifest, version range, or theme test suite. It uses Qirolab's Laravel theme loader, hard-coded build paths, `dev-main` dependencies, and no committed lockfile; housekeeping is unavailable or unlicensed. Direct compatibility is not promised. Any later support means an adapter for a restricted presentation subset.

## Licensing and assets

The project license decision is GPL-3.0 for code. The implementation is a clean reimplementation: do not copy original PHP code. Original artwork and themes may be kept in one clearly named repository folder, with one provenance file recording source, retrieval date, and hash for every asset. Credit original creators in `README`, state that the project is non-commercial, and state no Sulake affiliation. Asset provenance remains flagged for review but is not a work stop under this decision.

## Stage 2 handoff

Verified 2026-09-30 against `upstream/Polaris-Emulator/Database/Default Database/CleanDB.sql`. The first-release `users` account/profile/session columns and the complete `hotelview_news` row shape are schema-proven. PHPRetro route semantics, website-owned audit/TOTP/guestbook/privacy schemas, and any unlisted mapping remain UNKNOWN. The supplied modern-theme asset directory is deferred to the asset/provenance stage.

## Verification and stop rules

Near release, independent review means a fresh Claude Opus 5.5 review followed by a fresh Fable 5.1 review under the Phase 10 decision. The spike uses fresh-session reviews. No human review is required or available. Continue only with reproducible golden behavior, verified mappings, isolated PolarIS/Pixel63 boundaries, passing backend/browser/race/security tests, and review evidence. Stop for guessed schema, unavailable evidence or credentials, a security-boundary conflict, destructive production action, red/skipped/unavailable verification, five failed iterations for a unit, two materially similar failures without a changed hypothesis, or unverifiable spend/credentials. Never repeat unchanged tests or CI, bypass protections, expose secrets, or start paid work merely to keep a lane active.

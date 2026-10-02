# F7 React and Redis contract

## Scope and authority

This unit provides a package-managed React presentation boundary and an injected Redis-like support contract. Fixtures are synthetic. React themes receive typed view models only; they cannot select routes, database ownership, identity, authorization, CSRF, or audit behavior. MariaDB remains authoritative. No server-rendered theme templates, production data, credentials, live Redis, publishing, or handoff are included.

## Frontend

`frontend/package.json` pins React 19.1.1, TypeScript 5.9.2, and @types/react 19.1.10, with explicit GPL-3.0-only project licensing and Node >=26.7.0. `themeManifest.ts` accepts only `theme.v1`, the React StarterShell, `home.v1`, and the presentation capability. `viewModel.ts` rejects unsupported versions and malformed models. `StarterShell.tsx` is a minimal PHPRetro-compatible React shell using synthetic data.

## Cache contract

`internal/cache.RedisLike` is the only backend dependency: Get, Set, and Delete. `Store` validates namespaces and JSON serializes values. Read outage or expiry is a cache miss; Put and Invalidate outages return `ErrUnavailable` so callers cannot claim a write or invalidation succeeded. Namespaces are `phpretro:cache:read:` (default TTL 60s) and `phpretro:cache:support:` (default TTL 15s). Values are cache-only/support values; no authoritative account, profile, permission, session identity, or audit state is stored here. Invalidation explicitly deletes a namespaced key. Serialization is JSON; malformed JSON returns `ErrSerialization`. Namespace violations return `ErrNamespace`. Non-positive TTL returns `ErrExpired`. The deterministic `Memory` double uses an injected logical clock and a `Down` switch; no Redis server is required.

## Tests and unknowns

Synthetic TypeScript tests cover malformed manifests, capability expansion, unsupported view-model versions, and malformed models. Go tests cover expiry, JSON serialization errors, namespace violations, invalidation, outage-as-miss reads, and outage failures for writes/invalidation. Exact API schema and production Redis topology are intentionally unknown and were not guessed.

## Checks

- `node --version`: v26.7.0
- `npm --version`: 11.19.0
- `npm ci --include=dev --ignore-scripts`: passed; `npm run typecheck` passed; `npm test` passed with 3 tests.
- Docker image `golang:1.24` with `PATH=/usr/local/go/bin:$PATH`: `gofmt`, `go test ./...`, `go test -race ./...`, and `go vet ./...` passed for the F7 implementation. Repository CI remains pinned to `.go-version` Go 1.25.13.
- No commit or push performed.

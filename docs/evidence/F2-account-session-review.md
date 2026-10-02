# F2 account/session review packet

Base: `900b7207f01d7f5307b37fe693a4f9c416aafa50`; implementation branch scope was approved by PR #8.

The account boundary uses injected `Store` and `PasswordVerifier` interfaces. F1 now records the PolarIS emulator's BCrypt verifier and synthetic `$2y$` tests; concrete runtime row contents remain UNKNOWN and are not copied. Session state uses random 32-byte opaque tokens, SHA-256 server-side keys, expiry, logout deletion, and cookie attributes (`HttpOnly`, `SameSite=Lax`, optional `Secure`).

Tests cover synthetic successful/failed/store-error authentication, token rotation, logout, expiry, and cookie policy. The pinned `golang:1.24.6` image (`sha256:8d9e57c5a6f2bede16fe674c16149eee20db6907129e02c4ad91ce5a697a4012`) ran `gofmt`, `go test ./...`, and `go test -race ./...`; all passed. The host has no installed Go toolchain, so container output is the authoritative local test evidence.

No Luna delegation was used: verifier choice and session security are Sol-owned, and the bounded implementation was small enough that a second context would not repay itself. Jev was unavailable/escalated in F1 and no consequential Jev verdict was used. A6API per-unit token and cost export was not available in the local session; no savings claim is made.

Acceptance status: implementation tests pass and the verifier contract is now source-backed as BCrypt with `$2y$` support. Runtime row sampling and any upgrade policy remain separate evidence work. No production data, credentials, migrations, or deferred gates were touched.

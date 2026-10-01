# Initial supervised work-unit queue

These are the initial supervised units. Their caps are recorded in `DECISIONS.md`; Sol must still write the exact brief and status each unit before delegation.

| ID | Unit | Scope | Done when |
| --- | --- | --- | --- |
| F0 | Repository and CI baseline | `go.mod`, `.go-version`, `internal/foundation/`, `.github/workflows/`, `docs/`, `DECISIONS.md` | Pinned Go, dependency-free tests, race, `govulncheck`, module evidence artifact, license scan, and artifacts are reproducible. |
| F1 | Password-scheme evidence | `docs/`, fixture scripts only | PolarIS schema/rows and original source establish the verifier; unknowns remain explicit. |
| F2 | Account/session contract | named Go account/session packages and tests | Guest, failed, successful, logout, expiry, fixation, cookie, and failure contracts pass golden tests. |
| F3 | Profile read | profile service/handler/templates and tests | Only schema-proven fields render; unauthenticated and wrong-user cases are covered. |
| F4 | Golden harness | disposable fixtures, capture runner, hashes, CI | Route/method/status/redirect/cookie/body/hash comparisons are repeatable and classified. |
| F5 | Content read | one website-owned article/archive path | Source evidence, read contract, template output, and negative cases pass. |

Every unit brief must state base SHA, exact paths, evidence, tests, acceptance, stop conditions, and token cap. Any security, schema, production, or runner decision stays with Sol.

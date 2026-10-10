# F61 public profile HTTP evidence

Authority: unchanged `docs/roadmap/restart-contracts.md`, F61.
Public field authority: `docs/evidence/F3-profile-schema.md` and its pinned
Polaris source references. Only id, username, motto, look, gender and
account_created are exposed; the DTO retains accountCreated spelling,
profile.v1 version and normalized tab envelope.

Legacy source baseline: `internal/server/server.go` at brief base
836ea11409c03f574c777fd7733b9ad2d9a1dae7 used profileFixtures and ByID(1)
for the demo /api/profile route, profilePayload for the six public fields,
and profile.NewView for tab normalization (default/invalid tab is 1).
Existing server_test.go TestRoutes proves the DemoUser no-selection smoke
response. New() retains that explicit demo default and all other smoke routes.
The injected constructor does not default a missing selection.

NewWithProfileStore accepts the existing read-only profile.Store; no database
is opened. Exactly one id or username key is required. Duplicate keys,
ambiguous keys (including empty values), invalid query encoding and invalid
selectors return 400 before store access. IDs are positive decimal int64
values; usernames are trimmed, 1-32 ASCII letters/digits/underscore/hyphen.
A confirmed ErrNotFound returns 404. Other store errors, nil stores and
malformed identity/gender rows return generic 503 without diagnostic data.
The handler validates rows directly so a malformed identity is not confused
with a confirmed missing row by the existing Service validation.

Tests use a recording synthetic Store test double because exact boundary calls
and unavailable/error results must be observed without a database. Assertions
exercise the production constructor, routing, validation and JSON projection.
Two independent rows prove ID and trimmed-username selection and exact calls;
negative cases prove zero calls and exact generic error payloads.

fidelity: guessed. This is an approved new development HTTP contract;
capture fidelity is unverified, not legacy capture parity. No live requests,
real users, private fields, SQL, authentication or write changes are involved.

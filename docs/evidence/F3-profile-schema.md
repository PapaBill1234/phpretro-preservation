# F3 profile-read evidence

Status: source-backed scope evidence. No implementation or production data used.

## Authoritative sources

| Claim | Evidence | Result |
| --- | --- | --- |
| Profile identity and presentation columns exist | `upstream/Polaris-Emulator/Database/Default Database/CleanDB.sql:55189-55205` defines `id`, `username`, `real_name`, `motto`, `look`, `gender`, `account_created`, and related account fields. | Proven schema shape. |
| Lookup by numeric ID | `Emulator/src/main/java/com/eu/habbo/habbohotel/users/HabboManager.java:72-79` uses `SELECT * FROM users WHERE id = ? LIMIT 1`. | Proven source lookup; parameter is bound by the query helper. |
| Lookup by username | `HabboManager.java:82-89` uses `SELECT * FROM users WHERE username = ? LIMIT 1`. | Proven source lookup; parameter is bound by the query helper. |
| Mapping and normalization | `Emulator/src/main/java/com/eu/habbo/habbohotel/users/HabboInfo.java:79-117` maps id, username, motto, look, gender, account creation, home room, last online, and presentation background fields. Rank is resolved through the permissions manager. | Proven source mapping. |

## F3 boundary

The Go profile read may expose only `id`, `username`, `motto`, `look`, `gender`, and `account_created` in the first unit. Passwords, mail, IPs, machine identifiers, tokens, rank/authorization, currency, room state, and all writes are out of scope. `real_name` is schema-proven but not mapped by the cited `HabboInfo` constructor and remains UNKNOWN for the first contract.

## Checks

- Re-run the cited line inspections against the pinned local Polaris checkout.
- Verify the Go query uses a bound parameter, an explicit column list, and `LIMIT 1`.
- Use synthetic rows only for mapping tests; assert missing-row and malformed-gender behavior.
- Confirm `go test ./...` and `go test -race ./...` in the pinned container.

No full SQL row, credential, token, email, IP, or personal data is copied into this repository.

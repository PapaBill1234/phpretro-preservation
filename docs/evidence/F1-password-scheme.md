# F1 password-scheme evidence

Status: accepted evidence extraction. Synthetic data only; no full hash values are recorded.

## Evidence table

| Source/format | Observed shape | Verification operation | Status/confidence |
| --- | --- | --- | --- |
| PolarIS users.password | varchar(64) NOT NULL at upstream/Polaris-Emulator/Database/Default Database/CleanDB.sql:55189-55194 | Schema declares storage capacity only; the auth implementation below establishes the verifier used by the emulator. | Proven column shape; deployed rows still require runtime sampling (0.99 / 0.85 respectively). |
| PolarIS emulator BCrypt | `Emulator/pom.xml:660-666` documents favre BCrypt for auth endpoints and Laravel-style `$2y$` hashes; `PasswordHasher.java:10-23` hashes and verifies with BCrypt, failing closed on invalid input. | Source inspection of the pinned local Polaris checkout. | Proven verifier implementation; `$2y$` is the supported auth format (0.99). |
| Synthetic Laravel BCrypt | `PasswordHasherTest.java:18-25` converts a generated BCrypt value to `$2y$` and verifies correct/wrong passwords; `:27-32` verifies invalid hashes fail closed. | Existing synthetic unit tests; no production rows or full hashes copied. | Proven synthetic behavior (0.99). |
| Disposable Stage 3 users.password | The fixture table uses varchar(100); synthetic stage3admin row is 40 characters, lowercase hexadecimal, with no prefix. | Recomputed sha1("Stage3Pass!" + strtolower("stage3admin")) and compared only for equality; result matched. | Proven synthetic fixture behavior, not proof for all PolarIS rows (0.99). |
| Original PHPRetro helper at pinned commit 8ab8f81e6bcd09fc661547cb032ef045149c095 | includes/classes.php:38-40 defines HoloHash($password, $username) as sha1($password.strtolower($username)). account.php:41-45 applies it to submitted password and username before lookup. | git show at the pinned object and exact source search. | Proven for the pinned source (0.99). |
| Other hash formats | No additional user-password verifier was found in the inspected PolarIS auth source. The legacy PHPRetro SHA-1 format remains a separate compatibility input. | Exact source searches and the cited verifier tests. | Absence is limited to inspected inputs; other deployed rows/formats UNKNOWN. |

## Schema and row checks

The PolarIS DDL at lines 55189-55215 defines the users table, including password varchar(64) NOT NULL and username varchar(25) NOT NULL. The auth source uses favre BCrypt and tests Laravel-style `$2y$` verification. The disposable Stage 3 database is a different legacy fixture: DESCRIBE users reports name varchar(50) and password varchar(100). Its only inspected row is the synthetic stage3admin; the password is 40 lowercase hexadecimal characters. The full value is intentionally omitted.

The derived synthetic check was:

    SHA1(UTF-8("Stage3Pass!" + lowercase("stage3admin")))
    length = 40, lowercase-hex = true, database value matches = true

## Original source pin

The clean sibling checkout hotel-drogon-scope-guard/stage3-original-phpretro/ is at the requested commit 8ab8f81e6bcd09fc661547cb032ef045149c095 from https://github.com/Quackster/PHPRetro.git. git show at that object verifies both cited source paths and the SHA-1 construction. The working tree is clean. The local recovery checkout in this repository is a separate copy at another commit and is not the pin authority.

The checked-in source hash manifest remains a recovery manifest for the local copy; the pinned Git object and clean sibling checkout are the authority for the source-code claim.

## Recommendation

Use BCrypt verification for PolarIS-shaped rows, accepting the `$2y$` Laravel variant, and fail closed on malformed values. Keep the pinned PHPRetro SHA-1 construction only as a separately marked compatibility reader for legacy imports; do not write new SHA-1 values. Runtime row sampling remains UNKNOWN and must be checked with synthetic fixtures or an owner-approved disposable export before any migration or upgrade behavior is designed.

## Reproducibility

- Numbered source inspection verified the PolarIS DDL citation.
- DESCRIBE users and a synthetic-only SELECT classified the disposable schema and row shape; the full value was not copied.
- PowerShell SHA-1 recomputation verified synthetic equality without recording the hash.
- `pom.xml`, `PasswordHasher.java`, and `PasswordHasherTest.java` were inspected at the cited lines; the synthetic tests cover BCrypt generation, `$2y$` verification, wrong-password rejection, and malformed-hash rejection.
- git -C hotel-drogon-scope-guard/stage3-original-phpretro rev-parse HEAD returned the requested pin, and git show verified both source citations.
- The Jev helper returned escalate because its OpenRouter backend rejected typesafe/jev-latest as unavailable. No Jev selection was used; Sol verified the evidence directly. The initial default-path invocation was a tooling-resolution failure and was not retried unchanged.

No implementation files, production data, real user data, or credentials were used or changed.

# F1 password-scheme evidence

Status: accepted evidence extraction. Synthetic data only; no full hash values are recorded.

## Evidence table

| Source/format | Observed shape | Verification operation | Status/confidence |
| --- | --- | --- | --- |
| PolarIS users.password | varchar(64) NOT NULL at upstream/Polaris-Emulator/Database/Default Database/CleanDB.sql:55189-55194 | Schema declares storage capacity only; it does not prove a hash algorithm or current row format. | Proven column shape; hash format UNKNOWN (0.99 / 0.05 respectively). |
| Disposable Stage 3 users.password | The fixture table uses varchar(100); synthetic stage3admin row is 40 characters, lowercase hexadecimal, with no prefix. | Recomputed sha1("Stage3Pass!" + strtolower("stage3admin")) and compared only for equality; result matched. | Proven synthetic fixture behavior, not proof for all PolarIS rows (0.99). |
| Original PHPRetro helper at pinned commit 8ab8f81e6bcd09fc661547cb032ef045149c095 | includes/classes.php:38-40 defines HoloHash($password, $username) as sha1($password.strtolower($username)). account.php:41-45 applies it to submitted password and username before lookup. | git show at the pinned object and exact source search. | Proven for the pinned source (0.99). |
| Other hash formats | No additional formats were found in the inspected original login path or synthetic row. | Exact searches for HoloHash, sha1, md5, crypt, and password verification; database classification by length/characters. | Absence is limited to inspected inputs; other rows/formats UNKNOWN. |

## Schema and row checks

The PolarIS DDL at lines 55189-55215 defines the users table, including password varchar(64) NOT NULL and username varchar(25) NOT NULL. The disposable Stage 3 database is a different legacy fixture: DESCRIBE users reports name varchar(50) and password varchar(100). Its only inspected row is the synthetic stage3admin; the password is 40 lowercase hexadecimal characters. The full value is intentionally omitted.

The derived synthetic check was:

    SHA1(UTF-8("Stage3Pass!" + lowercase("stage3admin")))
    length = 40, lowercase-hex = true, database value matches = true

## Original source pin

The clean sibling checkout hotel-drogon-scope-guard/stage3-original-phpretro/ is at the requested commit 8ab8f81e6bcd09fc661547cb032ef045149c095 from https://github.com/Quackster/PHPRetro.git. git show at that object verifies both cited source paths and the SHA-1 construction. The working tree is clean. The local recovery checkout in this repository is a separate copy at another commit and is not the pin authority.

The checked-in source hash manifest remains a recovery manifest for the local copy; the pinned Git object and clean sibling checkout are the authority for the source-code claim.

## Recommendation

For the verified legacy fixture and pinned original source, a Go verifier can reproduce the exact SHA-1 construction only as a compatibility reader, with constant-time comparison and no new SHA-1 writes. Do not select the production PolarIS verifier from the column width or legacy fixture alone. PolarIS row-format evidence is still required before F2 chooses its verifier. If PolarIS rows are confirmed to use this legacy format, support a measured one-time upgrade on successful login to a modern password hash, preserving an explicit legacy/modern format marker and tests for both.

## Reproducibility

- Numbered source inspection verified the PolarIS DDL citation.
- DESCRIBE users and a synthetic-only SELECT classified the disposable schema and row shape; the full value was not copied.
- PowerShell SHA-1 recomputation verified synthetic equality without recording the hash.
- git -C hotel-drogon-scope-guard/stage3-original-phpretro rev-parse HEAD returned the requested pin, and git show verified both source citations.
- The Jev helper returned escalate because its OpenRouter backend rejected typesafe/jev-latest as unavailable. No Jev selection was used; Sol verified the evidence directly. The initial default-path invocation was a tooling-resolution failure and was not retried unchanged.

No implementation files, production data, real user data, or credentials were used or changed.

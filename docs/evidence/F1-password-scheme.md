# F1 password-scheme evidence

Status: complete evidence extraction with one explicit source-pin UNKNOWN. Synthetic data only; no full hash values are recorded.

## Evidence table

| Source/format | Observed shape | Verification operation | Status/confidence |
| --- | --- | --- | --- |
| PolarIS users.password | varchar(64) NOT NULL at upstream/Polaris-Emulator/Database/Default Database/CleanDB.sql:55189-55194 | Schema declares storage capacity only; it does not prove a hash algorithm or current row format. | Proven column shape; hash format UNKNOWN (0.99 / 0.05 respectively). |
| Disposable Stage 3 users.password | The fixture table uses varchar(100); synthetic stage3admin row is 40 characters, lowercase hexadecimal, with no prefix. | Recomputed sha1("Stage3Pass!" + strtolower("stage3admin")) and compared only for equality; result matched. | Proven synthetic fixture behavior, not proof for all PolarIS rows (0.99). |
| Original PHPRetro helper in the available checkout | includes/classes.php:38-40 defines HoloHash($password, $username) as sha1($password.strtolower($username)). account.php:41-45 applies it to submitted password and username before lookup. | Exact source search and line inspection. | Strong evidence for this checkout (0.99), but pinned-commit identity UNKNOWN. |
| Other hash formats | No additional formats were found in the inspected original login path or synthetic row. | Exact searches for HoloHash, sha1, md5, crypt, and password verification were run against the inspected source; database classification was length/character based. | Absence is limited to inspected inputs; other rows/formats UNKNOWN. |

## Schema and row checks

The PolarIS DDL at lines 55189-55215 defines the users table, including password varchar(64) NOT NULL, username varchar(25) NOT NULL, and the surrounding account fields. The disposable Stage 3 database is a different legacy fixture: DESCRIBE users reports name varchar(50) and password varchar(100). Its only inspected row is the synthetic stage3admin; the password is 40 lowercase hexadecimal characters. The full value is intentionally omitted from this document.

The derived synthetic check was:

    SHA1(UTF-8("Stage3Pass!" + lowercase("stage3admin")))
    length = 40, lowercase-hex = true, database value matches = true

## Original source pin

The available stage3-original-phpretro/ checkout is at commit db46513d20f8434c7979c2be0e5ef1ca9af8650e, not the plan’s requested 8ab8f81e6bcd09fc661547cb032ef045149c095. The requested object is absent from the checkout and the configured remotes did not resolve it. Therefore the claim that the inspected helper is exactly the pinned upstream commit remains UNKNOWN. The source lines are retained as supporting evidence only and require clean pinned-checkout verification before implementation.

The checked-in source hash manifest is docs/stage3-original-phpretro-sha256.csv; its current file SHA-256 is AA72CA4D73794DF6D17E704D532C8EFB6330BFBFDB727AD85EC748B28DC75081.

## Recommendation

For the verified legacy fixture, a Go verifier can reproduce the exact SHA-1 construction only as a compatibility reader, with constant-time comparison and no new SHA-1 writes. Do not select the production PolarIS verifier from the column width or from the legacy fixture alone. First obtain the exact pinned original source and inspect synthetic PolarIS-shaped rows. If PolarIS rows are confirmed to use this legacy format, support a measured one-time upgrade on successful login to a modern password hash, preserving an explicit legacy/modern format marker and tests for both. Until then, the PolarIS algorithm and upgrade path are UNKNOWN.

## Reproducibility

- Get-Content with numbered lines verified the PolarIS DDL citation.
- DESCRIBE users and a synthetic-only SELECT name,password FROM users classified the disposable schema and row shape; the full value was not copied.
- PowerShell SHA-1 recomputation verified the synthetic equality without recording the hash.
- Source search verified HoloHash and its call site at the cited lines.
- git cat-file -t 8ab8f81e6bcd09fc661547cb032ef045149c095 failed because the requested object is unavailable locally; this is recorded as UNKNOWN rather than guessed.
- The Jev helper was invoked once with the installed CLI and returned `escalate` because its OpenRouter backend rejected `typesafe/jev-latest` as unavailable. No Jev selection was used; Sol verified the evidence directly. The initial default-path invocation was a tooling-resolution failure and was not retried unchanged.

No implementation files, production data, real user data, or credentials were used or changed.

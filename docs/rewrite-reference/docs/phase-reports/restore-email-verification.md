# Restore email verification

## Summary

- Registration creates a 32-byte random token, stores only its SHA-256 hash, expires it after 24 hours, and emails the raw link.
- email.php verifies the hash, requires an unused unexpired token, atomically stamps used_at, and sets users.mail_verified to 1.
- Added phpretro_email_verification_tokens to migrations/001_custom_tables.sql.

## Files changed

- register.php
- email.php
- migrations/001_custom_tables.sql
- references/Custom-Schema-Additions.md
- docs/phase-reports/restore-email-verification.md

## Schema verification

Custom table and columns were verified from the supplied current Custom-Schema-Additions.md section 4. Polaris users columns were verified in CleanDB.sql: id, mail, and mail_verified.

## Assumptions and flags

- The email verification reward remains unavailable until the separate transaction-history feature restores its ledger.
- Tokens expire in 24 hours; prior unused tokens for the user are removed when a new token is issued.

## PHP lint

Not run: the GitHub-only environment has no php executable. Run php -l register.php and php -l email.php before merge.
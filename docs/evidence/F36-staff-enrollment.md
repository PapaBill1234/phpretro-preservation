# F36 synthetic staff enrollment evidence

Source fixture: `docs/roadmap/F31-F45-candidate-design.md`, F36 candidate row (line 54). It defines synthetic-only enrollment, identity binding, secret non-disclosure, disabled/unauthorized denial, duplicate and DB-failure negative cases, and atomic audit as the proposed contract. The same row says the owner/security/schema gate is open and staff identity, secret protection/recovery, and audit schema are UNKNOWN.

No legacy staff schema, production behavior, credentials, or real staff records are evidenced. All concrete identity, authorization-flag, validation, in-memory persistence, and audit field choices here are guessed test fixtures. The implementation does not enable production use.

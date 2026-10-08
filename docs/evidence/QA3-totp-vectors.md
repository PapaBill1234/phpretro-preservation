# QA3 fixed TOTP vectors

Acceptance authority: RFC 4226 Appendix D (SHA1 HOTP, six digits) and RFC 6238
Appendix B (SHA1 TOTP, 30-second period, eight digits). The public example key
is ASCII `12345678901234567890`, not a credential. The configured six-digit
TOTP values are the last six digits of Appendix B's eight-digit values.

| UTC Unix time | Published eight-digit value | Six-digit expected |
| --- | --- | --- |
| 59 | 94287082 | 287082 |
| 1111111109 | 07081804 | 081804 |
| 1111111111 | 14050471 | 050471 |
| 1234567890 | 89005924 | 005924 |
| 2000000000 | 69279037 | 279037 |
| 20000000000 | 65353130 | 353130 |

RFC 4226 counters 0, 1, 2, 3 are 755224, 287082, 359152, 969429.
At time 59 (counter 1), the coordinator keeps the existing synthetic zero-skew
policy: previous and next step codes are rejected as ErrExpiredCode and
counter 3 is ErrWrongCode. Alice uses the public RFC key, Bob a distinct
obvious ASCII development fixture; Alice's fixed code must be denied for Bob.
Missing/mismatched identities, disabled staff, malformed codes and unavailable
stores fail closed. No expected validation code comes from SyntheticCode.

This verifies the configured algorithm and validation boundary. It does not
verify session binding, authorization escalation, enrollment, replay durability
or original-site capture behavior. Timing policy remains fidelity: guessed.

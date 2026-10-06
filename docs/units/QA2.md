QA2 library-backed TOTP validation

fidelity: guessed

What works:
- TOTP computation and validation use github.com/pquerna/otp (HMAC-SHA1,
  six digits, 30-second period); validation accepts only the current step.
- Adjacent-step codes are explicitly rejected and classified as expired.
- Missing, disabled, malformed, wrong-user, wrong-code, and store-error cases
  fail closed.
- Deterministic RFC 6238 Appendix B vector and synthetic timing tests cover
  library parameters and boundary behavior.

What is guessed:
- The 30-second period and zero-skew policy are synthetic, unsupported by
  retained site evidence, and not owner-approved.
- RFC 6238 Appendix B is an external standards vector, not site evidence.

Run:
- go test ./internal/staff/... ./tests/staff/...
- bash scripts/check.sh

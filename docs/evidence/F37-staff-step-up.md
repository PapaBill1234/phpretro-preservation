# F37 staff step-up evidence

Source: docs/roadmap/F31-F45-candidate-design.md, F37 candidate row.

The source explicitly requires library-backed synthetic TOTP validation,
per-staff binding, negative cases, and fail-closed store errors. It also says
step-up scope, skew, rate limits, and failure response are UNKNOWN and requires
independent security review. This unit therefore records synthetic evidence
only; it does not claim production schema, capture parity, audit persistence,
replay protection, or HTTP/session integration.

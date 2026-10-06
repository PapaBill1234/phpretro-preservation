F37 evidence record

Source: docs/roadmap/F31-F45-candidate-design.md, F37 row.
It requires library-backed per-staff TOTP, session binding, explicit negative
cases, and approval of skew, rate limits, and failure response.

No retained staff capture or coordinator approval is present. Tests use
synthetic RFC 6238 secrets; guessed policy is recorded in docs/units/F37.md.

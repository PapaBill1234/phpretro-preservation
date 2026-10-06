fidelity: guessed

ValidateCode rejects enabled records whose StaffID is empty or differs from the
requested staff identity, before checking the secret or accepting a code. Disabled
records retain the existing ErrDisabled result. Matching enabled identities
continue using the synthetic RFC 6238 behavior.

No capture or fixture was supplied; the identity check is based on the unit
brief's security invariant. Test expectations are synthetic.

Run: go test ./internal/staff/... ./tests/staff/...
Gate: bash scripts/check.sh

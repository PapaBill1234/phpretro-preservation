# RF2a: Staff TOTP test audit

- Corrected the per-staff isolation assertion: Alice's generated code must not
  validate against Bob's distinct synthetic secret.
- Existing package declaration (`staff_test`) and filename (`totp_test.go`)
  match the external-test layout implied by `tests/staff` and its `staff` API
  import; no path or naming change is needed.
- No fixture or capture was supplied. Synthetic expectations are guessed;
  `fidelity: guessed`.
- No application behavior changed.
- Run with `go test ./...` and `bash scripts/check.sh`.

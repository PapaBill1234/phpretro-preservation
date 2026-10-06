RF1 consistency pass

What works:
- The listed packages retain their existing public boundaries and behavior.
- Cache, content, localization, PolarIS, profile, session, and staff code remain
  separated by domain with package-local errors and contracts.
- Existing tests pass without fixture changes.

Open audit findings:
- No concrete audit finding or fixture was supplied beyond “structure-only
  consistency pass”; no behavior-affecting refactor was justified.
- Package layout and naming were reviewed within the permitted paths and are
  consistent with the existing domain-package convention.

fidelity: guessed
coverage-exempt: no new behavior or tests were added because the brief supplied
no evidence-backed finding to exercise; existing package tests remain the
regression coverage.

Run:
- go test ./...
- bash scripts/check.sh

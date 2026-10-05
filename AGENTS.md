# PHP-Retro preservation

Goal: reimplement the public PHP-Retro site as a Go backend plus a React
frontend, from disposable captures and synthetic fixtures only. Development
project: no production environment, no real user data, no payments.

## Layout

- `cmd/phpretro` - HTTP entrypoint.
- `internal/<domain>` - one Go package per feature (profile, home, account,
  session, community, authflow, cache, localization, polaris, server).
- `frontend/src` - React views and typed view models; `frontend/tests`.
- `tests/golden` - capture comparison; `docs/evidence` - evidence records.
- `docs/units/Fxx.md` - one short delivery note per unit.
- `units.yaml` - the pipeline roadmap. `ops/` - orchestrator, skills, systemd
  units; not builder-owned.

## Gate

Run `scripts/check.sh`. It runs gofmt, `go build`, `go vet`, staticcheck,
`go test ./...`, `go test -race ./...`, gosec and govulncheck, and exits
non-zero on any failure. It is the only merge gate. Run it before finishing
and fix everything it reports.

## Closed list (never do these)

- Commit secrets, keys or credentials; this repository is public.
- Force-push, or push directly to `main`.
- Contact live outside systems or the original site.
- Use real user data.
- Edit AGENTS.md, skills, CI or `ops/` from a builder.

Never ask questions. Choose the safest reasonable option and record it in the
unit doc.

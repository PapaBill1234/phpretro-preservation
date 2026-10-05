# phpretro-preservation
Non-commercial preservation and hobby replacement for original PHPRetro

See [CHANGELOG.md](CHANGELOG.md) for the current implementation and operations history.

## Planning and operations

- [Fresh-start rewrite plan](docs/fresh-start-rewrite-plan-draft.md)
- [Workflow readiness and delegation](docs/workflow-readiness-and-delegation-draft.md)
- [Jev, cost, and agent operations](docs/jev-cost-and-agent-operations.md)
- [Readiness checklist](docs/rewrite-readiness.md)
- [Readiness evidence](docs/readiness-evidence.md)
- [Current Kanban work queue](tasks/queue.md)
- [Current AI run state and five-agent operating model](docs/ai-run-state.md)

Implementation is supervised through the Hermes Kanban board `phpretro-preservation`. The live profiles are `coordinator`, `backend`, `frontend`, `reviewer`, and `visual`; Hermes Nerve supervises active worker runs and Jev remains evidence-backed and policy-gated.

## How to run this

The development server requires the Go toolchain declared by `go.mod` (Go 1.24.0, with toolchain Go 1.24.6). From the repository root, start it with:

```sh
go run ./cmd/phpretro
```

The server listens on port `8080` by default. Set `PORT` to a value from `1` through `65535` to use a different port, for example `PORT=8081 go run ./cmd/phpretro`. To build the frontend bundle, run `npm run build` from the `frontend/` directory.

# Windows state at freeze

Recorded during the migration to the Ubuntu server on 2026-10-05. This
describes the machine being left behind. Nothing here was deleted.

## Freeze actions taken

| Action | Detail |
| --- | --- |
| Kanban dispatcher | Stopped. The gateway was stopped, which halts both the card dispatcher and the cron ticker. |
| Cron job `8b19b2ddfa63` (PHPRetro Kanban watchdog and feeder) | **Paused**, not deleted. |
| Cron job `3f676874aeb7` (PHPRetro economics digest, 6h) | **Paused**, not deleted (was already paused). |
| Gateway service | Stopped (`hermes gateway stop`). Restart with `hermes gateway start` or `schtasks /Run /TN Hermes_Gateway_930c1a5c`. |

Re-enable later with `hermes cron resume <id>` and `hermes gateway start`.

## Git state

- Repository: `C:/Users/Karim/Documents/ChatGPT/New project/phpretro-preservation`
- `main` at freeze: `6fc6e0d1a769b7f11025c3821f4b1971304febc7` (PR #54, the runnable development server)
- Working tree: **clean** (no uncommitted or untracked files)
- Local branches: 149 — all pushed to `origin`
- Remote branches: 159
- Registered worktrees: 150

### Uncommitted work resolved during the freeze

The working tree held the complete runnable-server implementation, untracked:

- `cmd/phpretro/main.go`
- `internal/server/fixtures.go`, `internal/server/server.go`, `internal/server/server_test.go`
- `frontend/index.html`, `frontend/src/main.tsx`, `frontend/vite.config.ts`
- modified `frontend/package.json` (adds `react-dom` and a bundler), `frontend/package-lock.json`, `README.md`

All of it was committed as `6fc6e0d` and delivered through PR #54, which is
merged. Verified before committing: `go build ./...` clean, `go test ./...` all
packages pass, and the server answers live on port 8099 (`/healthz`, `/`,
`/home`, `/account`, `/community`, `/articles`, 404 for unknown paths).

## Open pull requests

| PR | Branch | State |
| --- | --- | --- |
| #41 | `wt/policy-sweep` | Open, documentation-only supersession of stale policy wording. Parked; not a blocker for the migration. |

## Kanban board

Board: `phpretro-preservation`. Frozen at **192 done, 1 running, 4 todo, 1 ready, 0 blocked**.

In-flight when the gateway was stopped:

- `t_d224622f` — running, `backend`, "Correct PR41 current-main policy control and reconciliation"
- `t_f406ef0b` — completed during the freeze; its work is the server implementation committed above

Queued but not started:

- `t_502af887` — "Make the project runnable: entry point, HTTP server, mounted frontend" (superseded by the merged PR #54)
- `t_eaa85ee9` — "Add the Go executable entry point" (superseded by the merged PR #54)
- `t_8f738579`, `t_2446e418`, `t_19937f80` — the PR #41 review/approval/delivery chain

The board is exported read-only to `handoff/kanban-export/` and is **not**
revived on the server.

## Known defects on Windows at freeze

- **Broken worktrees.** Several cards were pointed at worktree paths that no longer existed as registered git worktrees (for example `.worktrees/wt-f23-backend` was an empty directory). Workers `cd`-ing into them found nothing, which is what produced the "blocked" cards that appeared despite unrestricted permissions. The failure was a stale/invalid workspace path, not a permission.
- **Stale bases.** Cards created before a merge kept an old base SHA, so packages merged afterwards were absent from their worktree and the card stopped on its own ancestry check.
- **Shell scripts under `plugins/nerve`** were patched during this session; see the migration report.

## Secrets

No secrets are recorded in this document. The Hermes `.env` files hold provider
credentials and are copied to the server separately over `scp` with mode `600`.

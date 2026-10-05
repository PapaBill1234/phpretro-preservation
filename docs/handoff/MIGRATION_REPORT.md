# Migration report: Windows → Ubuntu server

Executed 2026-10-05. Target: `ssh phpretro` (`ubuntu@ip-172-31-17-236`, Ubuntu
24.04.5 LTS). No passwords were used or stored; authentication is the
pre-configured key. No secrets are recorded in this document or committed to the
public repository.

## Summary

The repository, its local-only capture evidence, and the Hermes agent profiles
are on the server and verified. Go build, vet and the full test suite pass
there, and both required models answer a live smoke test. The old Kanban board
is **not** running on the server and cannot start on its own.

## 0. Server inspection (what was already there)

| Item | State found | Action |
| --- | --- | --- |
| OS | Ubuntu 24.04.5 LTS, user `ubuntu`, host `ip-172-31-17-236` | — |
| `git` | 2.43.0 | already correct |
| `gh` | 2.45.0 | already correct, already authenticated |
| `jq` | 1.7 | already correct |
| `tmux` | present | already correct |
| `build-essential` | gcc 13.3.0, GNU Make 4.3 | already correct |
| `go` | 1.24.6 at `/usr/local/go` | already correct — matches `go.mod` (`go 1.24.0`, `toolchain go1.24.6`) |
| `node` / `npm` | v26.10.0 / 11.19.1 | already correct |
| `docker`, `ufw`, `rsync`, `curl` | present | already correct |
| Repository | already cloned at `~/phpretro-preservation`, stale at `8ecbbfc` | fast-forwarded to `main` |
| Hermes | `~/.hermes` with all 7 profiles and `.env` files at mode 600 | inspected, updated |
| Capture evidence | `stage3-original-phpretro/` already present | verified byte-identical, left alone |

Nothing was overwritten without a backup. Every file changed on the server has a
`.bak-pre-migration-<timestamp>` or `.bak-pre-linux-path-<timestamp>` sibling.

## 1. Windows freeze

- Gateway stopped (halts both the card dispatcher and the cron ticker).
- Cron `8b19b2ddfa63` (watchdog/feeder) and `3f676874aeb7` (economics digest) **paused, not deleted**.
- In-flight cards allowed to finish; the two running cards either completed or were superseded.
- Recorded in `docs/handoff/WINDOWS_STATE.md`.

### Uncommitted work rescued

The working tree held the complete runnable-server implementation, untracked.
It was committed as `6fc6e0d` and delivered through PR #54 (merged). Verified
before committing: `go build ./...` clean, `go test ./...` all packages pass, and
the server answers live on port 8099.

All 149 local branches were pushed; nothing is left unpushed.

## 2. Kanban export

`handoff/kanban-export/` — read-only JSON archive, not revived on the server:

- `tasks.json` 270 · `task_comments.json` 208 · `task_runs.json` 306 · `task_links.json` 225 · `task_attachments.json` 4 · `task_events.json` 4774
- `README.md` index
- Scanned for key-shaped strings before committing: clean.

Delivered via PR #55 (merged).

## 3. Server preparation

- All required packages were already installed; nothing needed `apt`.
- Go 1.24.6 already matches the toolchain declared in `go.mod`.
- **`ufw` was inactive → now active.** Rules: allow `22/tcp` and `3389/tcp`
  (xrdp), default deny incoming, allow outgoing. SSH was confirmed still
  reachable immediately after enabling. 3389 was re-allowed on request after
  the initial "allow 22 only" pass; the xrdp listener is confirmed up on
  `*:3389`.
- **Hermes updated.** It was on a canary commit; `main` is the only published
  channel (`stable` is not published — `releases/channels/stable.json` does not
  exist). Updated forward on `main`: `v0.21.5+6980.g8d5e3e4.dirty` →
  **`v0.21.5+7252.g8030911.dirty` (main @ 80309111b4)**, with a backup.

### Defect found and fixed: Windows PATH baked into the server's Hermes

`hermes update` failed with `Could not resolve the main source channel: [Errno 2]
No such file or directory: 'git'`. The cause was not git: six of the seven
server `.env` files carried a `PATH=` line copied verbatim from the Windows
machine (`C:\Program Files\GitHub CLI;...`) with **no `/usr/bin`**, so `git` at
`/usr/bin/git` was unreachable to every subprocess Hermes spawned. Rewriting
those PATH lines to the server's own Linux tool directories fixed it, and the
update then resolved and completed.

This is the single most important finding of the migration: the same class of
stale-PATH defect had already caused a full session of worker failures on
Windows. Backups: `.env.bak-pre-linux-path-<timestamp>`.

## 4. Repository and hash manifests

- Server checkout fast-forwarded to `main` (211 tracked files, clean tree).
- `stage3-original-phpretro/` (local-only capture evidence, gitignored) was
  **already present** and byte-identical; no rsync was needed.
- Manifests generated on both sides and compared:

| Set | Files | Result |
| --- | --- | --- |
| Tracked files (git blob hashes) | 211 | **IDENTICAL** |
| Capture evidence (`stage3-original-phpretro/`, sha256) | 1383 | **IDENTICAL** |

Spot-check: `stage3-original-phpretro/account.php` hashes to
`4b9c7bb504fb35d138fc08da7e32f7cfc0fa1008dcc111b1865228aaa461567`, the exact
SHA-256 cited in the project roadmap — the evidence is authentic.

The evidence tree carries CRLF endings on both sides, and the two sides are
byte-identical. LF endings are used for repository files (git normalises them);
no line-ending conversion was applied to the evidence tree, because converting
it would have broken the byte-for-byte match the manifests are there to prove.

### Deliberately not copied

- `monitoring/` — 220 MB of local A6API request/response backups. These are
  operational telemetry, not project capture evidence, and the repository
  gitignores them specifically because they may contain request metadata.
- `frontend/node_modules/`, `frontend/dist/`, `__pycache__/` — regenerable.
- `.worktrees/` — 150 worktrees, regenerable, and the board is not being revived.

## 5. Hermes profiles

Already present and mostly already correct; compared by hash before touching.

**Already identical, skipped:** `memories/USER.md` in all six profiles,
`memories/MEMORY.md`, and every `SOUL.md` (top level plus all six profiles).

**Changed:** the approval-policy keys differed from the Windows configuration.
They were applied and then, on explicit instruction, **reverted** — the server
keeps its own safe defaults:

| Key | Server value |
| --- | --- |
| `approvals.mode` | `smart` |
| `approvals.single_query_mode` | `deny` |
| `approvals.cron_mode` | `deny` |
| `approvals.unattended_mode` | `deny` |
| `security.protected_instruction_files` | `true` |

`kanban.review_dispatch` is `false` and `providers.a6api.default_model` is
`gpt-6-luna` on both sides.

`.env` files: all seven present on the server at mode `600`. Key values were
never printed, read into this report, or committed.

### Windows path rewrite

- Six `.env` PATH lines rewritten to Linux directories (see the defect above).
- `grep` for `C:\Users\Karim` across `~/.hermes` (excluding the `hermes-agent`
  checkout and backups): **clean**. No Windows paths remain in any profile
  `config.yaml` or in the top-level `config.yaml`.

### Skills that depend on PowerShell or Windows-only tools

**None.** Every skill either declares `linux` in `platforms` or is one of four
macOS-only Apple skills (`apple-notes`, `apple-reminders`, `findmy`, `imessage`)
— which are macOS-specific, not Windows-specific, and were left in place.
`media/youtube-content` and `software-development/python-debugpy` mention
PowerShell only as a one-line Windows aside (`. .\activate.ps1`); both are
portable. `autonomous-ai-agents/computer-use` declares
`platforms: [macos, windows, linux]`.

Nothing was removed.

## 6. Verification on the server

```
go version            go1.24.6 linux/amd64   (matches go.mod: go 1.24.0 / toolchain go1.24.6)
go build ./...        exit 0
go vet ./...          exit 0
go test ./...         all 15 packages ok
```

Live model smoke tests, one line each:

```
hermes -z "Reply with exactly: SMOKE-OK-LUNA"     --model gpt-6-luna           -> SMOKE-OK-LUNA
hermes -z "Reply with exactly: SMOKE-OK-DEEPSEEK" --model deepseek-v4.1-flash  -> SMOKE-OK-DEEPSEEK
```

No other agents were started on the server.

## 7. GitHub CLI

`gh` **is** authenticated on the server (account `PapaBill1234`, token scopes
`gist`, `read:org`, `repo`, `workflow`) and can read the repository. The
skip-push fallback therefore does not apply and there is no command for the
owner to run.

## 8. The Kanban board is not running on the server

- Gateway: **stopped**.
- Both server cron jobs (`8b19b2ddfa63`, `3f676874aeb7`) **paused** — the
  watchdog/feeder was active when found and would otherwise have resumed
  dispatching cards.
- No gateway systemd unit exists, so nothing can restart it on boot.
- No `hermes` or `kanban` process is running.
- The board *data* is present at `~/.hermes/kanban` (a copy). It is inert with
  the gateway down and both jobs paused. The read-only archive in
  `handoff/kanban-export/` is the reference copy.

## Decisions taken without asking, and why

1. **Updated forward on `main` rather than pinning to the `v2026.9.24` tag.**
   No `stable` channel is published, and the install was already 6980 commits
   *past* that tag. Moving back would have been a downgrade of a working
   install, not an update.
2. **Did not copy `monitoring/`.** 220 MB of local request telemetry, not
   project evidence, and gitignored for metadata reasons.
3. **Did not convert the evidence tree to LF.** Doing so would have broken the
   byte-for-byte manifest match; the two sides are identical as they stand.
4. **Paused rather than deleted** every cron job and the board state on both
   machines.
5. **Reverted the approval-policy keys** to the server's safe defaults on
   explicit instruction, rather than porting the Windows values.

## What remains / known limitations

- **The Windows machine is untouched and still holds the frozen state.** The
  gateway there is stopped and both cron jobs are paused. Restart with
  `hermes gateway start` and `hermes cron resume <id>` if it is ever needed.
- **PR #41** (`wt/policy-sweep`) is still open on GitHub — documentation-only
  policy supersession, parked, not a migration blocker.
- **Hermes reports `.dirty` on both installs** because of pre-existing local
  modifications to `agent/auxiliary_client.py` (Windows) and one file on the
  server. These predate the migration and were not touched.
- **`ufw` rules are 22 and 3389.** The initial pass was "allow 22 only", which
  took RDP down; 3389 was re-allowed on request and the xrdp listener is up on
  `*:3389`. Any further port (for example a public HTTP port for the dev server)
  needs its own `sudo ufw allow <port>/tcp`.
- **The server's Hermes approval policy is the safe default**, not the Windows
  fast-mode policy. Starting agents there will hit approval prompts and the
  protected-instruction-file gate.

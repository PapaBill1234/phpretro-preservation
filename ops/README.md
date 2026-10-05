# ops/ - the autonomous unit pipeline

Decisions are made by `ops/orchestrator.py` (a script, zero tokens). Agents
only write, review or plan code. Tests are the gate; a merge queue replaces
SHA-bound approvals.

## What runs

| Piece | What it does |
| --- | --- |
| `ops/orchestrator.py` | One dispatch/verify/merge cycle. systemd timer, every 2 min, `flock`ed. |
| `scripts/check.sh` | The only gate: gofmt, go build, go vet, staticcheck, go test, go test -race, gosec, govulncheck. |
| `units.yaml` | The roadmap: one entry per unit (`id`, `title`, `status`, `depends_on`, `paths`, `tests`, `acceptance`, `fixtures`, `fidelity_notes`, `attempts`). |
| `ops/skills/{builder,reviewer,planner}/` | The three agent roles. Loaded with `-s`. |
| `ops/hooks/pre-push` | Safety outside the model: rejects pushes to `main`/`integration` and any force push. Activated with `git config core.hooksPath ops/hooks`. |
| `ops/nightly.py` | Nightly integration check, pipeline self-check, and failure alerts. systemd timer, `--all` at 03:15. |
| `ops/setup/configure-profiles.sh` | Configures the headless Hermes profiles. |
| `ops/systemd/` | `phpretro-orchestrator.{service,timer}`, `phpretro-nightly.{service,timer}`. |

## Nightly checks and alerts (`ops/nightly.py`)

| Job | What it does |
| --- | --- |
| `--integration` | Exports `origin/main` read-only, builds the server, starts it on a spare port, requests every route with its expected status and a key string, stops it. Result -> `nightly.json`. |
| `--selfcheck` | `python3 ops/orchestrator.py --selftest`, `bash -n` every hook, and the pre-push hook driven through a **real `git push`** in a scratch repo (protected path refused, in-scope push allowed, push to main refused). The project repo and its branches are never touched. |
| `--alerts` | Sends a one-line message **only** when something is wrong. No success messages. Runs hourly (cheap; the heavy checks are nightly). |

A failed integration check does not need a human: the orchestrator turns each
failing route into a planner fix unit (`fixes_route` records the route, so a
persistent failure does not pile up duplicates). A check that fails twice in a
row is an alert condition.

Alert conditions: no merge in 24h; a cap was hit; the STOP file exists; the
integration check or self-check failed twice in a row; disk over 85%.

Alerts go out on **ntfy**, the lightest Hermes platform: no account, no token,
no daemon on the public server. Inject a test failure with
`PHPRETRO_ALERT_TOPIC=<topic>`, or set `NTFY_TOPIC` in `~/.hermes/.env`; the
orchestrator prints the subscribe steps and the topic in `STATE.md` under
"## Alerts". `python3 ops/nightly.py --alerts --force-alert` re-sends an
existing condition; the same unchanged condition is otherwise re-nagged at most
every `PHPRETRO_ALERT_RENAG` seconds (default 6h).

## How a cycle decides

1. `git fetch`; load `units.yaml` plus the live state.
2. Ready units: `depends_on` all `merged`, paths disjoint from every unit
   already running. Up to `MAX_PARALLEL=4` builders start in their own
   worktree `~/work/<id>` on branch `unit/<id>`.
3. Builder runs headless (`hermes -z`, approvals bypassed, 25-minute cap).
   Tests first, then implementation, then `scripts/check.sh`.
4. `scripts/check.sh` in the worktree. On failure the tail of the output
   becomes the next attempt's feedback.
5. On pass: push, open PR, run the reviewer once for a JSON verdict. Only
   `severity: blocker` findings go back to the builder, one round maximum.
6. Merge queue under a lock: rebase on `main`, re-run `check.sh`, merge with
   `gh`. A conflict goes back to the same builder once.
7. Ladder on repeated failure: luna x2, deepseek-v4.1-flash x1, gpt-6.1-sol
   x1, then `parked` with the reason recorded. A parked unit gets at most 2
   planner retries, then `parked-final`.
8. When nothing is ready and design/parked units exist, the planner promotes a
   design unit into a full entry (splitting any `size: L`) or rewrites a parked
   unit.
9. Limits: per-run timeout, max attempts, `MAX_PARALLEL`, 12 merged units/day,
   60M tokens/day, 6M tokens per unit, and `~/phpretro-ops/STOP` halts all
   dispatch.

## Models and approvals

- builder: `gpt-6-luna`. reviewer: `deepseek-v4.1-flash`. planner:
  `deepseek-v4.1-flash`. `gpt-6.1-sol` only in the ladder's last step, for a
  planner run on a unit with unclear semantics, and as a second reviewer for
  diffs touching auth, sessions or schema.
- The reviewer is never the author's family: if deepseek wrote the code, luna
  reviews it and vice versa (`ops/orchestrator.py:reviewer_model_for`).
- Headless approvals are configured so no prompt can wait: `single_query_mode:
  deny`, a deny list of destructive globs (which fire even under `--yolo`), and
  an allowlist for git/go/gh/make. The deny list is the control the model
  cannot talk its way past.

## Where state lives

Everything the pipeline writes lives outside the repo, so `main` stays still:

```
~/phpretro-ops/state/STATE.md            counts, per-unit status, tokens, events,
                                         nightly pass/fail, alert setup
~/phpretro-ops/state/units.state.json    machine state
~/phpretro-ops/state/units.live.yaml     roadmap + runtime state
~/phpretro-ops/state/nightly.json        nightly check results + history
~/phpretro-ops/state/nightly-last.md     the same, readable
~/phpretro-ops/state/alerts.json         alert ledger (what was sent, when)
~/phpretro-ops/briefs/                   the exact prompt of every attempt
~/phpretro-ops/logs/                     agent output and *.usage.json per run
~/phpretro-ops/logs/nightly/             one JSON per nightly run
~/phpretro-ops/STOP                      touch this to halt all dispatch
```

## Install

```bash
git config core.hooksPath "$PWD/ops/hooks"
bash ops/setup/configure-profiles.sh
mkdir -p ~/phpretro-ops/{state,logs}
sudo cp ops/systemd/phpretro-orchestrator.* ops/systemd/phpretro-nightly.* ops/systemd/phpretro-alerts.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now phpretro-orchestrator.timer
sudo systemctl enable --now phpretro-nightly.timer
sudo systemctl enable --now phpretro-alerts.timer
```

To receive alerts, set `NTFY_TOPIC` (and `NTFY_PUBLISH_TOPIC`) in
`~/.hermes/.env` to a topic you subscribe to in the ntfy phone app. Nothing
else is required - no account, no token, no daemon.

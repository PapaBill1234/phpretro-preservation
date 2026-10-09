# Skill Doctor audit

Pinned upstream: https://github.com/evilstar2016/skill-doctor (MIT), npm version 0.7.0.

Install the runtime as Ubuntu's unprivileged account:

```sh
npm install --prefix "$HOME/phpretro-skill-doctor/runtime" @evilstar2025/skill-doctor@0.7.0 --ignore-scripts --no-audit --no-fund
python3 ops/skill-doctor/install_paused.py
```

The installer requires clean reviewed main, STOP and no reservations. It enables only an audit timer, every four hours. Run `python3 ops/skill_doctor.py` for a manual refresh; the full CLI is at `~/phpretro-skill-doctor/runtime/node_modules/.bin/skill-doctor`.

The collector runs `cost --platform codex --scope project --source skill --tokenizer approx --json` with an isolated HOME and no credentials. It neither launches MCP servers nor uses model inference nor changes agent settings. Reports and brief snapshots are private under `~/phpretro-skill-doctor`; only whitelisted counts reach the Builders dashboard. Collection skips active reservations. Stop scheduling with `systemctl --user disable --now phpretro-skill-doctor.timer`.

## Full upstream UI and CLI

The authenticated dashboard's Open full Skill Doctor link opens `/skill-doctor/`. The complete npm UI runs on loopback port 38123 behind the existing login and same-origin protections. Its bootstrap credential is private and forwarded only over loopback. API and asset URLs are scoped to the prefix; scans and benefit jobs retain streaming support. No credentials are exposed in URLs or dashboard data.

`~/.local/bin/skill-doctor` exposes all upstream CLI commands (`--help`). The UI and launcher share an isolated HOME; global settings apply to this Skill Doctor profile, not the authenticated Codex supervisor. The UI sees only its profile and PHPRetro checkout through a constrained Docker container. Existing Ubuntu Codex session directories, when present at UI startup, are mounted read-only for history analysis; auth.json is never mounted. Windows desktop history is not available on Ubuntu. Manual cleanup/configuration writes require the upstream previews/confirmations and can dirty the checkout; automation never applies them. Native directory dialogs require a desktop, so use the UI's manual path input on this headless host. Optional AI-assisted features require credentials configured by the owner in this private profile; none are copied or configured automatically.

OpenHands is not an upstream supported platform. Its latest completed builder/reviewer role brief is adapted into an isolated instruction snapshot. New runs also retain bounded metadata-only `.context.json` sidecars: request context/system/tool-schema estimates, tool calls/errors/repeats and completeness. Prompts, commands, outputs and credentials are never written to these sidecars. Historical runs without a sidecar remain unknown. The only enabled SDK tool is Execute; it is marked unused only when an observed completed run had no executions. Instruction necessity and realized savings cannot be inferred from this. Request estimates are not billed usage; existing charging remains authoritative. The dashboard exposes aggregate counts only. No automatic pruning is implemented.

Disable the full UI with `systemctl --user disable --now phpretro-skill-doctor-ui.service`. The coding STOP and disabled coding timers remain separate from both doctor services.

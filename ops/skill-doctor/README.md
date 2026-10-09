# Skill Doctor audit

Pinned upstream: https://github.com/evilstar2016/skill-doctor (MIT), version 0.7.0, source fe1f942cf715a47faa67def0fa5f07882f3a84dc. PHPRetro maintains a source extension for OpenHands discovery and receipt-backed sessions. Run `python3 ops/skill-doctor/build_extension.py` before the paused installer; it verifies/builds original source plus the maintained extension, records source hashes and package hash, and does not activate it. The installer requires this matching artifact and reviewed main.

OpenHands is selectable in scan settings and detected agents. Its optimization view reads real role receipts and context counters, including failed runs. Conversation transcripts were not retained by the SDK; older missing tool evidence stays unknown. A6API account calls are a separate billing view covering all inference keys in the current UTC day, bounded at 2000 calls. Session token counters and provider costs are not summed twice. Deep Scan remains manual; upstream null AI responses now generate a visible warning. Sol analysis uses high reasoning with an 8192 output-token ceiling; the small connection test uses no reasoning and 512 tokens. Embeddings remain enabled.

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

## Manual Deep Scan for builders and agents

Select `/home/ubuntu/phpretro-skill-doctor/agents` as the UI project to audit retained OpenHands builder/reviewer briefs for each current model family. The local collector refreshes this private audit workshop without inference. These SKILL.md records are labeled snapshots and are not enabled in Codex or OpenHands. Inspect real execution coverage on Builders; historical records without sidecars remain unknown. Do not infer instruction necessity or silently apply runtime prompt changes from a static audit.

The private profile is configured separately on Ubuntu for A6API `gpt-6.1-sol`; the UI and CLI adapter uses Responses with `reasoning.effort=high` and at most 4096 output tokens per request, retaining JSON output compatibility. Embeddings use the separately listed `text-embedding-3-small` model. Deep Scan and optional AI explanations run only when initiated manually; no AI scans are added to the timer. Provider bills include these manual calls. Four-hour collection remains local and does not initiate inference. Empty Codex history directories show a clean no-session state until actual native CLI sessions exist; SDK runs are never presented as Codex sessions.

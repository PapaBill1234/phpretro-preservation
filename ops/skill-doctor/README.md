# Skill Doctor audit

Pinned upstream: https://github.com/evilstar2016/skill-doctor (MIT), npm version 0.7.0.

Install the runtime as Ubuntu's unprivileged account:

```sh
npm install --prefix "$HOME/phpretro-skill-doctor/runtime" @evilstar2025/skill-doctor@0.7.0 --ignore-scripts --no-audit --no-fund
python3 ops/skill-doctor/install_paused.py
```

The installer requires clean reviewed main, STOP and no reservations. It enables only an audit timer, every four hours. Run `python3 ops/skill_doctor.py` for a manual refresh; the full CLI is at `~/phpretro-skill-doctor/runtime/node_modules/.bin/skill-doctor`.

The collector runs `cost --platform codex --scope project --source skill --tokenizer approx --json` with an isolated HOME and no credentials. It neither launches MCP servers nor uses model inference nor changes agent settings. Reports and brief snapshots are private under `~/phpretro-skill-doctor`; only whitelisted counts reach the Builders dashboard. Collection skips active reservations. Stop scheduling with `systemctl --user disable --now phpretro-skill-doctor.timer`.

OpenHands is not an upstream supported platform. Its latest completed builder/reviewer role brief is adapted into an isolated instruction snapshot for estimation only. Estimates exclude SDK system prompts, tool schemas and later conversation. No retained SDK tool history exists to prove unused resources. Counts are approximate context inventory, not billing, measured savings or recommendations to remove instructions. Supervisor work-directory inventory does not include its CLI-managed global prompt.

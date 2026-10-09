# Subscription supervisor (installed disabled)

This native Ubuntu service uses the official Codex CLI0.162.0 and ChatGPT
sign-in for gpt-6.1-sol. It is independent of the Windows app and RDP session.
Private auth lives in /home/ubuntu/phpretro-codex/private, mode700; auth.json
is mode600. No inference API key or alternate API endpoint is inherited.

The timer runs every30minutes after explicit activation. A healthy check uses
only local status and read-only account metadata; it does not invoke a model.
When a supported fault appears, Sol receives typed, sanitized facts and selects
one allowed action. Its job has no shell, unified-exec, hooks, web search or
subagents; it runs read-only with no approval prompts. The trusted Python
controller owns the fixed operational commands. It rechecks health, STOP and
quota immediately before acting and verifies the result afterward.

Supported fixes: restart billing collection, restart the dashboard, start a
missed controller cycle, or reconcile orphaned receipts through the existing
controller --no-dispatch path. Controller/receipt actions require no active
controller or workers. State corruption, low disk, code defects and ambiguous
failures remain unresolved. This initial version does not author source fixes.
It never removes intentional STOP, increases caps, expands canaries, waives
reviews, edits the usage ledger directly, or starts builders itself.

Model jobs require verified ChatGPT auth, gpt-6.1-sol availability, fresh readable
quota, ordinary usage permission, matching CLI version and exact-source runtime
validation. At90% used in either the five-hour or weekly window, jobs defer.
While a job runs, quota is checked every30seconds and missing/limited quota
cancels it. No automatic credits, resets, API billing fallback or model swap.
Concurrent account usage can move quota between observations; these are guarded
thresholds, not a promise of an exact percentage ceiling.

Maximum two model attempts per24hours; six-hour cooldown after every attempt,
including failures. Ten-minute model deadline and two-MB private output ceiling;
the whole systemd service has a15-minute backstop and KillMode=control-group.
A lock prevents overlapping cycles. Durable job PID/process identity prevents a
duplicate live job. Unreadable supervisor state fails closed without resetting
attempt history. Raw model events/decisions stay private; the authenticated
PHPRetro Builders page receives only enumerated statuses/actions, timestamps,
usage percentages and reported token counters. Missing usage displays Unknown.

Install: python3 ops/codex/install_paused.py from reviewed main with STOP and
zero reservations. This installs user units and the codex shell launcher,
explicitly disables the timer/service, and performs a read-only inspection.
It does not start inference or the pipeline. Sign-in can be completed through
the visible RDP CLI or codex login --device-auth.

After the autonomy canary succeeds and the coding pipeline is already active,
operator activation is: python3 ops/codex/activate.py --enable.
Disable: python3 ops/codex/activate.py --disable. Neither changes coding STOP.
Manual read-only inspection: python3 ops/codex_supervisor.py --inspect.
Do not enable until the user's requested autonomy run is complete. On activation,
retire the older desktop repair heartbeat to avoid two independent repair owners.

Monitor: PHPRetro #builders, systemctl --user status phpretro-codex-supervisor.timer,
and journalctl --user -u phpretro-codex-supervisor.service. Private model logs are
under ~/phpretro-codex/jobs; do not copy them to dashboard output or public PRs.

Official references: https://learn.chatgpt.com/docs/auth,
https://learn.chatgpt.com/docs/non-interactive-mode,
https://learn.chatgpt.com/docs/app-server, https://learn.chatgpt.com/docs/pricing.

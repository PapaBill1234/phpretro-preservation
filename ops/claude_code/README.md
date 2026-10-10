# Native Claude Code runtime

This replaces active OpenHands execution on the Ubuntu PHPRetro host. Native
Claude Code provides builder, independent reviewer and operational supervisor
sessions. OpenHands receipts and Canvas volumes remain historical/rollback data.

The pinned binary is `/home/ubuntu/.local/bin/claude`, version
`2.1.287 (Claude Code)`. Claude Code is the harness, not the model provider.
Builders retain Luna Ã¢â€ â€™ Sol Ã¢â€ â€™ DeepSeek escalation; independent reviewers use a
separate model family. Sol 6.1 supervises. All routes prefer A6API then admitted
Portdan fallback, using existing private Ubuntu credentials. No Anthropic login
is needed. Managed sessions receive only an ephemeral authenticated loopback
endpoint; provider credentials never enter the CLI, MCP children or Docker.

`gateway.py` translates Anthropic requests to Sol/Luna Responses or DeepSeek
chat requests. It preserves function calls/results and provider reasoning across
native resume, validates reported model aliases and numeric inclusive-cache
usage, and emits exclusive-cache Anthropic wire counters. A bounded nonstreaming
upstream response is sent as Anthropic SSE to the CLI. Unsupported content and
execution tools fail closed. Both response size and original timeout are bounded.

Builders have one explicit MCP tool, `execute`, in the existing credential-free,
network-disabled Docker sandbox. All native filesystem/terminal tools, hooks,
skills, slash commands, memory and automatic compaction are disabled in managed
pipeline sessions. Reviewers have no execution tools. Each request uses native
`--max-turns 1`; continuation resumes the same UUID inside the original receipt,
deadline, cash reservation and token allowance. Streamed assistant counters are
reconciled against strict final per-invocation counters. Native cumulative cost
on resume is not charged again. Missing usage receives a conservative full
request charge and stops; it is never marked complete.

The existing temporary two-family user policy remains. Different receipts alone
do not replace independent model families. Exact-head approval and CI remain.

All original limits/charges remain. A receipt-scoped gateway admits each physical
upstream attempt durably before transport, including fallback/reconnect attempts.
Its conservative input estimate is UTF-8 payload bytes plus4096 format overhead;
this estimate is explicitly not measured prompt tokenization. Context above the
60000-token input ceiling is denied before forwarding, with4096 output tokens.
The byte estimate and output must fit the remaining original hold. Unknown calls
retain their actual request holds under usagev2; v1 historical charges remain.
Unknown counters/identity/truncation stop the run without fabricated zero usage.

A6API billing and new Claude-harness receipts share the same provider cost basis:
use their maximum when reconciling daily spend, never add the same charge twice.
The original five-dollar daily estimate and observed balance guard stay active.
Portdan cash checks remain user-disabled, token charges retained, and unknown
Portdan model prices stay unknown. Failed Portdan DeepSeek capability evidence
is not promoted to verified fallback. This bridge is project-owned compatibility;
Anthropic does not officially support non-Claude models through gateways.

The dashboard's Claude panel shows installation/provider-credential/activation status and links
to the shared Doctor pages. Controlled receipts carry actual native session
identity, roles, final usage and bounded redacted timelines. Interactive native
transcripts are read as project-scoped metadata only, deduplicated against
controller sessions, and remain partial usage/context evidence. Old OpenHands
sessions keep their runtime labels. A6API billing calls remain separate evidence.
Doctor resources are audit snapshots, not proof of injected context. Unsupported
native configuration writes stay disabled. Deep/embedding scans remain manual.

## Reviewed cutover sequence

Keep the owned migration STOP until this sequence completes:

1. Build the pinned Doctor extension in a separate HOME, run its tests and the
   isolated browser fixture; retain exact-source/package hashes. The upstream
   tokenizer's two expensive existing tests require a 20-second test timeout on
   this host; their assertions are unchanged. Runtime time/spending limits are
   unchanged. The library test teardown explicitly drains React after cleanup.
2. Run `PHPRETRO_RUNTIME=claude-code python3 ops/claude_code/validate.py
   --doctor-evidence /home/ubuntu/phpretro-claude-code/doctor-browser-evidence.json`.
   Six non-provider checks may pass while provider remains false. Real pinned
   CLI loopback transport and the actual Docker MCP bridge use no paid inference.
3. Obtain a fresh independent exact-head maintenance source review and passing
   GitHub foundation CI. Publish only a reviewed branch/PR, never directly main.
   Existing maintenance review limits still apply.
4. Merge, fetch, and select clean `origin/main` in this worktree. Record the
   independent exact-head review in `state/claude-code-source-review.json`.
   Rebuild/verify matching Doctor package inputs as necessary, then run:
   `PHPRETRO_RUNTIME=claude-code python3 ops/claude_code/install_paused.py
   --doctor-manifest PATH_TO_BUILT_EXTENSION_MANIFEST`.
   The installer switches root/user service source paths, dashboard and Doctor
   runtime, disables old Codex supervision and Canvas restart, and retains STOP.
   A known backup is restored on installation failure; coding remains disabled.
5. After reviewed paused installation, run the explicit, once-per-source charged provider
   acceptance: `PHPRETRO_RUNTIME=claude-code python3 ops/claude_code/probe.py --run`.
   It uses the unchanged controller ledger/caps and a maintenance receipt, only
   under the unchanged owned STOP, after reviewed paused installation and six
   passing source checks. It cannot reroute a unit, clear STOP or create allowance.
   Inspect a failed receipt; do not repeat blindly or reset the attempt record.
   Use `--model gpt-6.1-sol` to check an explicitly unattempted model when an
   earlier model stopped the batch. Attempts are persisted before execution;
   completed and failed models cannot be repeated for the same source. A
   selected-model pass does not mean all configured models passed.
6. Repeat exact-source validation with `--provider-evidence
   /home/ubuntu/phpretro-ops/state/claude-code-provider.json` and the Doctor
   evidence. All seven checks must pass. Run `activate.py --enable` only then.
   It clears only the same owned temporary STOP, restores the previously
   authorized controller, and enables the native 30-minute Claude supervisor.
   A newer intentional STOP is preserved. Healthy/paused supervision uses no
   inference. Repairs remain typed existing reversible actions, two paid attempts
   per 24 hours with six-hour cooldown, not arbitrary host shell access.

F61's 2,995,501 historical tokens and 4,499 remaining allowance are unchanged.
Its current exact head still has no independent unit approval. Migration and
maintenance approval do not unblock, reroute, requeue or reset that unit.

Official references: [headless operation](https://code.claude.com/docs/en/headless),
[CLI flags](https://code.claude.com/docs/en/cli-reference),
[gateway compatibility](https://code.claude.com/docs/en/llm-gateway),
[custom models](https://code.claude.com/docs/en/model-config).

The installer normally requires reviewed `origin/main`. An explicit
`--defer-source-review` supports the user's deployment-before-review sequence
only for a clean published migration head with a private, exact-source,
four-hour authorization and the unchanged owned migration STOP. Installation
and Doctor manifests record review as pending. The bounded provider acceptance
can run while paused; ordinary coding activation still requires actual
independent source review. This never substitutes for unit approval or changes
any spending, token, provider or review-family limit.

On Ubuntu XFCE/RDP, `phpretro-claude-desktop.service` opens a terminal for each
active native builder. Windows follow the existing redacted assistant/tool
journal and show the original run identity and exit status. Closing a window
does not stop or duplicate its builder. No inference credentials are passed
to the desktop viewer. Completed windows remain visible for two minutes;
retained sessions and history remain available in Doctor.

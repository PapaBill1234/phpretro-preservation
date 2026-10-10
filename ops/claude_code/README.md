# Native Claude Code runtime

This replaces active OpenHands execution on the Ubuntu PHPRetro host. Native
Claude Code provides builder, independent reviewer and operational supervisor
sessions. OpenHands receipts and Canvas volumes remain historical/rollback data.

The pinned native binary is `/home/ubuntu/.local/bin/claude`, version
`2.1.287 (Claude Code)`. The initial model is `claude-sonnet-5-5`. Authentication
uses the operator's native Claude subscription login, without copying credentials
to Docker or putting them in the repository. Run on the host:

```sh
ssh -t phpretro '/home/ubuntu/.local/bin/claude auth login'
```

Builders have one explicit MCP tool, `execute`, in the existing credential-free,
network-disabled Docker sandbox. All native filesystem/terminal tools, hooks,
skills, slash commands, memory and automatic compaction are disabled in managed
pipeline sessions. Reviewers have no execution tools. Each request uses native
`--max-turns 1`; continuation resumes the same UUID inside the original receipt,
deadline, cash reservation and token allowance. Streamed assistant counters are
reconciled against strict final per-invocation counters. Native cumulative cost
on resume is not charged again. Missing usage receives a conservative full
request charge and stops; it is never marked complete.

The user requested full Claude replacement. Consequently the initial review
policy uses separate completed Claude author/reviewer sessions, with different
receipt IDs and native UUIDs, bound to the exact Git head. This is one model
family, not evidence of independent model families. Sensitive work retains the
same head, CI, receipt and merge requirements.

All existing limits and charges remain. The original $5/day estimated spending
guard is an API-equivalent quote, not a Claude subscription invoice or remaining
quota. CLI's soft cash option is not a hard guard: the trusted runner reserves
the full 1,004,096-token request ceiling and checks the original cash hold before
each invocation. This can limit concurrency. Historical A6API prices/billing are
not repriced at Claude rates; Portdan's user-disabled cash check stays disabled.
Claude quota/reset information is unavailable and must not be invented.

The dashboard's Claude panel shows installation/login/activation status and links
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
5. After native login, run the explicit, once-per-source charged provider
   acceptance: `PHPRETRO_RUNTIME=claude-code python3 ops/claude_code/probe.py --run`.
   It uses the unchanged controller ledger/caps and a maintenance receipt, only
   under the unchanged owned STOP, after reviewed paused installation and six
   passing source checks. It cannot reroute a unit, clear STOP or create allowance.
   Inspect a failed receipt; do not repeat blindly or reset the attempt record.
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
[authentication](https://code.claude.com/docs/en/authentication),
[Sonnet model/prices](https://platform.claude.com/docs/en/models/sonnet-5-5/overview).

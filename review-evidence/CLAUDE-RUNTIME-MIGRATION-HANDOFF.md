# Latest steering: Claude Code harness with A6API models

2026-10-10: user explicitly answered "just put a6api through it" and "use a6api our own models". This section overrides ALL earlier Anthropic subscription/login and same-Claude-family statements below. No Anthropic authentication question is pending. Target is native Claude Code 2.1.287 as harness, with original A6API-first/Portdan-second Sol6.1, Luna6 and DeepSeekv4.1Flash. Retired Haiku stays retired. Temporary two-family override remains; separate same-family sessions do not authorize unit approval.

Candidate /home/ubuntu/phpretro-claude-code/migration, branch codex/claude-code-runtime, draft PR111. Owned migration STOP and disabled root/old native timers remain; dashboards/Doctor/billing active, no workers/reservations, F61 still parked2995501/3000000,4499remaining. No activation/cutover or paid inference occurred during this revision. Private original provider file remains in place; CLI/MCP/Docker do not receive provider credentials. Thirty-minute chat continuation prompt is updated to this direction.

New receipt-scoped gateway implements Anthropic facade to existing Responses routes for Sol/Luna and chat for DeepSeek. CLI receives an ephemeral authenticated loopback endpoint with --bare/custom model; builders only Docker MCP execute, reviewers no tools. Actual native resume retains UUID, tool results and provider reasoning. Every physical upstream attempt, including fallback/reconnect, is durably charged before transport. Original input60000/output4096, original token/cash holds/deadline retained; UTF-8 byte+4096 bound is explicitly an estimate, not measured prompt tokens. Strict numeric inclusive-cache counters become exclusive-cache wire counters. Unknown usage/identity/truncation stops with conservative holds. New gateway usagev2 preserves historical nativev1 and SDKv1/v2/v3 charges. Portdan disabled cash guard is separate from known quote reporting; unknown prices stay unknown. A6API billing and Claude-harness receipt costs share one provider basis and cannot be double counted. Old route observations retain their timestamps and establish endpoints only, not new harness compatibility. Unverified Portdan DeepSeek fallback stays unverified.

Prepared Doctor uses the original shared pages for Claude: issues/resources, current usage, month/week/session costs, suggestions, verification, timeline, provider evidence, scan records/library/settings/mobile. Actual Sol/Luna/DeepSeek model filters work in a three-receipt synthetic browser fixture; historical native transcripts retain actual model labels but unknown provider/context/completeness. Doctor package unchanged ce2a65f20dbe50cfd965dd66056176293df174ba674af5086eea4d4554c2d213, NOT live installed. Sixteen browser cases passed. Live Doctor remains the older UI-only package, not this Claude candidate.

Evidence before final tiny numeric/metadata hardening:444 ops tests passed(2 platform skips); eight real installed-CLI adapter synthetic upstream cases passed, including all three models with builder tool/resume and tool-free review, fallback conservative charge and identity rejection. Twelve new gateway unit tests cover byte/remaining holds, malformed numeric/cache usage, denied reviewer tools, cancellation, original request holds, prelaunch zero, encrypted reasoning and truthful Portdan quotes. Final hardening additionally rejects completed zero counters and preserves reported model alias. Refresh relevant checks on final literal source; do not reuse old source hashes as new acceptance. New provider acceptance is still UNMEASURED; no external availability probes or paid calls have run.

Resume: wait for current validator SSH job to finish, then synchronize final small local source changes(gateway.py, worker.py, probe.py, test_claude_gateway.py), rerun targeted/full appropriate tests and browser on final source, refresh exact-source checks, commit a fast-forward revision and update PR111 description/CI. No force/direct-main push; authorized maintainer hook exception command-scoped only. Normal reviewed paused install remains gated by fresh independent exact-head source review. Original native maintenance review quota exhausted: earliest ordinary slot1791691145.3487856. Do not reset/reuse old Doctor review jobs or counters. After reviewed paused install, probe.py --run can make one bounded compatibility acceptance segment across the three models through original controller ledger under unchanged owned STOP; it is not a Sol availability poll, unit review or allowance reset. Inspect failures, no blind retries. All seven exact-source checks before activation. F61 stays parked; migration approval is not its unit approval. No automatic Deep/embedding scans.

Usage87percent five-hour/44percent weekly at this checkpoint. Skip scheduled work>=90percent and stop safely before95percent five-hour. Never consume reset/purchase credits. Keep safe pause and checkpoint larger work for eligible next run. No permission/attention questions or other-chat messages.

---

Earlier historical checkpoint (superseded where contradictory):

# PHPRetro native Claude Code migration

Checkpoint: 2026-10-10 10:12 UTC. The user explicitly replaced the OpenHands
objective with full native Claude Code execution on Ubuntu. This checkpoint
supersedes the prior OpenHands-only Doctor UI work and activation instructions.
Exclude hotel-drogon. No new permission/attention questions for routine work.

## Safe live state

Native Claude Code 2.1.287 is installed at `/home/ubuntu/.local/bin/claude`.
Subscription authentication was still absent at the last sanitized check:
`loggedIn=false`, `authMethod=none`. Required human login command:
`ssh -t phpretro '/home/ubuntu/.local/bin/claude auth login'`.
Never display, copy, transfer or commit native credentials.

Owned STOP: `/home/ubuntu/phpretro-ops/STOP`; pause owner
`codex-claude-code-runtime-migration`, mtime_ns 1791622371140315572,
previous_stop=false, previous_mode=autonomous. Root orchestrator and native
Codex supervisor timers are stopped. No running workers or reservations.
Dashboard/access/Doctor/billing remain available. The previous reviewed source
a8faf918dc99cd26ef2bb286bc1e75b3243c083f and the user's UI-only Doctor candidate
remain live. The Claude pipeline, services and Doctor package are NOT deployed.

The previous Doctor UI package SHA256 is
3d0f1b52cc381fee4fc95f943475b3fc55211e5c31e766ae353aa2a94347af55,
with reviewed=false / acceptance_complete=false. Its existing rollback remains
`/home/ubuntu/phpretro-skill-doctor/ui-parity-deployments/1791616264`.

F61 remains PARKED: PR95, attempt2, tokens2,995,501 of unchanged3,000,000;
remaining4,499; exact head f87cc4b2198abfebe1ff6d16548ba43c318f6d5b. No fresh
independent unit approval. F62/F63 remain dependent. Do not reroute, requeue,
replace units, erase charges, raise budgets or interpret maintenance approval
as unit approval. F61 cannot cover the new native request bound either.

## Prepared source and evidence

Isolated source: `/home/ubuntu/phpretro-claude-code/migration`, branch
`codex/claude-code-runtime`, based on reviewed a8faf918dc99cd26ef2bb286bc1e75b3243c083f.
Local maintained mirror: `implementation/ops`. Commit/PR publication follows
this checkpoint; inspect Git/artifact state for the exact resulting head.

Exact implementation fingerprint:
6665a13d066d0d37d1891c427811f13ace396986b53979fa5f9ed42b53013759.
Prepared Doctor package SHA256:
ce2a65f20dbe50cfd965dd66056176293df174ba674af5086eea4d4554c2d213.
Manifest: `/home/ubuntu/phpretro-claude-code/doctor-build-home/phpretro-skill-doctor/extension-manifest.json`.
Tool image `phpretro-tools:20261010`:
sha256:0e72f56c64ca83a325a647bd33a306d2bd7cdf509314f26bf0d912a920dc957e.
Vulnerability snapshot1791624276. Final exact validation1791627420.764694.

Actual acceptance:

- 432 ops tests pass, two platform-dependent skips; 25 new Claude cases.
- All 754 upstream/extension Doctor tests pass across97files; typecheck/package
  pass. Host command used20-second per-test timeout, two workers. Two unchanged
  upstream tokenizer assertions take6.9 and16.2seconds; default5seconds was
  insufficient. No runtime time/spending cap was raised. Library teardown now
  cleans/drains React; the real missing error-alert accessibility was repaired.
- 15 isolated browser cases pass, no browser errors, shared original layouts,
  including all Doctor pages, Claude wizard, main dashboard and legacy bookmark.
  The Claude receipt is explicitly SYNTHETIC fixture data, never live history.
  Historical rows are actual retained metadata. No Deep/embedding/paid scan ran.
- Four real pinned CLI loopback synthetic transport cases pass: text, actual
  native MCP/resume behavior,429 with no hidden retry,wrong model rejection.
- Actual Docker MCP bridge executes, denies a host-only file and cancellation,
  drains the container; zero inference.
- All six non-provider exact-source checks pass: foundation,ops,frontend,
  isolation,lifecycle,resources. Provider=false, overallpassed=false honestly.
  This is NOT real Anthropic identity/entitlement/request/usage evidence.
- JavaScript syntax and Git whitespace checks pass.

Private logs/evidence: `/home/ubuntu/phpretro-claude-code/` contains
doctor-tests.log,doctor-build.log,ui-browser.log,doctor-browser-evidence.json,
validation.log and ui-browser screenshots. Exact validator state is
`/home/ubuntu/phpretro-ops/state/claude-code-validation.json`.

## Implemented cutover contract

Native subscription inference stays on the trusted host. Builders have only the
credential-free Docker MCP execute tool; reviewers have no tools. Managed host
skills/memory/plugins/hooks are disabled. The runner admits one physical request
per invocation, resumes the same UUID, retains original receipt/deadline/caps,
reconciles strict exclusive-cache final usage, and never double-charges native
cumulative resumed cost. Unknown calls receive1,004,096-token charge and stop.
Original daily estimated$5 cap and historical A6API/Portdan cash behavior remain.
Subscription quotes are API equivalents, never an invoice/quota/reset claim.

Optional reviewer-policy question went unanswered; after a reasonable wait the
stated assumption was separate Claude author/reviewer sessions for full native
replacement. Policy uses one Claude family; completed distinct receipts/UUIDs
and exact Git head are mandatory. Do not call this independent model families.

The prepared installer switches root/user source paths, dashboard and Doctor,
stops Docker-managed Canvas and its restart policy, retains rollback/runtime/
volumes/history, and leaves STOP. Failure restores a known backup while keeping
coding disabled. Activation clears only the unchanged owned migration STOP after
all seven fresh exact-source checks and login. New native supervisor cadence is
30minutes; healthy/paused checks use no inference. Two paid typed repair
attempts/24hours with6hourcooldown remain; no arbitrary host code repair tool.
Doctor uses the shared original pages, actual managed receipts/redacted timeline,
partial deduplicated native transcript metadata, separate A6API billing evidence.
Interactive context remains unknown; unsupported native writes stay disabled.

## Remaining gates and continuation

1. Publish isolated draft PR with explicit pending login/provider/review; attach
   it to this chat. No force/direct-main push. A command-scoped maintainer hook
   exception is authorized for protected ops paths, not failed checks.
2. Wait for a NEW legitimate maintenance exact-head independent source review.
   Existing quota is exhausted: two completed reviews started1791604745.3487856
   and1791611475.0008192. Earliest ordinary24hour slot1791691145.3487856.
   Do not reuse the Doctor logical task, reset duration/counters or evade quota.
3. Passing CI+independent review before merge and reviewed paused install.
   Detailed sequence is `ops/claude_code/README.md`. Installer requires clean
   origin/main, exact six-check evidence and independent reviewed head.
4. Once logged in and paused installation is reviewed, run the explicit native
   `probe.py --run` ONCE for this source. It requires owned STOP and existing
   controller lock/caps/ledger; it cannot dispatch/requeue units or clear STOP.
   Inspect its receipt on failure; never blind retry/reset its attempt record.
5. Add real provider evidence to exact validation; then `activate.py --enable`.
   Preserve a later intentional STOP and F61 parking. Claim native delivery only
   after real exact-head unit approval/CI/merge, not migration maintenance checks.

Thirty-minute chat automation should continue this migration under usage guards,
quiet while unchanged, without obsolete OpenHands activation or auto Deep Scan.
Check usage first; skip>=90percent five-hour/weekly, stop before95percent
five-hour. Never use reset/purchase credits. One bounded segment per scheduled
run, about15minutes, checkpoint work. Pending login/quota are safe waits; don't
request attention repeatedly or invent completion. Use private credentials in
place, no process argv/environment/Docker config dumps, no messages to other chats.

Final whitespace cleanup changed the fingerprint above. All six non-provider exact-source checks passed again on that literal source at1791627420.764694. Provider remains false and overallpassed=false; native login is absent. Doctor inputs/package and all 754 tests are unchanged. Fifteen browser cases passed again on the final fingerprint. The thirty-minute chat heartbeat was reactivated with Claude migration priority and the same guards.

Publication checkpoint: committed clean f22706152ff6c0847c13892ce1168c8e29d283fd, pushed codex/claude-code-runtime with the authorized command-scoped maintainer hook exception. Draft PR https://github.com/PapaBill1234/phpretro-preservation/pull/111 is attached to this chat. Foundation CI passed for f22706152ff6c0847c13892ce1168c8e29d283fd (21seconds, run38044486149); this does not provide independent source review. All six final exact-source checks passed, provider remains unmeasured/login false. This publication note is mirrored outside the Git checkout to keep the reviewed candidate clean. Scheduled continuation is ACTIVE every30minutes. Codex use at publication:68percent five-hour,41percent weekly; no reset/purchase used.

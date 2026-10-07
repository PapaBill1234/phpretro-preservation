# Maintenance A: delegated owner decisions

Scope: independent audit B2, B4, B6 and E Prompt 1, with the owner's
maintenance/deployment overrides. This is an authorized ops branch, not a
builder unit. The STOP file remains present throughout preparation. No
running Hermes jobs are interrupted. The desktop remains enabled.

- Retain every local check, quality check, protected path, cap and serialized
  merge lock. Preserve the deployed 30/day cap with its nightly 12/day revert.
  Add staff paths to the existing sensitive-path second review, which also
  uses a family different from its author and primary reviewer.
- Review is mandatory. A strictly parsed successful review needs an immutable
  receipt matching the exact head and reviewer family. A block parks immediately;
  a fix gets at most one repair build, and remaining blockers park. Gate and
  quality checks repeat after rebase. The merge API is bound to the reviewed head.
- Review outages get one retry in another family. Use Claude Sonnet 5.5 on A6API
  only for this bounded fallback: its ID is in the installed provider model
  inventory. Using the author's family as fallback would weaken independence.
  Provider faults and admission denials defer the PR; timeout/malformed
  reviews park only that unit. Git/GitHub inventory outages defer a cycle
  without creating permanent STOP; accounting failures still create STOP.
- Jev a/b are budgeted advisory observations, never routing authority. Retain
  deterministic timeout, split, ladder and cap rules. Jev c has no review waiver
  or provider call. Remove Token Terminator's automatic cycle guard and uninstall
  its builder plugin; retain all existing telemetry and historical artifacts.
- Immutable run IDs make briefs, logs, usage and verdict receipts non-overwriting.
  Append spend before publication; append outcome separately without charging
  twice. Only real builder launches consume attempts; provider faults consume
  none. Preserve previous legacy attempt counts as the stricter baseline.
- Reserve each paid role's remaining unit allowance (audit at most 3M; Jev at
  most 36,864 tokens) before launching. All roles honor STOP, daily/individual
  caps and provider backoff. Reservations are conservative admission accounting,
  not a claim of provider-enforced token limits. Overspend stops dispatch.
- Three consecutive A6API provider errors pause all new paid dispatch; automatic
  backoff applies before that. An explicit owner recovery is required after the
  circuit opens. Ordinary reviewer failures do not stop other units.
- Validate an entire plan before mutating anything. Existing IDs are never
  replaced, even on promotion; use fresh children. Reject runtime identities,
  protected/escaping paths, invalid statuses and self/unknown/cyclic dependencies.
  First replacement inherits the parent's prerequisites; consumers wait for all
  children. Delivered history is not changed.
- Atomic snapshots use validated replacement and file/directory fsync. Ledger
  writes are append-only and durable. Seed missing legacy spend from valid
  pre-maintenance counters, with explicit provenance, never guessed zeros.
  Corrupt counters recover from the ledger; invalid or unsettled ledger entries
  keep STOP present rather than relaunching an unaccounted worker. UTC daily
  resets remain valid; unit lifetime counters never reset.
- Reconcile all merged unit PRs using merge-commit ancestry in fetched main.
  Preserve each prior unit record in append-only reconciliation history. Record
  adoption separately from new merges; never redispatch an accepted delivery.
  This owner override records Git delivery, not a claim of capture parity.
- One-time main protection: no required remote status checks, no force push,
  no deletion. Preserve existing admin enforcement and conversation resolution.
  A runtime merge refusal parks the unit and never rewrites protection.

Deployment requires the complete local gate, ops regressions, selftest and a
successful independent DeepSeek review on the exact candidate commit. Confirm
workers and merge/planner/reviewer jobs have drained, merge an ops PR, deploy,
run deployed tests/selftest and one cycle with dispatch disabled, then observe
three real cycles. On a deployment invariant failure, create STOP first, allow
existing jobs to finish, restore the baseline/tagged source and backed-up state,
preserve post-backup ledgers/history, record the reason and leave STOP present.

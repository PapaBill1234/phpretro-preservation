# Maintenance C: bounded preparation, model policy and actual timing

The owner's 2026-10-07 overrides replace the audit's disabled two-unit pilot
and two-unit buffer. This changes pipeline, measurement and test quality only.
The approved Go/React, MariaDB with Redis support, Habbo/Atom/theme-system,
Polaris and preserved-legacy roadmap remains unchanged. No product code, tests,
acceptance criteria, feature priority, storage contract or theme design changes.
Severity decides execution priority, as explicitly authorized by this prompt.

## Effective models and reasoning

| Role | Setting |
|---|---|
| Builder, ordinary launches 1–3 | gpt-6-luna / medium |
| Builder, security/persistence/session/auth paths or acceptance; launch 4 | gpt-6.1-sol / medium |
| Primary reviewer of new GPT-authored work | deepseek-v4.1-flash; medium for high risk, low otherwise |
| Historical DeepSeek author, high risk | Sol / medium, to retain a different family |
| Once-only unavailable-review fallback / sensitive second review | Existing alternate-family policy, with risk-based reasoning; no waiver |
| Planner, including Sol when existing unclear-semantics routing selects it | low |
| Weekly auditor | gpt-6.1-sol / medium |

Risk detection covers auth/account/session, security, audit/staff, cache,
storage/database/migrations, server boundaries and Polaris; it also reads the
written title/acceptance and, for review, the actual diff. This is conservative:
shared server/staff files may use Sol even for a small edit. Old model overrides
cannot select a builder outside the owner rule. Jev remains advisory, and every
merge still needs valid independent approval tied to its exact current head.

The audit's supplied tariffs make Sol uncached input/output 6.67 times Luna and
cache-read 3.33 times Luna. These are rate comparisons, not measured per-unit
cost increases or provider bills. Medium reasoning may change token use.
Run metadata records effective model/reasoning and cache read/write/reasoning
categories. Incomplete calls and unknown cached tariffs remain unpriced; the
existing conservative token charge, reservations and all caps stay in force.
No premium audit model is introduced. Prompts/transcripts are excluded from
the new metadata and normalized usage records.

## Ready buffer and single writer

The target is eight dependency-satisfied, evidence-ready units with disjoint
declared paths, before daily admission. A single staged planner can prepare
up to the existing three-slice limit for one approved parent while builders
run. It receives an immutable board/source snapshot and cannot apply output.
Only the locked cycle writer settles usage, validates the current contract
revision, IDs/DAG, paths, evidence, STOP and budgets, then applies all or none.
Counter/status progress on unrelated builders does not stale a contract;
changed topology, source or parent eligibility does. A stale revision is
recorded and not automatically retried on that same revision.

Severity orders builders and planner targets; a QA prefix no longer defers a
security fix. Plans inherit the parent's severity, and depth is bounded at two
new generations to prevent endless fresh-ID splits. Existing planner retries,
four builder launches, slice limit, per-unit and daily token caps, merge cap,
guards, STOP, local gate and independent review are retained. Permanent guard
or policy refusals are not routed into fresh-ID rewrites. An exhausted parent
cannot prevent another eligible parent from planning.

Maintenance B's twelve reserved IDs without distinct acceptance remain in the
roadmap. They cannot be automatically promoted without written acceptance.
F35/F38's missing concrete adapter contracts cannot be invented to fill eight
slots. Existing cards/scope remain; readiness may therefore be below eight.
Nightly fix planning retains its existing single-writer validation and takes
precedence over buffer preparation when already queued. Weekly audit is checked
independently after preparation so continuous planning cannot defer it forever.

## Timing, prefix and branch recovery

Static builder constraints precede every variable unit field. The commit prefix
and document filename remain explicitly bound to the unit below that prefix.
Meaning is preserved. API/system context may still affect actual cache reuse;
no saving or speedup is claimed without provider counters and comparable runs.

Immutable process receipts independently observe exits and the existing absolute
dispatch deadline while the writer is checking/reviewing another job. Observers
write metadata only, never scheduler/accounting state. The existing timeout and
usage-flush handler remains. Deployed jobs are drained naturally before source
changes; no running job is interrupted by maintenance. Check, merge wait,
planner validation, ready depth and idle reasons are recorded separately.
Metadata failures stop admission; usage is retained before publication.
Already-running builders and the staged planner drain and settle even if another
serial job fails. A failed pre-launch receipt cancels that reservation without
starting a worker; a failed post-launch receipt retains the spend. Planner root,
depth and stale-revision bounds survive runtime YAML serialization.

Maintenance B's first live cycle failed because F38's local and remote histories
diverged (four local commits, one remote). Recovery now retains the remote history
with a normal merge, aborts conflicts and parks dirty/conflicting work without
discarding it, consuming an attempt or pushing. The repository's no-force-push
rule also requires integrating main with a normal merge instead of rebasing and
force-pushing unit branches. Every existing scope, full check, quality and
independent-review gate reruns on that integrated head before a normal push.
No protection is deleted or bypassed. This resolves a deployment prerequisite,
not a product feature or roadmap change.

## Baseline and rollout

The frozen 24-hour baseline ending 2026-10-07 09:55:46 UTC has one evidence-ready
unit and a 14.45-minute dispatch-to-merge median for eleven distinct Git-delivered
units. Historical average builder occupancy is n/a: publication/run-end records
do not prove process exit. Git deliveries include documents/scaffolds and are
not product completion. Elapsed delivery time includes retries and idle/STOP.
Three observed cycles cannot establish a causal model/speed comparison.

Previous A safety controls are included in B's merged baseline; B's exact-head
core, quality and measurement reviews and all checks passed. Its deployment
rolled back at branch recovery, with STOP retained. C builds on that reviewed
combined candidate, fixes the prerequisite and retains its gates. Before deploy:
full local gate, ops/selftest, and different-family exact-head review. Then STOP,
drain, backup, normal ops PR merge, deployed tests/selftest, dispatch-disabled
cycle, and three real cycles. On error, duplicate dispatch/delivery, decreased
counters or failed selftest: STOP, drain without killing work, restore tag and
source/state backup while preserving append-only usage and Git deliveries,
record the cause in STATE.md, and leave STOP in place.

# Maintenance B: measurement and test-quality decisions

The owner's 2026-10-07 instruction fixes the approved scope: preserve original
PHPRetro behavior where the roadmap specifies it, Redis, Go backend, React
frontend, new Habbo theme, extensible theme system, Atom CMS theme and Polaris
integration. This overrides older Atom deferrals and audit assumptions of a
strict one-for-one preservation. No feature, priority, architecture, storage
choice, theme design, unit ID or roadmap entry changes in this maintenance.
MariaDB remains authoritative; Redis remains a supporting service, as written
in DECISIONS.md:23. Missing acceptance details are gaps, not permission waits.

## Measurement decisions

- Retain all 56 canonical cards and report all 68 runtime cards separately.
  Design placeholders stay in the approved roadmap. The overlapping platform
  summaries do not inflate its denominator. Git delivery, canonical status,
  runtime status and classification are distinct columns; no history is deleted.
- Classes: not started; designed (specification/evidence/documents); scaffold
  (fixtures, demo data, in-memory stand-ins, unconnected adapters); implemented
  (real implementation wired to the intended backend and tested); verified
  (implementation tests independently compared with its acceptance source).
  Infrastructure utilities may be implemented without being product features.
- Criteria are copied verbatim from units.yaml; where absent, use the nearest
  written acceptance/observable statement in the existing candidate design.
  Retain runtime-promoted criteria with separate provenance. No new behavioral
  acceptance requirements are invented. New delivery or changed source invalidates
  the assessment instead of automatically promoting it from a merge or coverage.
- Legacy tests need original-source or retained-capture provenance. New features
  use approved roadmap/design documents, including new security contracts.
  Citations alone do not prove parity: independent review must check expected
  behavior against that source. A guessed label never waives this gate.
- tests/golden/original/ was not populated: Docker returned permission denied
  for unix:///var/run/docker.sock. No real site, external capture, new database,
  privilege workaround or architecture was used. Optional capture work is skipped.

## Recorded contract gaps (no feature substitutions)

- F31-F34, F39, F41-F47 have reserved identifiers but no distinct new acceptance
  boundaries in their design documents. Preserve them; use the nearest written
  statement and report the gap instead of removing or renumbering them.
- F35: docs/roadmap/F31-F45-candidate-design.md:53 specifies atomic audited writes
  but leaves the selected mutation, schema, actor fields and transaction boundary
  open. internal/audit/audit.go uses a synthetic schema; no approved real adapter
  defines zero-row success semantics. Record the audit's RowsAffected concern;
  do not build a new schema/store or assert a new persistence contract.
- F38/F38-a: the same design's line 56 requires durable atomic replay but leaves
  persistence and compare/update locking open. replay.go delegates to an interface;
  replay_test.go implements its own file store. Reopening that fake does not prove
  production durability. Keep the existing tests/assertions and independent
  review; report scaffold and the missing adapter contract.
- F21 is approved as a mutation workflow, but current settings.go exposes only
  a read/validation method. Report scaffold; do not add a feature in maintenance.
- Habbo and Atom theme scope is approved by the owner, but their concrete package,
  assets and visual acceptance inventory is not written in the cited roadmap.
  Report the closest written versioned-theme requirement plus this gap. Do not
  design the themes or infer rights, asset inventories or emulator-write scope.
- Cache/session support is already required by DECISIONS.md:23 and F50; F38
  already requires durable replay. Their replacements are scheduled at the
  requirement level. Other product memory stores whose real replacement is not
  explicitly scheduled are inventoried as unscheduled, without creating units
  or choosing new persistence. Normal test-only mocks are reported separately.

## Quality/deployment decisions

Removal checks accept a named behavioral assertion against a compilable mutant;
compilation errors, panics, race errors, timeouts and tool failures are not proof.
The focused original tests must pass before mutation; an already failing test
cannot prove that removing production behavior caused its assertion to fail.
Mutations preserve source bytes and the Git index, and run in isolated worktrees.
Missing, malformed or erroring coverage fails even with a documented exemption;
only valid below-floor coverage retains the existing documented-exemption rule.
If the shared quality module is unavailable, set STOP before another admission.
A successful process exit accompanied by a provider-outage signal cannot approve
review. Regression tests cover these cases and zero-spend worker-launch recovery.
The dotted Sonnet route returned HTTP 400 with unsupported request fields;
`claude-sonnet-5-5` returned a complete review through the same A6API provider.
Use that working route for the existing once-only alternate-family fallback.
This changes no builder ladder or review independence requirement.
No overlapping product tests are removed: the evidence does not justify losing
assertions, and missing F35/F38 contracts prevent replacement adapter tests.

Maintenance A's pending fail-closed controls are included before B deployment.
The existing STOP from A's provider failures remains present. All gates, caps,
protected paths, STOP and independent review remain. The candidate needs the full
local gate, ops tests/selftest and a valid review on its exact head from a different
model family. Deployment drains jobs without killing any; it runs deployed checks
and a dispatch-disabled cycle before observing three cycles. Provider failures
cannot count as successful review or justify removal of STOP. Rollback preserves
append-only actual spend and delivery history rather than undoing real work.

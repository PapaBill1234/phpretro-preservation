# Handoff: Design PHP-Retro Project and Profile Skills

## Objective

Design a small, project-specific skill system for the `phpretro-preservation` repository and its live Hermes agent profiles. The goal is to make future agents better at this repository's actual workflows without duplicating or replacing the existing global Hermes skill catalog.

This is a design task first. Do not install, overwrite, or evolve live skills until the proposed skill boundaries and target locations have been reviewed.

## Repository

Project root:

`C:\Users\Karim\Documents\ChatGPT\New project\phpretro-preservation`

The repository uses Go and contains project orchestration rules in `AGENTS.md`. The active branch at the time of this handoff was `recovery/f8-kanban-failsafe`; re-check the branch and status before making changes.

## Existing project guidance

Read `AGENTS.md` completely before designing anything. It defines the project-specific operating model, including:

- Sol/coordinator ownership and Luna worker profiles
- A6API-only model policy for coordinator and subagents
- Kanban board and profile names
- bounded cards, isolated worktrees, base SHA checks, and accepted parent results
- reviewer independence
- continuation invariant: every coordinator unit must plan a successor
- dispatch preflight and board-health checks
- Jev's advisory/evidence-backed role
- economics and telemetry requirements
- coordinator ownership of security, production, schema, and runner decisions

Do not weaken or contradict these rules in a skill.

## Current Hermes skill layout

Shared/global live skills:

`C:\Users\Karim\AppData\Local\hermes-phpretro\skills`

Profile-specific live skill trees:

- `C:\Users\Karim\AppData\Local\hermes-phpretro\profiles\coordinator\skills`
- `C:\Users\Karim\AppData\Local\hermes-phpretro\profiles\backend\skills`
- `C:\Users\Karim\AppData\Local\hermes-phpretro\profiles\frontend\skills`
- `C:\Users\Karim\AppData\Local\hermes-phpretro\profiles\reviewer\skills`
- `C:\Users\Karim\AppData\Local\hermes-phpretro\profiles\visual\skills`

These profile trees contain mostly copies of the broad Hermes skill inventory. They are not currently a tailored PHP-Retro skill set.

Project-local search found no `SKILL.md` files in the repository. The project has `AGENTS.md`, but that is project context, not a Hermes skill.

## Why this handoff exists

A previous Hermes self-evolution run targeted a broad/global skill inventory. Its output included unrelated skills such as Apple Notes and Apple Reminders. That was not evidence of a PHP-Retro failure; it happened because no PHP-Retro-specific skills existed and the run was not restricted to a project-specific target set.

The self-evolution project generated candidate files under:

`C:\Users\Karim\AppData\Local\hermes-phpretro\work\hermes-agent-self-evolution\runs\...\candidates`

Each candidate generally has:

- `baseline_skill.md`: original source text used for evaluation
- `evolved_skill.md`: generated proposal

The evolution code explicitly saves proposals and does not modify source skill files automatically. Do not assume any candidate is deployed.

## Design goals

Create only skills that add repository-specific operational value. Prefer a small set of composable skills over one huge router or project manual.

Candidate areas to evaluate:

1. **Kanban coordinator operations**
   - inspect current board state
   - select the smallest authorized next unit
   - create dependency-linked implementation/review/successor cards
   - verify base SHA ancestry and accepted terminal parents before dispatch
   - perform continuation and board-health checkpoints

2. **Repository verification and evidence**
   - inspect source, diffs, tests, and authoritative commits
   - distinguish worktree changes, commits, reviews, integration, and verified delivery
   - produce concise evidence-backed handoffs

3. **Backend Go workflow**
   - contracts, adapters, tests, and ownership boundaries
   - project-specific verification commands discovered from the repository
   - no invented schema or production assumptions

4. **Frontend/localization workflow**
   - React/TypeScript boundaries if present in the current repository state
   - localization regression coverage and evidence requirements
   - avoid visual changes unless assigned to the frontend/visual scope

5. **Independent reviewer workflow**
   - review findings first, ordered by severity
   - verify acceptance criteria and tests independently
   - do not approve a worker's own result

6. **Visual/fixture workflow**, only if the repository contains a real visual scope
   - inspect existing conventions before inventing fixtures
   - keep visual work isolated from backend/contracts

7. **Card authoring and dispatch readiness**
   - translate roadmap scope into a bounded card with exact file scope, base SHA, evidence, tests, done criteria, stop conditions, and token cap
   - record dependencies and distinguish a ready card from a merely drafted card
   - preflight accepted ancestry and terminal parent results before unblocking or dispatching
   - prevent two active cards from editing overlapping files
   - avoid worktree-only or stale-ancestry cards

8. **Worker implementation handoff**
   - inspect the assigned card before editing
   - stay within the recorded file scope and stop when the scope is insufficient
   - report authoritative commit, changed files, tests, review state, and base SHA
   - distinguish local success from integrated, reviewed, and verified delivery

9. **Failure recovery and card correction**
   - classify failures as scope error, stale base, dependency error, test/evidence failure, environment/runner failure, or implementation defect
   - preserve failed-card evidence and do not mask it with a replacement card
   - correct the root cause, recreate stale cards from the accepted integration head, and link recovery work to the original card
   - verify that a recovered result is independently reviewed before acceptance

10. **Roadmap continuation and project-wide planning**
   - inspect the current roadmap and completed work, not only the latest localization unit
   - select the smallest source-backed next unit across backend, frontend, adapters, tests, evidence, infrastructure, and integration work
   - create the next implementation/review cards plus a successor coordinator card before completing a coordinator unit
   - stop only for an explicit stop condition, exhausted authorized scope, hard dependency, or operator-owned gate

Do not create all ten automatically. First inspect the source tree, tests, scripts, board/card history, recent commits, and current roadmap to determine which procedures are real, recurring, and sufficiently distinct to deserve skills. The card-related areas are high priority because many previous cards failed; the next AI must diagnose those failures from evidence rather than merely add more generic instructions.

## Card-failure investigation required before drafting

The next AI should explicitly review failed and recovered cards from the durable Kanban board and correlate them with repository history. For each failure, capture:

- card ID, title, profile, status, base SHA, parent/dependency state, and worktree/commit identifiers;
- the failure category and the first observable cause;
- whether the card was incorrectly scoped, dispatched from a stale base, blocked by an unaccepted parent, or failed during implementation/review/verification;
- whether the failure was repeated by a sibling card or caused by the dispatcher/board workflow;
- the smallest reusable procedure that would prevent recurrence;
- the evidence and test gate that should be added to a future card.

Do not assume localization was the only source of failures. Examine the whole project history and roadmap for recurring problems involving contracts, adapters, React/frontend work, tests, evidence documents, integration, worktree ancestry, review handoffs, and continuation planning. A card skill should improve card quality and lifecycle control; it should not turn every implementation task into an oversized checklist.

Potential card skills may need to be separated by lifecycle rather than technology:

- `phpretro-card-authoring`: write bounded, dependency-aware cards;
- `phpretro-dispatch-preflight`: verify base SHA, parents, file conflicts, and readiness;
- `phpretro-worker-handoff`: produce authoritative implementation evidence;
- `phpretro-card-recovery`: classify and recover failed/stale cards;
- `phpretro-coordinator-continuation`: maintain the roadmap and successor invariant.

These are names for investigation, not pre-approved files. Consolidate overlapping procedures after inspecting the real failures.

## Skill placement decision

Determine whether each proposed skill should be:

- project-local and committed in this repository, if the repository supports/consumes project-local skills;
- a user-local Hermes skill under the active Hermes home, if it is specific to this user's local orchestration setup;
- profile-specific under one or more `profiles/<name>/skills` trees, if it truly belongs to a role;
- shared/global, only if it is broadly useful outside PHP-Retro.

Do not confuse these locations. In-repo skill authoring guidance says `skill_manage(action='create')` creates user-local skills; it does not create committed in-repo skills. For committed repository skills, use the repository's established layout and normal file-edit/git workflow after inspecting its conventions.

If no project-local skill mechanism is currently configured, propose the smallest supported arrangement rather than silently inventing a loader or directory convention.

## Required design constraints

- Preserve `AGENTS.md` as the project rule source of truth.
- Skills should reference Hermes tools and repository-relative paths where applicable.
- Do not hardcode this machine's absolute paths in a committed skill.
- Do not put secrets, credentials, or production data in skills.
- Keep descriptions concise and trigger-oriented.
- Include explicit "When to use" and "Do not use for" boundaries.
- Every procedure step should have a checkable completion criterion.
- Include verification commands based on the actual repository, not guessed commands.
- Avoid a giant routing/hub skill that merely points to other skills.
- Avoid duplicating the same skill in every profile unless the profile genuinely needs a distinct variant.
- Keep coordinator-only decisions separate from worker procedures.
- Keep reviewer skills independent from implementation skills.
- Do not run the self-evolution pipeline during initial design.
- Do not deploy generated candidates as part of this handoff.

## Full-program requirement

This is not a request for only a cautious first set. The user is willing to invest in evolving the skills and wants a complete plan for extracting the project's full potential from the live agents. The next AI must design the entire project-specific skill architecture before implementation, while still using evidence to decide exact wording, overlap, and evaluation cases.

The project currently has no PHP-Retro-specific `SKILL.md` files, so the full program must cover both skill creation and the controlled path to live deployment. Do not confuse a complete plan with deploying everything blindly. The plan must enumerate the complete target surface, dependencies, evaluation method, rollout order, rollback path, and acceptance criteria.

## Complete skill architecture to design

The next AI should assess and design the following complete layers. It may merge items when the repository evidence shows that separation would create duplication, but every capability must be accounted for.

### 1. Coordinator and roadmap control

- project orientation and source-of-truth discovery;
- roadmap decomposition into the smallest authorized unit;
- card authoring with exact file scope, base SHA, evidence, tests, done criteria, stop conditions, token cap, and owner;
- dependency graph construction and readiness transitions;
- continuation planning and successor coordinator cards;
- board-health checks and stalled-work detection;
- coordinator-only decisions for security, schema ownership, production, and runners;
- economics, model, latency, retry, and Jev telemetry capture.

### 2. Card lifecycle and dispatch reliability

- card intake and prerequisite inspection;
- dispatch preflight for accepted integration ancestry and terminal accepted parents;
- stale-base, deleted-worktree, and worktree-only commit detection;
- overlapping-file and ownership-conflict detection;
- implementation, review, integration, and verification state transitions;
- failure classification and root-cause recovery;
- card recreation rules that preserve history and link the recovery to the failed card;
- prevention of blocked cards whose prerequisites are already satisfied.

### 3. Worker execution and handoff

- profile-specific card reading and scope confirmation;
- source inspection before edits and no invented APIs/schema;
- strict file-scope discipline and stop/escalate behavior;
- test-first or regression-first behavior appropriate to the task;
- authoritative commit and changed-file reporting;
- handoff evidence that distinguishes worktree state, commit, review, integration, and verified delivery;
- explicit reporting of blockers, assumptions, retries, and residual risk.

### 4. Independent review and acceptance

- reviewer-only review procedure with findings first and severity ordering;
- acceptance-criteria and scope verification;
- security, regression, compatibility, and test-gap checks;
- independent review of recovered work;
- rejection and rework routing without self-approval;
- final delivery gate requiring source, diff, tests, review, and integration evidence.

### 5. Backend and Go engineering

- Go package and module orientation;
- contracts, adapters, boundaries, and schema ownership;
- test organization and focused regression coverage;
- error handling, concurrency, persistence, and integration conventions found in the repository;
- backend card decomposition and review criteria;
- commands and verification derived from the actual `go.mod`, scripts, and tests.

### 6. Frontend and React/TypeScript engineering

- frontend source and package orientation if present;
- component boundaries, state/data flow, and API integration;
- localization boundaries and regression coverage;
- frontend test/build/lint procedures from the repository;
- separation of functional frontend work from visual/fixture work;
- responsive and accessibility checks where applicable.

### 7. Adapters, integrations, and infrastructure

- PolarIS or other adapter boundaries discovered in source;
- Redis or external-service boundaries and test doubles;
- configuration and environment handling without exposing secrets;
- integration-test strategy and external dependency isolation;
- production-readiness review remaining coordinator-owned;
- runner and gateway interactions treated as explicit infrastructure work.

### 8. Tests, fixtures, and regression recovery

- test discovery and selection by changed surface;
- RED-GREEN-REFACTOR workflow where appropriate;
- synthetic versus production-like fixture boundaries;
- localization, contract, adapter, and integration regression patterns;
- flaky/failing test diagnosis and evidence preservation;
- full-suite escalation criteria;
- no claiming a pass from a partial or unrelated test command.

### 9. Evidence, documentation, and preservation

- evidence-document creation tied to exact source and test results;
- preservation-oriented change records and historical scope boundaries;
- counts and claims reconciled programmatically;
- handoff and release-note conventions;
- audit trail for card, commit, review, integration, and verification identifiers.

### 10. Visual and product-quality work

- visual profile scope and fixture ownership;
- inspect existing UI conventions before changing presentation;
- visual regression or screenshot evidence where the project supports it;
- accessibility and responsive checks;
- isolation from backend/contracts and no speculative redesign.

### 11. Cross-cutting safety and operating rules

- A6API model restrictions and profile ownership;
- Jev as an advisory typed judgment backed by supplied evidence;
- secret and production-data boundaries;
- no destructive Git operations without authorization;
- no external writes without read-back verification;
- exact identifier/value preservation;
- concise, evidence-backed reporting;
- explicit stop conditions instead of guessing.

## Full evolution and rollout plan

The next AI should produce and execute a staged program, not just draft prose:

1. **Baseline inventory:** inspect `AGENTS.md`, source tree, tests, scripts, roadmap, board history, profile configuration, and all relevant card outcomes. Produce a capability-to-profile matrix.
2. **Failure atlas:** catalogue every failed/recovered card and recurring implementation/review/dispatch failure across the whole project. Link each prevention rule to evidence.
3. **Architecture design:** define the complete skill set, shared references, profile ownership, project-local versus user-local placement, dependencies, and non-overlap rules.
4. **Task datasets:** create representative evaluation tasks for coordinator, backend, frontend, reviewer, visual, evidence, and card lifecycle behavior. Include success cases, failure recovery, stale-base cases, scope conflicts, and stop-condition cases.
5. **Baseline evaluation:** run the current live-agent configuration against the dataset and record task success, test correctness, scope violations, evidence completeness, unnecessary calls, latency, token cost, retries, and Jev usage.
6. **Skill authoring:** write the complete proposed skills and supporting references/templates/scripts. Keep project rules in `AGENTS.md` and procedural skills focused on repeatable behavior.
7. **Static and structural validation:** validate frontmatter, triggers, references, platform assumptions, paths, size, profile loading, and contradictions with `AGENTS.md`.
8. **Evolved-candidate generation:** use self-evolution only on the PHP-Retro skill targets, not the broad global catalog. Preserve baseline/candidate/metrics for every target and record failed candidates separately.
9. **Candidate review:** compare evolved candidates against the authored baseline, constraints, failure atlas, and holdout tasks. Reject candidates that improve one metric while weakening safety, evidence, scope control, or cost.
10. **Profile staging:** install selected candidates into isolated staging copies of coordinator, backend, frontend, reviewer, and visual profiles. Do not modify all live profiles at once.
11. **Shadow and regression evaluation:** repeat the same tasks, add unseen holdouts, compare against baseline, and inspect qualitative traces for overreach, omissions, and circular instructions.
12. **Selective deployment:** deploy only candidates that meet acceptance gates, record exact source and destination paths, retain backups, and make rollback one operation per skill/profile.
13. **Live monitoring:** track card failure rate, stale dispatch rate, rework rate, review rejection rate, test/evidence defects, completion time, token cost, and user-visible regressions.
14. **Iteration:** revise weak skills, add missing skills only from recurring evidence, and periodically re-run the holdout suite. Do not evolve unrelated global skills just because they are available.

## Program-level acceptance criteria

The program is complete only when:

- every recurring PHP-Retro capability and profile has an explicit skill decision: create, merge, retain in `AGENTS.md`, or intentionally omit;
- all five named profiles have documented skill ownership and loading paths;
- card failures are measured before and after, with recovery and dispatch metrics included;
- representative tasks cover the entire roadmap, not only localization;
- evolved candidates have baseline, metrics, constraints, and holdout evidence;
- live deployment is selective, backed up, reversible, and read back for verification;
- no skill contradicts `AGENTS.md` or coordinator-only authority;
- the improvement is demonstrated by matched baseline-versus-skilled results, not by prose quality or the number of files created;
- the final report clearly separates designed, generated, staged, deployed, rejected, and failed artifacts.

The next AI must not claim that the live agents have reached their full potential until these gates are met. The earlier self-evolution run is useful input, but it was a broad global-catalog run and does not satisfy this PHP-Retro program.

## Recommended deliverables from the next AI

1. A short inventory of the repository's real recurring workflows and ownership boundaries.
2. A proposed skill matrix with columns for skill name, purpose, trigger, owner/profile, placement, dependencies, and verification.
3. A clear decision about project-local versus profile-specific placement.
4. Draft `SKILL.md` files only after the matrix is agreed with the evidence in the repository. If autonomous implementation is authorized, keep the drafts narrowly scoped and validate them.
5. Tests or structural validation appropriate to the chosen skill format.
6. A deployment plan that leaves the user able to review and select skills individually.
7. A report distinguishing drafted files, installed files, and merely proposed files.
8. A card-failure report covering the full project, with evidence-backed categories and proposed prevention rules.
9. A roadmap-wide skill matrix that includes work beyond localization and explains which skills belong to coordinator, backend, frontend, reviewer, or visual profiles.

## Verification checklist

Before claiming completion, verify:

- [ ] `AGENTS.md` was read and its rules are reflected rather than contradicted.
- [ ] Current git branch and status were checked.
- [ ] Existing skill/loading conventions were inspected.
- [ ] No project-specific `SKILL.md` was assumed to exist without checking.
- [ ] Every proposed skill has a concrete recurring PHP-Retro use case.
- [ ] Failed cards were inspected across the project, not inferred from localization alone.
- [ ] Card failure categories are supported by board/history evidence.
- [ ] Proposed card skills cover authoring, dispatch, handoff, recovery, and continuation only where each is needed.
- [ ] The roadmap review includes backend, frontend, contracts/adapters, tests, evidence, integration, and infrastructure where present.
- [ ] Profile ownership is justified for each profile-specific skill.
- [ ] No unrelated global skills such as Apple/media skills are included merely because they exist globally.
- [ ] Candidate/generated skills are not described as deployed.
- [ ] Any created file has a precise path and validation evidence.
- [ ] The final report lists what changed, what remains proposals, and what was not touched.

## Scope stop conditions

Stop and report rather than guessing if:

- the repository has no supported project-local skill loading mechanism;
- profile skill loading behavior cannot be established from configuration/source;
- a proposed skill would conflict with `AGENTS.md`;
- required verification commands or board APIs are unavailable;
- deployment would require changing live profile skills without an explicit selection gate.

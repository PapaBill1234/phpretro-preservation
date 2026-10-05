# Proposal: approval stability for planning-only candidates

**Status: adopted as Option A (owner decision, 2026-10-04) and recorded in `DECISIONS.md`. Committed here as the proposal's rationale and measured evidence; the body below is the text as raised, and the "Outcome" section at the end records what was decided. The "What the owner needs to decide" questions are answered there.**

Raised by the owner on 2026-10-04 after the F18-F30 scope approval cycle.

## Problem

A planning-only, single-document candidate had to be re-reviewed and re-approved because `main` advanced underneath it. The content never changed.

Evidence from the F18-F30 cycle:

| Candidate SHA | What happened | Approval |
|---|---|---|
| `523dcdd` | original proposal | reviewed, superseded |
| `61f4036` | rebuilt on a later `main` | reviewer ACCEPTED (`t_59399fdd`), approver APPROVE (`t_309369cf`) |
| `3f688f8` | rebuilt again on `7c14cb3` | reviewer ACCEPTED (`t_b14749f9`), approver APPROVE (`t_ccd5229d`) |

Across all three candidates the proposal content was byte-identical: 13 table rows and all 20 cited source hashes unchanged. Only the base moved. Every rebuild invalidated the prior review, the prior CI run, **and** the prior approval, because each was bound to a commit SHA.

Measured cost of the re-approval alone, from the A6API profile telemetry:

```
approver  t_309369cf   18 calls   1,443,487 tokens   9m
approver  t_ccd5229d   15 calls   1,480,554 tokens  10m
                      ------------------------------------
                      re-approval of identical content: ~1.48M tokens
```

Total across the seven cards in this chain from 19:00 UTC: **9,453,363 tokens**, all `gpt-6.1-sol`, of which roughly 2.9M was the two approver decisions on the same content.

The rule that produced this is correct in intent — a changed SHA genuinely can invalidate an approval — but it binds to the wrong thing. A commit SHA changes for reasons that have nothing to do with the approved content.

## Option A — bind approval to content, not to the commit

**Mechanism.** The approver's verdict binds to a *content digest* instead of a commit SHA. The digest is computed over the candidate's full changed path set relative to its merge base:

```
digest = sha256( for each changed path, sorted by path:
                   path + "\0" + blob_sha256(path) + "\0" + mode )
```

The verdict records both the digest and the commit SHA. At merge time the digest is recomputed and compared.

- **Digest unchanged** (pure rebase, no path added or removed, no blob altered) → the approval carries forward. A mechanical rebase-verification card replaces full re-review and re-approval: ancestry from the new base, blob equality for every path, path-set equality, `git diff --check`, and required CI on the new head.
- **Digest changed** (any blob, any path, any mode) → the approval is invalidated exactly as today: fresh exact-target independent review, green required CI on the new head, and a fresh approver decision.

**Who computes it.** The approver must recompute the digest itself at decision time from the repository, never accept a digest asserted by the coordinator or by a card. That keeps the existing independence property intact.

**Scope.** Start with planning-only and documentation-only candidates where every changed path is prose. Do not extend it to code until the digest has been exercised and the interaction between a rebase and the approved content is understood — a base change can be semantically meaningful even when the candidate's own bytes are identical (for example, a proposal that cites line numbers in a file the base modified).

**What it does not fix.** A genuinely edited proposal still needs a full cycle. A rebase that pulls in a base change touching a cited file still needs a human-meaningful re-check, which the digest cannot see. So the rule should not be stated as "rebases are free" but as "a rebase that leaves every approved byte and path identical does not invalidate the approval".

## Option B — freeze `main` while an approval is in flight

**Mechanism.** While any card sits in the review or approver lane, no other PR merges. Enforced as a coordinator rule, or mechanically as a board-level claim.

**Cost.** It serializes the whole project behind the slowest gate. In this cycle, PR32 and PR33 landed before the approval and caused the staleness — Option B would have blocked them, which is the point, but it also means an unrelated documentation fix waits on a scope decision.

**What it does not fix.** It does not help when `main` legitimately must advance (a security fix, a broken CI repair). It converts a rework problem into a throughput problem.

A narrow version of this is already good practice and was applied here: while PR31's approval was in flight the operator deliberately held PR34, precisely so `main` would not move and invalidate `3f688f8`. That worked, but it worked because a human tracked it. Making it a rule is Option B.

## Recommendation

**Option A as the primary rule, scoped to planning-only and documentation-only candidates, with the narrow form of Option B as a backstop.**

Rationale:

- A addresses the actual failure — SHA-binding, not concurrency. The content was identical across all three candidates; the digest would have been identical too.
- The digest is cheap to compute and strictly stronger than a re-read for the question "did the rebase alter the approved bytes?", because it is exact where a re-review is probabilistic.
- Scoping to prose keeps the semantic-rebase risk out of scope until it is understood.
- The narrow Option B (do not merge unrelated PRs while a delivery is in the review or approver lane) is worth codifying regardless, because it is the reason `3f688f8` survived long enough to be approved.

Estimated saving on this cycle alone: ~1.48M tokens for the re-approval, plus ~1.2M for the second reviewer card, plus the coordinator rebuild passes.

## What the owner needs to decide

1. Option A, Option B, both, or neither.
2. If Option A: whether the mechanical rebase-verification may replace *both* the re-review and the re-approval, or only the re-approval while a cheap re-review still runs.
3. If Option A: whether it is scoped to prose-only candidates initially, as recommended, or extended to code.
4. Where the rule is recorded — `AGENTS.md`, `DECISIONS.md`, and the `phpretro-scope-approval` skill — and whether it needs its own reviewed PR.

## Not done

Nothing in this document has been implemented, committed, or pushed. No board card exists for it. The current SHA-bound rule remains in force exactly as written.

## Outcome (recorded when this proposal was committed)

Option A was adopted by the owner on 2026-10-04 and is recorded in `DECISIONS.md` under "approval stability, Option A". As decided:

- Approval binds to a content digest over the candidate's full changed path set rather than to the commit SHA.
- A pure rebase whose diff is byte-identical may skip re-review and re-approval.
- The digest comparison runs in CI or on the `reviewer` profile and never on the `coordinator`.
- There is no standing freeze on `main`, so the narrow form of Option B was not adopted as a rule.
- The rule applies to prose-only and documentation-only candidates and is not extended to code yet.

The "Not done" paragraph above describes the document's state when it was raised, not its state now: this file is the committed record of the proposal.

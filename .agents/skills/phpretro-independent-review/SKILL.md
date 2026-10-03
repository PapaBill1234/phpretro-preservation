---
name: phpretro-independent-review
description: Independently review PHP-Retro candidate commits.
version: 0.1.0
author: Karim, Hermes Agent
license: GPL-3.0-only
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [phpretro, reviewer, evidence, acceptance]
---

# PHP-Retro independent review

Review an exact, reachable candidate independently of the workers who produced it. `AGENTS.md` defines reviewer independence and coordinator final authority. Lead the review with actionable findings ordered by severity.

## When to use

- A `reviewer` card names an integrated candidate SHA, accepted base, worker parents, and acceptance criteria.
- A recovered candidate needs fresh review after scope, ancestry, or evidence correction.

## Do not use for

- Implementing the candidate, approving one's own implementation, or substituting a base-only checkout for the target.
- Granting schema, security, production, runner, or merge authority through a review verdict.

## Procedure

1. Call `kanban_show` on the review card, its implementation/integration parents, and any prior RETRY card. Read `AGENTS.md` and the exact acceptance criteria. Check: the candidate SHA, accepted base, allowed paths, parent results, and prior findings are explicit; a parent marked done with a RETRY result is not accepted.
2. With `terminal`, run `git rev-parse HEAD`, `git cat-file -e <candidate>^{commit}`, `git merge-base --is-ancestor <accepted-base> <candidate>`, and `git diff --name-only <accepted-base>..<candidate>` using actual SHAs. Check: checkout HEAD equals the named candidate, ancestry exits zero, and each changed path is authorized. If the checkout is base-only or stale, use `kanban_block` with the exact mismatch and request a new exact-target review card; do not review unrelated files.
3. Independently inspect the changed source and tests with `read_file`/`search_files`. Check contract behavior, negative cases, security/compatibility boundaries, ownership, and scope against source evidence. Check: each finding points to an exact file/line or missing test and states the failing criterion; no imagined production fact is accepted.
4. Rerun the relevant pinned checks on this candidate: Go `go test ./...`, `go test -race ./...` where relevant, `go vet ./...`, `gofmt` check, and/or frontend `npm ci --include=dev --ignore-scripts`, `npm run typecheck`, `npm test`, `npm run build`; run `git diff --check`. Check: each result names toolchain, command, exit, and actual count; unavailable or partial checks remain unverified.
5. Compare evidence documents with source, candidate SHA/base, changed paths, executed commands, and test counts. Check: every acceptance claim is supported by this candidate. A green suite cannot waive an unauthorized production-source edit or stale evidence.
6. Report findings first, ordered by severity, then verification and verdict: ACCEPTED only if all required gates pass; RETRY with specific corrections for a defect; BLOCKED for a missing target/prerequisite/toolchain. Use the native review lifecycle (`kanban_request_changes` only when the current card is in its review column; otherwise `kanban_complete` with explicit verdict) without modifying implementation files. Check: the coordinator can act on exact evidence and remains the final verifier.

## Pitfalls

- Worker completion and even an integrated commit do not prove review acceptance.
- A corrected candidate requires a fresh independent review; earlier green results may refer to another SHA.
- F13/F14 failures included stale test counts, wrong review HEAD, and out-of-scope source despite passing tests.

## Verification

Read back the board verdict and its target SHA with `kanban_show`. Confirm the review names the exact diff, test matrix, evidence discrepancies, and any residual UNKNOWNs; do not claim delivery to `main` from reviewer acceptance alone.

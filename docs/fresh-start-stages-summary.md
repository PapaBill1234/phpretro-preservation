# Fresh-start stages summary

Status: Stages 1–5 have deliverables. No rewrite repository has been created and no implementation work is authorized by this sequence.

## Stage 1 — Reconciliation

Established the authority split and scope:

- Original `Quackster/PHPRetro` supplies behavior and routes.
- PHPRetro-PDO supplies security ideas only.
- PolarIS owns hotel storage.
- Pixel63 is isolated and optional.
- Holograph is dropped.
- The first release starts with account/session, profile read, one content read, then audited writes and security slices.

Details: [`fresh-start-reconciliation.md`](fresh-start-reconciliation.md).

## Stage 2 — PolarIS schema verification

Checked the first-release mappings against `CleanDB.sql`. Proven `users` account/profile/session fields and the `hotelview_news` row shape were recorded. Fields not proven for the required behavior remain `UNKNOWN`; no columns were guessed.

Handoff: [`fresh-start-reconciliation.md`](fresh-start-reconciliation.md), section “Stage 2 handoff”.

## Stage 3 — Original PHPRetro golden capture

Ran the original PHPRetro in disposable Docker with synthetic data and captured public, login, failed login, successful login, authenticated profile, authenticated article, cookies, redirects, hashes, and logout. The installer/helper root causes were repaired only in the disposable setup. The host port remained unverified; internal container capture succeeded.

Evidence: [`ai-run-state.md`](ai-run-state.md), section “Stage 3 PHPRetro preservation capture”.

## Stage 4 — Fresh-start location

Compared a branch in the current repository with a new repository. The selected location is a **new repository**, because the rewrite should have an independent history and boundary from the existing implementation. No repository was created.

Proposal: [`fresh-start-stage4-location-proposal.md`](fresh-start-stage4-location-proposal.md).

Open setup details: repository name/owner, visibility, access controls, and approved evidence to transfer.

## Stage 5 — License and asset provenance draft

Drafted GPL-3.0/non-commercial README wording and a per-file asset provenance table containing source, creator/rights holder, retrieval date, SHA-256, license/terms, and attribution notes. The draft has not been applied to `README.md`, a license file, or an asset directory.

Draft: [`fresh-start-stage5-license-provenance-draft.md`](fresh-start-stage5-license-provenance-draft.md).

## What comes next

Draft the actual rewrite plan from this evidence. Before repository setup or implementation, decide the repository setup details and backend/frontend architecture. No C++ or Go implementation was started by these five stages.

# Readiness evidence

Updated 2026-10-01.

| Area | Evidence | Status |
| --- | --- | --- |
| Repository | `origin` points to `PapaBill1234/phpretro-preservation`; `main` and `integration` exist; current work is on `integration`. | Verified locally |
| Jev | Local Codex config exposes `jev_judge` and `jev_gate`; global `PreToolUse` invokes `codex-jev ... hook gate`. | Verified locally; live hook result still requires a normal tool session |
| Cost monitoring | A6API rates, JSONL collector, Tampermonkey collector, PowerShell collector, summaries, backups, and fixtures are present. | Verified locally |
| Monitoring tests | Node userscript test passes; Windows PowerShell collector test passes. | Verified locally |
| Go baseline | `go.mod`, `.go-version`, dependency-free package, and baseline test are present. | Added; local execution blocked because Go is not installed |
| Security CI | Workflow run `36941954680` passed on commit `8ad7480`; formatting, tests, race tests, module evidence, pinned `govulncheck` 1.1.4, and license inventory all passed. | Verified on GitHub |
| Original evidence | Recovered stage directories and fresh-start outputs exist in the recovery bundle and sibling scope-guard checkout. | Available; authoritative input approval pending |
| Branch policy | Public GitHub API confirms `main` requires one pull-request review and the `foundation` status check, enforces administrators, resolves conversations, and blocks force-pushes/deletions. | Verified on GitHub |

Raw A6API archives and backups are deliberately ignored by Git because they contain request metadata. The checked-in fixtures and collectors are sufficient to reproduce offline validation; live exports remain local evidence.

Public GitHub API verification on 2026-10-01 found: the repository is public, unarchived, and defaults to `main`; both `main` and `integration` are present; `main` is protected as recorded above; and the security workflow is active with a successful run on `integration`.

Current planning confidence: approximately 94%. The remaining uncertainty is concentrated in the first clean original-source/golden-runtime rerun and the first measured delegation comparison; those require the supervised work units themselves.

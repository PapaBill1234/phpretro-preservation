# Readiness evidence

Updated 2026-10-01.

| Area | Evidence | Status |
| --- | --- | --- |
| Repository | `origin` points to `PapaBill1234/phpretro-preservation`; `main` and `integration` exist; current work is on `integration`. | Verified locally |
| Jev | Local Codex config exposes `jev_judge` and `jev_gate`; global `PreToolUse` invokes `codex-jev ... hook gate`. | Verified locally; live hook result still requires a normal tool session |
| Cost monitoring | A6API rates, JSONL collector, Tampermonkey collector, PowerShell collector, summaries, backups, and fixtures are present. | Verified locally |
| Monitoring tests | Node userscript test passes; Windows PowerShell collector test passes. | Verified locally |
| Go baseline | `go.mod`, `.go-version`, dependency-free package, and baseline test are present. | Added; local execution blocked because Go is not installed |
| Security CI | Workflow runs formatting, tests, race tests, module evidence, `govulncheck`, and uploads evidence. | Added; CI execution pending |
| Original evidence | Recovered stage directories and fresh-start outputs exist in the recovery bundle and sibling scope-guard checkout. | Available; authoritative input approval pending |
| Branch policy | Branch names are visible locally; protection/ruleset settings were not verified through GitHub CLI. | External verification pending |

Raw A6API archives and backups are deliberately ignored by Git because they contain request metadata. The checked-in fixtures and collectors are sufficient to reproduce offline validation; live exports remain local evidence.

Public GitHub API verification on 2026-10-01 found: the repository is public, unarchived, and defaults to `main`; both `main` and `integration` are present but currently report `protected: false`; the remote currently exposes zero Actions workflows because the new local workflow has not been pushed. These are readiness gaps, not assumptions.

Current planning confidence: approximately 88%. The remaining uncertainty is concentrated in external GitHub controls, CI execution, Go toolchain availability, original-source/golden-runtime verification, approved caps, and the first measured delegation comparison.

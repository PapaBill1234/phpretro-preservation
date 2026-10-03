# PHP-Retro Hermes skill deployment — 2026-10-03 UTC

## Source and installation

The eight canonical source files are `.agents/skills/phpretro-*/SKILL.md` on `codex/phpretro-skills`. The exact skill-source commit is `c8379b5e1ef8ebaac80b4ed1a08cdcd0b2d57ff2`, based on `origin/main` commit `031a336088a784c7773958768ec872da9ea7d08a`. Installation read each `SKILL.md` from the committed Git blob, not from an uncommitted working tree.

| Hermes profile | Installed skills |
| --- | --- |
| coordinator | `phpretro-roadmap-cards`, `phpretro-dispatch-recovery`, `phpretro-integration-acceptance` |
| backend | `phpretro-worker-handoff`, `phpretro-go-contracts` |
| frontend | `phpretro-worker-handoff`, `phpretro-react-boundary` |
| reviewer | `phpretro-independent-review` |
| visual | `phpretro-worker-handoff`, `phpretro-visual-fixtures` |

Each profile copy is at `HERMES_HOME/profiles/<profile>/skills/phpretro/<skill>/SKILL.md`. The manifest and per-skill rollback scripts are at `HERMES_HOME/backups/phpretro-skills/20261003T215849Z-c8379b5/`. The manifest records exact destination, SHA-256, previous-file state, and source commit. No destination file existed before this installation. A rollback is one profile/skill invocation of `rollback.py`, followed by a fresh loader check.

## Checks performed

- All eight YAML frontmatters parsed; folder names matched skill names; descriptions met the length limit; required sections and numbered-step checks were present. `git diff --check` passed.
- The deployment verifier compared all ten installed files byte-for-byte with their committed Git blobs and checked the recorded SHA-256 values. It marked the manifest `installed` only after all ten passed.
- Fresh Hermes CLI processes using the live `HERMES_HOME` listed the expected PHP-Retro skills as **enabled local** skills for each of the five profiles. Pre-installation inventory showed no PHP-Retro profile skills.
- The existing broad local skill catalog was left in place. No project-trust configuration or Kanban board state was changed by this deployment.

## Remaining evaluation

An isolated alternate `HERMES_HOME` loader smoke test could not complete because Hermes attempted a source update and received HTTP 503. Live-profile fresh-process loading passed. The frozen card cases, holdouts, self-evolution runs, and matched before/after cost and correctness measurements described in the [program](phpretro-skill-program-design.md) have not been run. Do not claim that the skills have reduced failures or cost until those comparisons are measured.

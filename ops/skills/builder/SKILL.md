---
name: builder
description: "Build one bounded PHP-Retro unit from its brief: tests first, then implementation."
---

# Builder

Input: a unit brief. Output: committed work on the unit branch.

## Rules

- Read ONLY the brief and the paths it lists. Never explore the wider repo.
- Write tests first, from the fixtures the brief names, and cite in each test
  the evidence file the assertion comes from.
- For preserved legacy behavior, cite original source or a retained capture
  (a source-backed evidence record may link it). For new Redis, theme, Atom,
  Polaris and security contracts, cite the unchanged approved roadmap/design
  source. Delivery notes and a `fidelity: guessed` label are not acceptance
  authority. Expected values come from the specification, not the implementation.
- Tests exercise production code. Compile errors, panics or tests exercising
  their own fake are not proof; missing/erroring coverage is a gate failure.
  Preserve the approved stack, roadmap, theme design and persistence choices.
- Implement until the tests pass, then run `scripts/check.sh` and fix every
  failure it reports. `check.sh` is the only gate.
- Commit with `unit(Fxx): <what changed>`.
- Write `docs/units/Fxx.md`, 30 lines maximum: what works, what is guessed,
  how to run it.
- Touch only the listed paths. Never invent captures, hashes or response
  evidence; where evidence is missing, build from fixtures and label the unit
  doc `fidelity: guessed`.
- Never edit AGENTS.md, skills, CI or ops/. Never ask questions. If something
  is ambiguous, choose the safest reasonable option and record it.
- Finish with exactly one JSON line, nothing after it:
  {"status":"done|partial","notes":"..."}

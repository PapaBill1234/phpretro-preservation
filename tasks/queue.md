# Supervised work queue

Only one unit is ready. The batch scope is `docs/evidence/**` and `tasks/F1.md` for F1; no implementation or production scope is approved.

| ID | Status | Unit | Exact scope | Reason |
| --- | --- | --- | --- | --- |
| F0 | accepted | Repository and CI baseline | Historical F0 foundation files | CI baseline passed and was accepted before this queue. |
| F1 | accepted | PolarIS password-scheme evidence | `docs/evidence/**`, `tasks/F1.md` | Pinned original source is now verified; PolarIS row format remains an explicit F2 evidence input. |
| F2 | ready | Account/session contract | `internal/account/**`, `internal/session/**`, `tests/**`, `docs/evidence/**` via a new scope brief | F1 source evidence is accepted; F2 must verify PolarIS rows before choosing a verifier. |
| F3 | blocked | Profile read | No files approved | Requires accepted F2 contract and schema evidence. |
| F4 | blocked | Golden harness | No files approved | Requires F1-F3 evidence and implementation contracts. |
| F5 | blocked | Content read | No files approved | Requires prior accepted foundation units. |
| F6+ | deferred | Later features and production gates | No files approved | Later owner decisions; deferred gates remain closed. |

Every unit brief must state its base SHA, exact allowed paths, evidence, tests, acceptance criteria, stop conditions, and token cap. Any security, schema, production, or runner decision stays with Sol.

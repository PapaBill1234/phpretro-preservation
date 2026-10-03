# Current AI run state

This is the active state for the Go PHPRetro preservation rewrite. The old C++/Drogon plan-v4 continuation note is archived at [`docs/archive/cpp-modular-cms-history.md`](archive/cpp-modular-cms-history.md) and is not permission to resume. Work is dispatched through the durable Hermes Kanban board `phpretro-preservation`.

- **active unit:** F8 localization contract, with bounded frontend/backend/visual implementation cards and an independent review card
- **status:** F0-F7 foundation and React/Redis/PolarIS boundaries are merged; F8 is the next synthetic-only implementation slice
- **allowed scope:** only active Kanban cards and their exact paths; worktrees are isolated and the coordinator integrates reviewed results
- **blocked:** production registration, payments, emulator writes, client handoff, staff operations, Pixel63, Atom, nginx/metrics/fuzzing, and SWF remain closed
- **deferred:** production registration, payments, emulator writes, client handoff, staff operations, Pixel63, Atom, nginx/metrics/fuzzing, and SWF; React is mandatory for all themes, Redis is required for approved cache/session-support slices, and localization/housekeeping CMS work is staged through bounded briefs
- **agents:** `coordinator`/Sol owns discovery and acceptance; `backend`/Luna owns Go contracts; `frontend`/Luna owns React/TypeScript; `visual`/Luna owns presentation fixtures; `reviewer`/Sol independently verifies cards
- **supervision:** Hermes Nerve supervises active Kanban runs and may consult Jev through the configured Reflex path when its ROI/cooldown policy allows; Jev never grants permission
- **stop conditions:** guessed schema/hash scheme, missing source evidence, real user data, secret detection, payment/quota/auth failure, or a second failed attempt
- **last boundary:** F7/PolarIS/React/Redis work is on `main` at `0fd95a4706da324c9a6a2390853e6d998b7a980e`; local F8 changes are present but uncommitted and must be treated as the current working baseline

The coordinator may continue bounded Kanban cards autonomously. Every coordinator completion must leave successor work queued or record a documented stop reason; an empty board is not a successful continuation state. Before dispatch, every card must point at the accepted integration SHA, never a worktree-only or stale base. Every completion still requires source-backed review, tests, scope verification, and explicit external-state verification before merge.

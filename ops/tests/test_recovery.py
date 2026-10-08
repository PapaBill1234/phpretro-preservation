"""F38 recovery loop: a unit-scoped recovery failure must never abort the cycle.

These tests reproduce the 2026-10-08 F38 failure: a local branch diverged from
its remote, a runtime ``pr: 0`` that hid an already-open PR #66, and a rejected
non-fast-forward push raised from ``push_and_open_pr`` that escaped ``cycle()``
and crash-looped the systemd unit every two minutes.

GitHub, the providers and the workers are mocked here. No real branch, PR or
pipeline state is read or written: ``harness`` already forces PHPRETRO_OPS,
PHPRETRO_WORK and HOME into a throwaway temp tree before ``orchestrator`` is
imported.
"""

from __future__ import annotations

import unittest
from unittest import mock

from harness import tmpdir

import orchestrator as o


def _state() -> dict:
    return {"events": [], "day": "2026-10-08", "merged_today": 0,
            "tokens_today": 1000000}


class ScriptedGit:
    """Scripted ``o.git`` / ``o.git_out`` for the recovery paths.

    ``relations`` maps a branch name to how its worktree relates to the remote:
    ``ahead`` (remote head is an ancestor of HEAD), ``behind`` (HEAD is an
    ancestor of the remote), ``diverged`` (neither) or ``current`` (identical).
    """

    def __init__(self, relations: dict):
        self.relations = relations
        self.git_calls: list = []
        self.git_out_calls: list = []
        self.head = "a" * 40
        self.remote = "b" * 40

    def _branch(self, args) -> str:
        for arg in args:
            if isinstance(arg, str) and "unit/" in arg:
                return arg.split("..")[-1].split("refs/remotes/origin/")[-1]
        return ""

    def git(self, *args, cwd=None, timeout=None):
        self.git_calls.append(args)
        branch = self._branch(args)
        relation = self.relations.get(branch)
        if args[:2] == ("merge-base", "--is-ancestor") and relation:
            first, second = args[2], args[3]
            remote_ref = f"refs/remotes/origin/{branch}"
            if relation == "ahead":
                return (0, "") if first == remote_ref else (1, "")
            if relation == "behind":
                return (0, "") if second == remote_ref else (1, "")
            if relation == "current":
                return (0, "")
            return (1, "")                      # diverged
        return (0, "")

    def git_out(self, *args, cwd=None, timeout=None):
        self.git_out_calls.append(args)
        if args[:2] == ("rev-list", "--count"):
            return "1" if self._branch(args) else ""
        if args[:2] == ("rev-parse", "--abbrev-ref"):
            return self._branch(args) or "unit/F38"
        if args[:2] == ("rev-parse", "HEAD"):
            return self.head
        if args[:1] == ("rev-parse",) and str(args[1]).startswith("refs/remotes"):
            return self.remote
        return ""


class DivergedHistoryTest(unittest.TestCase):
    """Local 4 commits / remote 1: publishing would need a force-push."""

    def test_diverged_worktree_raises_a_unit_conflict(self):
        unit = {"id": "F38", "status": "todo", "attempts": 2, "tokens": 554087,
                "pr": 0}
        git = ScriptedGit({"unit/F38": "diverged"})
        pushed = mock.Mock(side_effect=AssertionError("must not push"))
        with mock.patch.object(o, "git", git.git), \
             mock.patch.object(o, "git_out", git.git_out), \
             mock.patch.object(o, "attach_worktree", lambda u: tmpdir("f38-")), \
             mock.patch.object(o, "adopt_branch_unit", lambda u, s: False), \
             mock.patch.object(o, "push_and_open_pr", pushed):
            with self.assertRaises(o.RecoveryConflict) as ctx:
                o.recover_branch(unit, {}, _state())
        self.assertIn("diverged", str(ctx.exception))
        pushed.assert_not_called()
        # Nothing was recorded as recovered and no counter moved.
        self.assertEqual(unit["attempts"], 2)
        self.assertEqual(unit["tokens"], 554087)
        self.assertNotEqual(unit.get("status"), "queued")


class ExistingPrTest(unittest.TestCase):
    """Runtime ``pr: 0`` must not hide an existing PR #66."""

    def test_zero_runtime_pr_reuses_the_open_pr(self):
        unit = {"id": "F38", "status": "todo", "attempts": 2, "tokens": 554087,
                "pr": 0}
        state = _state()
        history: dict = {}
        git = ScriptedGit({"unit/F38": "ahead"})
        pushed = mock.Mock(side_effect=AssertionError("must not open a duplicate PR"))
        with mock.patch.object(o, "git", git.git), \
             mock.patch.object(o, "git_out", git.git_out), \
             mock.patch.object(o, "attach_worktree", lambda u: tmpdir("f38-")), \
             mock.patch.object(o, "adopt_branch_unit", lambda u, s: False), \
             mock.patch.object(o, "run_check", lambda wt: (0, "ok")), \
             mock.patch.object(o, "find_existing_pr", lambda b: 66), \
             mock.patch.object(o, "push_and_open_pr", pushed), \
             mock.patch.object(o, "record_history",
                               lambda u, outcome: history.__setitem__(u["id"], outcome)):
            self.assertTrue(o.recover_branch(unit, {}, state))
        self.assertEqual(unit["pr"], 66)
        self.assertEqual(unit["status"], "queued")
        self.assertEqual(history["F38"], "recovered")
        pushed.assert_not_called()

    def test_push_and_open_pr_reuses_before_pushing(self):
        unit = {"id": "F38", "status": "todo", "attempts": 1, "tokens": 1}
        git = ScriptedGit({})
        with mock.patch.object(o, "git", git.git), \
             mock.patch.object(o, "find_existing_pr", lambda b: 66), \
             mock.patch.object(o, "sh",
                               mock.Mock(side_effect=AssertionError("no gh call"))):
            self.assertEqual(o.push_and_open_pr(unit, tmpdir("f38-"), "ok", _state()), 66)
        self.assertEqual(git.git_calls, [])


class RecoverUnitsTest(unittest.TestCase):
    """One unit's conflict must not stop an unrelated unit."""

    def test_rejected_push_parks_one_unit_and_lets_another_proceed(self):
        roadmap = {
            "F38": {"id": "F38", "status": "todo", "attempts": 2,
                    "tokens": 554087, "pr": 0},
            "F40": {"id": "F40", "status": "todo", "attempts": 1,
                    "tokens": 100, "pr": 0},
        }
        state = _state()
        history: dict = {}
        git = ScriptedGit({"unit/F38": "diverged"})
        real_recover = o.recover_branch

        def recover(unit, hist, st):
            if unit["id"] == "F40":
                unit["pr"], unit["status"] = 41, "queued"
                return True
            return real_recover(unit, hist, st)

        with mock.patch.object(o, "git", git.git), \
             mock.patch.object(o, "git_out", git.git_out), \
             mock.patch.object(o, "recover_branch", recover), \
             mock.patch.object(o, "attach_worktree", lambda u: tmpdir("f38-")), \
             mock.patch.object(o, "adopt_branch_unit", lambda u, s: False), \
             mock.patch.object(o, "record_history",
                               lambda u, outcome: history.__setitem__(
                                   u["id"], {"outcome": outcome})), \
             mock.patch.object(o, "event",
                               lambda s, m: s["events"].append(m)), \
             mock.patch.object(o, "telemetry_event", lambda *a, **k: None):
            o.recover_units(roadmap, {}, state)

        # F38 is parked with its reason; its counters are untouched.
        self.assertEqual(roadmap["F38"]["status"], "parked")
        self.assertIn("recovery conflict", roadmap["F38"]["reason"])
        self.assertEqual(roadmap["F38"]["attempts"], 2)
        self.assertEqual(roadmap["F38"]["tokens"], 554087)
        self.assertEqual(history["F38"]["outcome"], "recovery-conflict")
        # The unrelated unit still proceeded.
        self.assertEqual(roadmap["F40"]["status"], "queued")
        self.assertEqual(roadmap["F40"]["pr"], 41)
        # No false recovery-success event was emitted for the failure.
        self.assertFalse([e for e in state["events"] if "recovered" in e])

    def test_unexpected_errors_are_not_swallowed(self):
        roadmap = {"F38": {"id": "F38", "status": "todo", "attempts": 2,
                           "tokens": 1, "pr": 0}}
        with mock.patch.object(o, "recover_branch",
                               mock.Mock(side_effect=ValueError("programming error"))):
            with self.assertRaises(ValueError):
                o.recover_units(roadmap, {}, _state())

    def test_no_change_units_are_never_recovered(self):
        roadmap = {"F38": {"id": "F38", "status": "todo", "attempts": 2,
                           "tokens": 1, "pr": 0}}
        called = mock.Mock()
        with mock.patch.object(o, "recover_branch", called):
            o.recover_units(roadmap, {"F38": {"outcome": "no-change"}}, _state())
        called.assert_not_called()


class DispatchGuardTest(unittest.TestCase):
    """An open PR must be reused, never duplicated by a fresh build."""

    def test_dispatch_queues_a_unit_that_already_has_an_open_pr(self):
        unit = {"id": "F38", "status": "todo", "attempts": 2, "tokens": 1,
                "paths": ["internal/staff"]}
        roadmap = {"F38": unit}
        state = _state()
        build = mock.Mock(side_effect=AssertionError("must not rebuild"))
        with mock.patch.object(o, "paid_allowed", lambda *a, **k: True), \
             mock.patch.object(o, "select_ready", lambda r, s: [unit]), \
             mock.patch.object(o, "find_existing_pr", lambda b: 66), \
             mock.patch.object(o, "start_build", build), \
             mock.patch.object(o, "event", lambda s, m: s["events"].append(m)):
            o.dispatch(roadmap, state)
        build.assert_not_called()
        self.assertEqual(unit["status"], "queued")
        self.assertEqual(unit["pr"], 66)

    def test_adopt_is_skipped_for_a_branch_that_does_not_exist(self):
        unit = {"id": "F38", "status": "todo", "attempts": 0, "pr": 0}
        with mock.patch.object(o, "git", lambda *a, **k: (1, "")), \
             mock.patch.object(o, "sh",
                               mock.Mock(side_effect=AssertionError("no gh call"))):
            self.assertFalse(o.adopt_branch_unit(unit, _state()))


class StopAndCapTest(unittest.TestCase):
    """STOP and the caps still gate the pipeline."""

    def test_stop_halts_the_cycle_before_any_git_or_gh_call(self):
        stop = tmpdir("stop-") / "STOP"
        stop.write_text("")
        with mock.patch.object(o, "STOP_FILE", stop), \
             mock.patch.object(o, "ensure_dirs", lambda: None), \
             mock.patch.object(o, "git",
                               mock.Mock(side_effect=AssertionError("must not run"))), \
             mock.patch.object(o, "sh",
                               mock.Mock(side_effect=AssertionError("must not run"))):
            o.cycle()          # returns without raising
        self.assertTrue(stop.exists())

    def test_merge_cap_stops_dispatch(self):
        roadmap = {"F38": {"id": "F38", "status": "todo", "attempts": 0,
                           "paths": ["internal/staff"]}}
        state = _state()
        state["merged_today"] = 3
        with mock.patch.object(o, "effective_merge_cap", lambda s: 3):
            self.assertEqual(o.select_ready(roadmap, state), [])

    def test_daily_token_cap_stops_dispatch(self):
        roadmap = {"F38": {"id": "F38", "status": "todo", "attempts": 0,
                           "paths": ["internal/staff"]}}
        state = _state()
        state["tokens_today"] = o.DAILY_TOKEN_CAP
        self.assertEqual(o.select_ready(roadmap, state), [])


if __name__ == "__main__":
    unittest.main()

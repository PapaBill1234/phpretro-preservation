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

import contextlib
import json
import os
import unittest
from unittest import mock

from harness import commit, git_repo, head, run, tmpdir

import orchestrator as o


@contextlib.contextmanager
def in_dir(path):
    """Run the block with the process cwd at ``path``.

    ``o.git``/``o.git_out`` default to the process cwd for the calls that do not
    pass one, so a real-Git test has to move the process, not a mock.
    """
    previous = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _state() -> dict:
    return {"events": [], "day": "2026-10-08", "merged_today": 0,
            "tokens_today": 1000000}


class ScriptedGit:
    """Scripted ``o.git`` / ``o.git_out`` for the recovery paths.

    ``relations`` maps a branch name to how its worktree relates to the remote:
    ``ahead`` (remote head is an ancestor of HEAD), ``behind`` (HEAD is an
    ancestor of the remote), ``diverged`` (neither) or ``current`` (identical).
    ``merge_rc`` is what a diverged-history reconciliation merge returns;
    ``dirty`` is what ``status --porcelain`` reports for the worktree.
    """

    def __init__(self, relations: dict, merge_rc: int = 0, dirty: str = "",
                 push_rc: int = 0, merge_conflicts: bool = True):
        self.relations = relations
        self.merge_rc = merge_rc
        self.dirty = dirty
        self.push_rc = push_rc
        self.merge_conflicts = merge_conflicts
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
        if args[:1] == ("push",):
            return (self.push_rc, "rejected" if self.push_rc else "")
        if "merge" in args:
            if "--abort" in args or "--ff-only" in args:
                return (0, "")
            return (self.merge_rc, "CONFLICT" if self.merge_rc else "")
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
        if args[:2] == ("status", "--porcelain"):
            return self.dirty
        if args[:2] == ("diff", "--name-only"):
            return "internal/staff/replay.go" if (self.merge_rc and
                                                  self.merge_conflicts) else ""
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
    """Local 4 commits / remote 1: both histories must survive."""

    def _recover(self, git, unit, pushed):
        with mock.patch.object(o, "git", git.git), \
             mock.patch.object(o, "git_out", git.git_out), \
             mock.patch.object(o, "attach_worktree", lambda u: tmpdir("f38-")), \
             mock.patch.object(o, "adopt_branch_unit", lambda u, s: False), \
             mock.patch.object(o, "run_check", lambda wt: (0, "ok")), \
             mock.patch.object(o, "find_existing_pr", lambda b: 66), \
             mock.patch.object(o, "push_and_open_pr", pushed):
            return o.recover_branch(unit, {}, _state())

    def test_conflicting_merge_is_a_unit_conflict(self):
        unit = {"id": "F38", "status": "todo", "attempts": 2, "tokens": 554087,
                "pr": 0}
        git = ScriptedGit({"unit/F38": "diverged"}, merge_rc=1)
        pushed = mock.Mock(side_effect=AssertionError("must not push"))
        with self.assertRaises(o.RecoveryConflict) as ctx:
            self._recover(git, unit, pushed)
        self.assertIn("both histories preserved", str(ctx.exception))
        pushed.assert_not_called()
        self.assertEqual(unit["attempts"], 2)
        self.assertEqual(unit["tokens"], 554087)
        self.assertNotEqual(unit.get("status"), "queued")

    def test_clean_merge_reconciles_both_histories(self):
        unit = {"id": "F38", "status": "todo", "attempts": 2, "tokens": 554087,
                "pr": 0}
        git = ScriptedGit({"unit/F38": "diverged"}, merge_rc=0)
        pushed = mock.Mock(side_effect=AssertionError("must not push"))
        self.assertTrue(self._recover(git, unit, pushed))
        self.assertEqual(unit["status"], "queued")
        self.assertEqual(unit["pr"], 66)
        self.assertIn("merged", unit["reason"])
        # The reconciliation was an ordinary merge commit, never a force-push.
        self.assertTrue(any("merge" in call for call in git.git_calls))

    def test_a_non_conflict_merge_failure_surfaces(self):
        """A local Git failure is not the unit's fault: it must not be parked."""
        unit = {"id": "F38", "status": "todo", "attempts": 2, "tokens": 1,
                "pr": 0}
        git = ScriptedGit({"unit/F38": "diverged"}, merge_rc=1,
                          merge_conflicts=False)
        pushed = mock.Mock(side_effect=AssertionError("must not push"))
        with self.assertRaises(RuntimeError) as ctx:
            self._recover(git, unit, pushed)
        self.assertNotIsInstance(ctx.exception, o.RecoveryConflict)
        self.assertNotEqual(unit.get("status"), "queued")

    def test_dirty_recovery_checkout_is_preserved_not_pushed(self):
        unit = {"id": "F38", "status": "todo", "attempts": 2, "tokens": 1,
                "pr": 0}
        git = ScriptedGit({"unit/F38": "ahead"}, dirty=" M internal/staff/x.go")
        pushed = mock.Mock(side_effect=AssertionError("must not push"))
        with self.assertRaises(o.RecoveryConflict) as ctx:
            self._recover(git, unit, pushed)
        self.assertIn("unfinished local edits", str(ctx.exception))
        pushed.assert_not_called()


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

    def test_recovery_publishes_the_reconciled_head_before_reusing_the_pr(self):
        unit = {"id": "F38", "status": "todo", "attempts": 2, "tokens": 1, "pr": 0}
        history: dict = {}
        git = ScriptedGit({"unit/F38": "ahead"})
        with mock.patch.object(o, "git", git.git), \
             mock.patch.object(o, "git_out", git.git_out), \
             mock.patch.object(o, "attach_worktree", lambda u: tmpdir("f38-")), \
             mock.patch.object(o, "adopt_branch_unit", lambda u, s: False), \
             mock.patch.object(o, "run_check", lambda wt: (0, "ok")), \
             mock.patch.object(o, "find_existing_pr", lambda b: 66), \
             mock.patch.object(o, "push_and_open_pr",
                               mock.Mock(side_effect=AssertionError("must not open"))), \
             mock.patch.object(o, "record_history",
                               lambda u, outcome: history.__setitem__(u["id"], outcome)):
            self.assertTrue(o.recover_branch(unit, {}, _state()))
        # The ahead worktree was pushed, so the PR's branch holds this head.
        self.assertTrue(any(call[:1] == ("push",) for call in git.git_calls))
        self.assertEqual(unit["pr"], 66)

    def test_recovery_preserves_a_prior_quality_finding(self):
        unit = {"id": "F38", "status": "todo", "attempts": 2, "tokens": 1,
                "pr": 0, "reason": "quality: tests do not exercise the change",
                "feedback": "repair the tests"}
        git = ScriptedGit({"unit/F38": "ahead"})
        with mock.patch.object(o, "git", git.git), \
             mock.patch.object(o, "git_out", git.git_out), \
             mock.patch.object(o, "attach_worktree", lambda u: tmpdir("f38-")), \
             mock.patch.object(o, "adopt_branch_unit", lambda u, s: False), \
             mock.patch.object(o, "run_check", lambda wt: (0, "ok")), \
             mock.patch.object(o, "find_existing_pr", lambda b: 66), \
             mock.patch.object(o, "record_history", lambda u, outcome: None):
            self.assertTrue(o.recover_branch(unit, {}, _state()))
        self.assertIn("tests do not exercise the change", unit["feedback"])
        self.assertIn("repair the tests", unit["feedback"])

    def test_push_and_open_pr_publishes_then_reuses(self):
        unit = {"id": "F38", "status": "todo", "attempts": 1, "tokens": 1}
        git = ScriptedGit({})
        with mock.patch.object(o, "git", git.git), \
             mock.patch.object(o, "find_existing_pr", lambda b: 66), \
             mock.patch.object(o, "sh",
                               mock.Mock(side_effect=AssertionError("no gh call"))):
            self.assertEqual(o.push_and_open_pr(unit, tmpdir("f38-"), "ok", _state()), 66)
        # The branch is published before the existing PR is reused.
        self.assertTrue(any(call[:1] == ("push",) for call in git.git_calls))

    def test_stale_recorded_pr_is_a_unit_conflict(self):
        """A closed or foreign recorded PR must never be queued as recovered."""
        for recorded, open_pr in ((99, 66), (99, 0)):
            with self.subTest(recorded=recorded, open_pr=open_pr):
                unit = {"id": "F38", "status": "todo", "attempts": 2,
                        "tokens": 1, "pr": recorded}
                git = ScriptedGit({"unit/F38": "ahead"})
                pushed = mock.Mock(side_effect=AssertionError("must not push"))
                with mock.patch.object(o, "git", git.git), \
                     mock.patch.object(o, "git_out", git.git_out), \
                     mock.patch.object(o, "attach_worktree",
                                       lambda u: tmpdir("f38-")), \
                     mock.patch.object(o, "adopt_branch_unit", lambda u, s: False), \
                     mock.patch.object(o, "run_check", lambda wt: (0, "ok")), \
                     mock.patch.object(o, "find_existing_pr", lambda b: open_pr), \
                     mock.patch.object(o, "push_and_open_pr", pushed):
                    with self.assertRaises(o.RecoveryConflict):
                        o.recover_branch(unit, {}, _state())
                pushed.assert_not_called()
                self.assertNotEqual(unit.get("status"), "queued")

    def test_pr_lookup_failure_defers_and_is_not_a_unit_failure(self):
        unit = {"id": "F38", "status": "todo", "attempts": 2, "tokens": 1,
                "pr": 0}
        git = ScriptedGit({"unit/F38": "ahead"})

        def unavailable(branch):
            raise o.DeliveryUnavailable("github unavailable")

        with mock.patch.object(o, "git", git.git), \
             mock.patch.object(o, "git_out", git.git_out), \
             mock.patch.object(o, "attach_worktree", lambda u: tmpdir("f38-")), \
             mock.patch.object(o, "adopt_branch_unit", lambda u, s: False), \
             mock.patch.object(o, "run_check", lambda wt: (0, "ok")), \
             mock.patch.object(o, "find_existing_pr", unavailable):
            with self.assertRaises(o.DeliveryUnavailable):
                o.recover_branch(unit, {}, _state())
        self.assertNotEqual(unit.get("status"), "parked")


class GitHubLookupTest(unittest.TestCase):
    """A provider outage must not look like "no PR exists"."""

    def test_lookup_failure_raises_delivery_unavailable(self):
        with mock.patch.object(o, "sh", lambda *a, **k: (1, "HTTP 500")):
            with self.assertRaises(o.DeliveryUnavailable):
                o.find_existing_pr("unit/F38")

    def test_no_pr_returns_zero(self):
        with mock.patch.object(o, "sh", lambda *a, **k: (0, "[]")):
            self.assertEqual(o.find_existing_pr("unit/F38"), 0)

    def test_open_pr_returns_its_number(self):
        payload = json.dumps([{"number": 66, "headRefName": "unit/F38"}])
        with mock.patch.object(o, "sh", lambda *a, **k: (0, payload)):
            self.assertEqual(o.find_existing_pr("unit/F38"), 66)

    def test_open_pr_from_another_branch_is_ignored(self):
        """The lookup re-checks identity; a foreign result is not reused."""
        payload = json.dumps([{"number": 9, "headRefName": "unit/OTHER"}])
        with mock.patch.object(o, "sh", lambda *a, **k: (0, payload)):
            self.assertEqual(o.find_existing_pr("unit/F38"), 0)

    def test_rejected_push_is_a_unit_conflict(self):
        unit = {"id": "F38", "status": "todo", "attempts": 1, "tokens": 1}
        git = ScriptedGit({}, push_rc=1)
        with mock.patch.object(o, "git", git.git), \
             mock.patch.object(o, "find_existing_pr", lambda b: 0):
            with self.assertRaises(o.RecoveryConflict):
                o.push_and_open_pr(unit, tmpdir("f38-"), "ok", _state())

    def test_pr_creation_failure_defers_and_is_not_a_unit_failure(self):
        """gh pr create failing is a provider problem, not a unit conflict."""
        unit = {"id": "F38", "status": "todo", "attempts": 1, "tokens": 1}
        git = ScriptedGit({})
        with mock.patch.object(o, "git", git.git), \
             mock.patch.object(o, "sh",
                               mock.Mock(return_value=(1, "HTTP 500 from the API"))), \
             mock.patch.object(o, "find_existing_pr", lambda b: 0):
            with self.assertRaises(o.DeliveryUnavailable):
                o.push_and_open_pr(unit, tmpdir("f38-"), "ok", _state())


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
        git = ScriptedGit({"unit/F38": "diverged"}, merge_rc=1)
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
             mock.patch.object(o, "run_check", lambda wt: (0, "ok")), \
             mock.patch.object(o, "find_existing_pr", lambda b: 0), \
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

    def test_provider_unavailability_is_not_a_unit_failure(self):
        roadmap = {"F38": {"id": "F38", "status": "todo", "attempts": 2,
                           "tokens": 1, "pr": 0}}
        with mock.patch.object(o, "recover_branch",
                               mock.Mock(side_effect=o.DeliveryUnavailable("gh down"))):
            with self.assertRaises(o.DeliveryUnavailable):
                o.recover_units(roadmap, {}, _state())
        # The unit keeps its state and counters: the outage is not its fault.
        self.assertEqual(roadmap["F38"]["status"], "todo")
        self.assertEqual(roadmap["F38"]["attempts"], 2)
        self.assertEqual(roadmap["F38"]["tokens"], 1)

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
             mock.patch.object(o, "git", lambda *a, **k: (1, "")), \
             mock.patch.object(o, "find_existing_pr", lambda b: 66), \
             mock.patch.object(o, "start_build", build), \
             mock.patch.object(o, "event", lambda s, m: s["events"].append(m)):
            o.dispatch(roadmap, state)
        build.assert_not_called()
        self.assertEqual(unit["status"], "queued")
        self.assertEqual(unit["pr"], 66)

    def test_dispatch_never_rebuilds_a_unit_already_merged_in_git(self):
        """A branch that is already an ancestor of origin/main is a delivery."""
        unit = {"id": "F40", "status": "todo", "attempts": 0, "pr": 0,
                "paths": ["internal/home"]}
        roadmap = {"F40": unit}
        state = _state()
        build = mock.Mock(side_effect=AssertionError("must not rebuild"))
        with mock.patch.object(o, "paid_allowed", lambda *a, **k: True), \
             mock.patch.object(o, "select_ready", lambda r, s: [unit]), \
             mock.patch.object(o, "git", lambda *a, **k: (0, "")), \
             mock.patch.object(o, "adopt_branch_unit", lambda u, s: False), \
             mock.patch.object(o, "start_build", build), \
             mock.patch.object(o, "event", lambda s, m: s["events"].append(m)):
            o.dispatch(roadmap, state)
        build.assert_not_called()
        self.assertEqual(unit["status"], "parked")
        self.assertIn("already merged", unit["reason"])

    def test_adopt_uses_github_even_when_the_branch_is_gone(self):
        """GitHub deletes the head branch on merge; absence is not evidence."""
        unit = {"id": "F40", "status": "todo", "attempts": 0, "pr": 0}
        state = _state()
        payload = json.dumps([{"number": 67, "headRefName": "unit/F40",
                               "mergeCommit": {"oid": "d" * 40}}])

        def sh(cmd, **kw):
            return (0, payload) if cmd[:2] == ["gh", "pr"] else (1, "")

        with mock.patch.object(o, "sh", sh), \
             mock.patch.object(o, "git", lambda *a, **k: (0, "")), \
             mock.patch.object(o, "git_out", lambda *a, **k: "f" * 40), \
             mock.patch.object(o, "_check_main_cached", lambda head: (0, "ok")), \
             mock.patch.object(o, "event", lambda s, m: s["events"].append(m)):
            self.assertTrue(o.adopt_branch_unit(unit, state))
        self.assertEqual(unit["status"], "merged")
        self.assertEqual(unit["pr"], 67)

    def test_adopt_never_accepts_a_pr_from_another_branch(self):
        unit = {"id": "F38", "status": "todo", "attempts": 0, "pr": 0}
        payload = json.dumps([{"number": 9, "headRefName": "unit/OTHER",
                               "mergeCommit": {"oid": "e" * 40}}])
        with mock.patch.object(o, "sh", lambda *a, **k: (0, payload)), \
             mock.patch.object(o, "git", lambda *a, **k: (0, "")), \
             mock.patch.object(o, "git_out", lambda *a, **k: "f" * 40):
            self.assertFalse(o.adopt_branch_unit(unit, _state()))

    def test_adopt_returns_false_without_a_merged_pr(self):
        unit = {"id": "F38", "status": "todo", "attempts": 0, "pr": 0}
        with mock.patch.object(o, "sh", lambda *a, **k: (0, "[]")), \
             mock.patch.object(o, "git", lambda *a, **k: (1, "")), \
             mock.patch.object(o, "git_out", lambda *a, **k: "f" * 40):
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


class RealGitHistoryTest(unittest.TestCase):
    """Diverged histories against REAL Git: both tips must survive the merge."""

    def _seed(self):
        """A repo whose local branch and origin/<branch> have both moved on."""
        repo = git_repo(tmpdir("real-"))
        (repo / "base.txt").write_text("base")
        commit(repo, "base")
        run(["git", "branch", "origin/main"], cwd=repo)
        run(["git", "checkout", "-qb", "unit/F38"], cwd=repo)
        (repo / "remote.txt").write_text("remote")
        commit(repo, "remote work")
        remote_tip = head(repo)
        run(["git", "update-ref", "refs/remotes/origin/unit/F38", remote_tip], cwd=repo)
        run(["git", "reset", "--hard", "origin/main"], cwd=repo)
        (repo / "local.txt").write_text("local")
        commit(repo, "local work")
        return repo, head(repo), remote_tip

    def test_diverged_histories_are_joined_and_both_tips_survive(self):
        repo, local_tip, remote_tip = self._seed()
        unit = {"id": "F38", "branch": "unit/F38"}
        relation = o.validate_recovery_worktree(
            unit, repo, "refs/remotes/origin/unit/F38")
        self.assertEqual(relation, "merged")
        merged = head(repo)
        self.assertNotIn(merged, (local_tip, remote_tip))
        for tip in (local_tip, remote_tip):
            self.assertEqual(
                run(["git", "merge-base", "--is-ancestor", tip, merged],
                    cwd=repo).returncode, 0,
                f"{tip[:8]} is not an ancestor of the reconciled merge")
        # Neither side's content was dropped.
        self.assertTrue((repo / "local.txt").is_file())
        self.assertTrue((repo / "remote.txt").is_file())

    def test_dirty_worktree_is_refused_by_real_git(self):
        repo, _, _ = self._seed()
        (repo / "local.txt").write_text("edited but uncommitted")
        unit = {"id": "F38", "branch": "unit/F38"}
        with self.assertRaises(o.RecoveryConflict):
            o.validate_recovery_worktree(unit, repo,
                                         "refs/remotes/origin/unit/F38")

    def test_worktree_on_another_branch_is_refused(self):
        repo, _, _ = self._seed()
        run(["git", "checkout", "-q", "origin/main"], cwd=repo)
        unit = {"id": "F38", "branch": "unit/F38"}
        with self.assertRaises(o.RecoveryConflict):
            o.validate_recovery_worktree(unit, repo,
                                         "refs/remotes/origin/unit/F38")


class RealGitPushTest(unittest.TestCase):
    """The reconciled head is what actually lands on the published branch."""

    def setUp(self):
        self.origin = tmpdir("origin-")
        run(["git", "init", "--bare", "-q", str(self.origin)])
        self.repo = git_repo(tmpdir("push-"))
        run(["git", "remote", "add", "origin", str(self.origin)], cwd=self.repo)
        (self.repo / "base.txt").write_text("base")
        commit(self.repo, "base")
        run(["git", "push", "-q", "origin", "HEAD:refs/heads/main"], cwd=self.repo)
        run(["git", "fetch", "-q", "origin"], cwd=self.repo)
        run(["git", "checkout", "-qb", "unit/F38"], cwd=self.repo)
        (self.repo / "remote.txt").write_text("remote")
        commit(self.repo, "remote work")
        self.remote_tip = head(self.repo)
        run(["git", "push", "-q", "origin", "HEAD:refs/heads/unit/F38"], cwd=self.repo)
        run(["git", "reset", "--hard", "origin/main"], cwd=self.repo)
        (self.repo / "local.txt").write_text("local")
        commit(self.repo, "local work")
        self.local_tip = head(self.repo)
        run(["git", "fetch", "-q", "origin", "--prune"], cwd=self.repo)

    def test_recovery_publishes_the_reconciled_head_under_the_pr(self):
        unit = {"id": "F38", "status": "todo", "attempts": 2, "tokens": 1,
                "pr": 0}
        with in_dir(self.repo), \
             mock.patch.object(o, "attach_worktree", lambda u: self.repo), \
             mock.patch.object(o, "adopt_branch_unit", lambda u, s: False), \
             mock.patch.object(o, "run_check", lambda wt: (0, "ok")), \
             mock.patch.object(o, "find_existing_pr", lambda b: 66):
            self.assertTrue(o.recover_branch(unit, {}, _state()))
        merged = run(["git", "rev-parse", "HEAD"], cwd=self.repo).stdout.strip()
        published = run(["git", "rev-parse", "refs/heads/unit/F38"],
                        cwd=self.origin).stdout.strip()
        # The PR's branch now holds exactly the reconciled head.
        self.assertEqual(published, merged)
        for tip in (self.local_tip, self.remote_tip):
            self.assertEqual(
                run(["git", "merge-base", "--is-ancestor", tip, published],
                    cwd=self.origin).returncode, 0)
        self.assertEqual(unit["pr"], 66)
        self.assertEqual(unit["status"], "queued")


if __name__ == "__main__":
    unittest.main()

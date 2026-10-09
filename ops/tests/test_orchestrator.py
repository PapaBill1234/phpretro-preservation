"""orchestrator: diff base, diff guard, planner, advisory units, deadlock.

Every test here corresponds to a defect that actually took the live pipeline
down (parked QA1/QA2, a starved design backlog, a split deadlock) or to a rule
the operator asked for (advisory QA, the unit's own delivery note).
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from harness import REPO, commit, git_repo, head, run, tmpdir

import orchestrator as o


class DiffBaseTest(unittest.TestCase):
    """The guard/quality diff must compare against the MERGE BASE (three-dot).

    A two-dot ``BASE HEAD`` diff also reports what main gained after the branch
    point as if the unit had changed it, which parked QA1/QA2/F36 for touching
    docs/units/RF1.md - a file they never touched.
    """

    def setUp(self):
        self.repo = git_repo(tmpdir("diffbase-"))
        (self.repo / "docs/units").mkdir(parents=True)
        (self.repo / "a.txt").write_text("a")
        (self.repo / "docs/units/OTHER.md").write_text("base")
        commit(self.repo, "base")
        run(["git", "branch", "origin/main"], cwd=self.repo)
        # the unit branch, based on the current trunk
        run(["git", "checkout", "-qb", "unit/X"], cwd=self.repo)
        (self.repo / "b.txt").write_text("b")
        commit(self.repo, "unit work")
        # trunk advances AFTER the branch point
        run(["git", "checkout", "-q", "origin/main"], cwd=self.repo)
        (self.repo / "docs/units/OTHER.md").write_text("changed on main")
        (self.repo / "mainonly.txt").write_text("m")
        commit(self.repo, "main advances")
        run(["git", "checkout", "-q", "unit/X"], cwd=self.repo)

    def test_sanity_old_two_dot_blames_main_only_files(self):
        two = run(["git", "diff", "--name-only", "origin/main", "HEAD"],
                  cwd=self.repo).stdout.split()
        self.assertIn("mainonly.txt", two)
        self.assertIn("docs/units/OTHER.md", two)

    def test_changed_files_ignores_main_only_files(self):
        files = o.changed_files(self.repo)
        self.assertNotIn("mainonly.txt", files)
        self.assertNotIn("docs/units/OTHER.md", files)

    def test_changed_files_keeps_the_units_own_change(self):
        self.assertIn("b.txt", o.changed_files(self.repo))


class DiffGuardTest(unittest.TestCase):
    def test_in_scope_path_allowed(self):
        self.assertEqual(o.guard_violations(["internal/registration/x.go"],
                                            ["internal/registration"]), [])

    def test_listed_file_and_wildcard_allowed(self):
        allowed = ["internal/registration/**", "docs/units/F25.md"]
        self.assertEqual(o.guard_violations(["internal/registration/x.go"], allowed), [])
        self.assertEqual(o.guard_violations(["docs/units/F25.md"], allowed), [])

    def test_protected_paths_rejected(self):
        for path in ("ops/orchestrator.py", "scripts/check.sh", "AGENTS.md",
                     ".github/workflows/ci.yml", "skills/x/SKILL.md"):
            with self.subTest(path=path):
                got = o.guard_violations([path], ["internal/reg"])
                self.assertEqual(got, [(path, "protected path")])

    def test_out_of_scope_path_rejected(self):
        self.assertEqual(
            o.guard_violations(["internal/profile/profile.go"], ["internal/registration"]),
            [("internal/profile/profile.go", "outside the unit's listed paths")])

    def test_own_delivery_note_always_allowed(self):
        # The brief requires docs/units/<id>.md; a unit whose paths omit it must
        # not be rejected for writing it (this parked F38-ba).
        self.assertEqual(
            o.guard_violations(["docs/units/F38-ba.md"], ["internal/staff/window.go"], "F38-ba"),
            [])

    def test_another_units_note_is_still_out_of_scope(self):
        self.assertEqual(
            o.guard_violations(["docs/units/F26.md"], ["internal/reg"], "F25"),
            [("docs/units/F26.md", "outside the unit's listed paths")])

    def test_no_blanket_pass_when_unit_id_unknown(self):
        self.assertEqual(
            o.guard_violations(["docs/units/F1.md"], ["internal/reg"]),
            [("docs/units/F1.md", "outside the unit's listed paths")])


class PlannerOutputTest(unittest.TestCase):
    def test_replacement_paths_gain_the_mandatory_doc(self):
        plan = ('units:\n  - id: F9a\n    title: "p1"\n    size: S\n'
                '    paths: [internal/big/a.go]\n    acceptance: ["works"]\n'
                '    tests: ["go test ./..."]\n')
        road = {}
        self.assertTrue(o.apply_planner_output(road, {}, {}, plan, old_id="F9", mode="split"))
        self.assertIn("docs/units/F9a.md", road["F9a"]["paths"])

    def test_size_l_replacement_rejected(self):
        plan = ('units:\n  - id: F9c\n    title: "too big"\n    size: L\n'
                '    paths: [internal/big/c.go]\n    acceptance: ["works"]\n'
                '    tests: ["go test ./..."]\n')
        self.assertFalse(o.apply_planner_output({}, {}, {}, plan, old_id="F9", mode="split"))

    def test_oversized_split_rejected(self):
        many = "units:\n" + "".join(
            f'  - id: F9{i}\n    title: "p{i}"\n    size: S\n'
            f'    paths: [internal/big/{i}.go]\n    acceptance: ["works"]\n'
            f'    tests: ["go test ./..."]\n' for i in range(o.SPLIT_MAX_UNITS + 1))
        self.assertFalse(o.apply_planner_output({}, {}, {}, many, old_id="F9", mode="split"))


class AdvisoryUnitsTest(unittest.TestCase):
    """QA units advise; they must never gate or starve feature work."""

    def test_classification(self):
        self.assertTrue(o.is_advisory({"id": "QA1"}))
        self.assertTrue(o.is_advisory({"id": "X", "kind": "audit-fix"}))
        self.assertFalse(o.is_advisory({"id": "F31"}))
        self.assertFalse(o.is_advisory({"id": "RF1", "kind": "refactor"}))

    def test_dependency_on_a_qa_unit_is_stripped_from_f_units(self):
        live = {
            "F40": {"id": "F40", "status": "todo", "depends_on": ["QA1", "F35"]},
            "F35": {"id": "F35", "status": "merged"},
            "QA1": {"id": "QA1", "kind": "audit-fix", "status": "parked"},
            "QA2": {"id": "QA2", "kind": "audit-fix", "status": "todo",
                    "depends_on": ["QA1"]},
        }
        o.strip_advisory_deps(live)
        self.assertEqual(live["F40"]["depends_on"], ["F35"])
        self.assertEqual(live["QA2"]["depends_on"], ["QA1"])  # QA may depend on QA

    def test_advisory_yields_when_real_work_is_ready(self):
        road = {"F99": {"id": "F99", "status": "todo", "paths": ["p/f"], "tokens": 0},
                "QA9": {"id": "QA9", "status": "todo", "kind": "audit-fix",
                        "paths": ["p/q"], "tokens": 0}}
        self.assertEqual([u["id"] for u in o.select_ready(road, _free_state())], ["F99"])

    def test_promotion_outranks_advisory_qa(self):
        contract = tmpdir("approved-promotion-") / "contract.md"
        contract.write_text("Approved bounded synthetic contract.\n")
        road = {"QA9": {"id": "QA9", "status": "todo", "kind": "audit-fix",
                        "paths": ["p/q"], "tokens": 0},
                "F32": {"id": "F32", "status": "design", "planner_retries": 0,
                        "planning_ready": True, "planning_context": "contract.md",
                        "planning_paths": ["p/f"], "planning_acceptance": ["done"],
                        "planning_tests": ["test done"]}}
        from unittest.mock import patch
        with patch.object(o, "REPO", contract.parent):
            self.assertTrue(o.planner_pending(road))
            self.assertEqual(o.select_ready(road, _free_state()), [])

    def test_advisory_runs_once_nothing_can_be_promoted(self):
        road = {"QA9": {"id": "QA9", "status": "todo", "kind": "audit-fix",
                        "paths": ["p/q"], "tokens": 0},
                "F33": {"id": "F33", "status": "design-blocked", "planner_retries": 2}}
        self.assertFalse(o.planner_pending(road))
        self.assertEqual([u["id"] for u in o.select_ready(road, _free_state())], ["QA9"])


class PlannerStarvationTest(unittest.TestCase):
    """maybe_plan() must run when the only ready todo is advisory."""

    def setUp(self):
        self._saved_run = o.hermes_run
        self._saved_size = o.jev_size_check
        o.hermes_run = lambda *a, **k: (0, "", {})
        o.jev_size_check = lambda u: {"action": "run_as_is", "source": "rule"}

    def tearDown(self):
        o.hermes_run = self._saved_run
        o.jev_size_check = self._saved_size

    def test_real_todo_holds_the_planner_back(self):
        road = {"F32": {"id": "F32", "status": "todo", "depends_on": [], "tokens": 0}}
        self.assertFalse(o.maybe_plan(road, {"events": []}))

    def test_blocked_advisory_todo_does_not_starve_promotion(self):
        state = {"events": [], "tokens_today": 0}
        road = {"QA3": {"id": "QA3", "status": "todo", "kind": "audit-fix",
                        "depends_on": ["QA1"], "tokens": 0},
                "QA1": {"id": "QA1", "kind": "audit-fix", "status": "parked",
                        "blocked_reason": "no approved contract"},
                "F32": {"id": "F32", "status": "design", "depends_on": [],
                        "design_doc": "", "planner_retries": 0}}
        self.assertFalse(o.maybe_plan(road, state))
        self.assertEqual(o.select_ready(road, _free_state()), [])

    def test_ready_advisory_todo_does_not_starve_promotion(self):
        # The live regression: QA3 became deps-merged and blocked promotion.
        state = {"events": [], "tokens_today": 0}
        road = {"QA3": {"id": "QA3", "status": "todo", "kind": "audit-fix",
                        "depends_on": [], "tokens": 0},
                "F32": {"id": "F32", "status": "design", "depends_on": [],
                        "design_doc": "", "planner_retries": 0}}
        self.assertFalse(o.maybe_plan(road, state))
        self.assertEqual([u["id"] for u in o.select_ready(road, _free_state())], ["QA3"])


class SplitDeadlockTest(unittest.TestCase):
    """A requested split that the planner cannot produce must not wedge a unit.

    It used to keep ``split_requested`` with retries exhausted: select_ready
    skipped it forever and maybe_plan refused to act - a permanent idle unit.
    """

    def setUp(self):
        self._saved_run = o.hermes_run
        self._saved_size = o.jev_size_check
        o.hermes_run = lambda *a, **k: (0, "", {})   # planner output always rejected
        o.jev_size_check = lambda u: {"action": "run_as_is", "source": "rule"}

    def tearDown(self):
        o.hermes_run = self._saved_run
        o.jev_size_check = self._saved_size

    def test_flag_cleared_when_retries_are_spent(self):
        road = {"F9": {"id": "F9", "status": "todo", "split_requested": True,
                       "planner_retries": o.PLANNER_RETRIES - 1, "tokens": 0,
                       "paths": ["p/x"], "title": "t"}}
        o.maybe_plan(road, {"events": [], "tokens_today": 0})
        self.assertEqual(road["F9"]["planner_retries"], o.PLANNER_RETRIES - 1)
        self.assertTrue(road["F9"]["split_requested"])
        self.assertEqual(road["F9"]["status"], "parked")

    def test_the_previously_stuck_unit_becomes_dispatchable(self):
        road = {"F9": {"id": "F9", "status": "todo", "split_requested": True,
                       "planner_retries": o.PLANNER_RETRIES - 1, "tokens": 0,
                       "paths": ["p/x"], "title": "t"}}
        o.maybe_plan(road, {"events": [], "tokens_today": 0})
        self.assertNotIn("F9", [u["id"] for u in o.select_ready(road, _free_state())])

    def test_size_check_does_not_request_a_split_past_the_retry_budget(self):
        o.jev_size_check = lambda u: {"action": "split", "source": "jev"}
        road = {"F9": {"id": "F9", "status": "todo", "planner_retries": o.PLANNER_RETRIES,
                       "tokens": 0, "paths": ["p/x"], "title": "t"}}
        ready = o.select_ready(road, _free_state())
        self.assertFalse(road["F9"].get("split_requested"))
        self.assertIn("F9", [u["id"] for u in ready])


class DiagnosisTest(unittest.TestCase):
    """STATE.md's five-line diagnosis (asked for by the operator)."""

    def _roadmap(self):
        return {
            "F31": {"id": "F31", "status": "promoted"},
            "F32": {"id": "F32", "status": "design"},
            "QA1": {"id": "QA1", "kind": "audit-fix", "status": "parked",
                    "attempts": 4, "reason": "diff guard: docs/units/RF1.md"},
            "QA2": {"id": "QA2", "kind": "audit-fix", "status": "parked",
                    "attempts": 4, "reason": "quality: tests do not exercise the change"},
            "F38": {"id": "F38", "status": "parked-final", "reason": "quality"},
        }

    def _state(self, ts: str):
        return {"day": "2026-10-06", "merged_today": 3, "tokens_today": 1000,
                "events": [{"ts": ts, "msg": "cycle start (x)"}]}

    def test_exactly_five_lines(self):
        lines = o.diagnosis_lines(self._roadmap(), self._state(o.now()))
        self.assertEqual(len(lines), 5, lines)
        for i, prefix in enumerate(("1. Parked:", "2. F31+", "3. ",
                                    "4. Timer:", "5. Dispatch:")):
            self.assertTrue(lines[i].startswith(prefix), lines[i])

    def test_line1_names_every_parked_unit_and_its_reason(self):
        # Two parked units: a bare sorted() over dicts raised TypeError at cycle end.
        line = o.diagnosis_lines(self._roadmap(), self._state(o.now()))[0]
        for token in ("QA1", "QA2", "F38", "diff guard", "quality"):
            self.assertIn(token, line)

    def test_line3_reports_caps_inactive_and_stop_absent(self):
        line = o.diagnosis_lines(self._roadmap(), self._state(o.now()))[2]
        self.assertIn("not in effect", line)
        self.assertIn("no STOP file", line)

    def test_timer_freshness_both_ways(self):
        now = datetime.now(timezone.utc)
        fresh = o.diagnosis_lines(self._roadmap(),
                                  self._state(now.strftime("%Y-%m-%dT%H:%M:%SZ")))[3]
        stale = o.diagnosis_lines(
            self._roadmap(),
            self._state((now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")))[3]
        self.assertIn("within the last hour", fresh)
        self.assertIn("NOT in the last hour", stale)

    def test_write_state_md_renders_the_section(self):
        o.write_state_md(self._roadmap(), self._state(o.now()))
        body = o.STATE_MD.read_text().split("## Diagnosis", 1)[1].split("## Quality", 1)[0]
        self.assertEqual(len([l for l in body.splitlines() if l.startswith("- ")]), 5)


def _free_state() -> dict:
    return {"merged_today": 0, "tokens_today": 0, "events": []}


if __name__ == "__main__":
    unittest.main()

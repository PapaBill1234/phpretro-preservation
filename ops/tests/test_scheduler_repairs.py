"""Regression tests for scheduler repair, planning contracts, and persistence."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from harness import tmpdir

import orchestrator as o


class PlanningContractTest(unittest.TestCase):
    def test_late_context_is_preserved_beyond_old_prefix_limit(self):
        root = tmpdir("planning-context-")
        doc = root / "approved.md"
        body = "approved contract\n" + ("x" * 13000)
        doc.write_text(body)
        unit = {"planning_context": "approved.md"}
        with patch.object(o, "REPO", root):
            self.assertEqual(o.planning_context(unit), body)

    def test_unfilled_missing_oversized_and_protected_contracts_are_ineligible(self):
        root = tmpdir("planning-invalid-")
        (root / "ok.md").write_text("approved")
        (root / "huge.md").write_text("x" * 65537)
        base = {"planning_ready": True, "planning_paths": ["internal/a"],
                "planning_acceptance": ["done"], "planning_tests": ["check"],
                "planning_context": "ok.md"}
        with patch.object(o, "REPO", root):
            self.assertTrue(o.planning_eligible(base))
            for change in (
                {"planning_ready": False},
                {"planning_acceptance": []},
                {"planning_tests": []},
                {"planning_context": "missing.md"},
                {"planning_context": "huge.md"},
                {"planning_context": "ops/orchestrator.py"},
            ):
                candidate = dict(base)
                candidate.update(change)
                self.assertFalse(o.planning_eligible(candidate), change)
            with patch.object(o, "hermes_run") as paid:
                road = {"F1": dict(base, planning_context="missing.md", status="design",
                                    id="F1", planner_retries=0)}
                self.assertFalse(o.maybe_plan(road, {"events": [], "tokens_today": 0}))
                paid.assert_not_called()

    def test_unfilled_design_does_not_starve_ready_qa(self):
        road = {
            "F1": {"id": "F1", "status": "design", "planner_retries": 0},
            "QA1": {"id": "QA1", "status": "todo", "kind": "audit-fix",
                    "paths": ["p/q"], "tokens": 0},
        }
        self.assertEqual([u["id"] for u in o.select_ready(road, {"events": []})], ["QA1"])


class RepairDispatchTest(unittest.TestCase):
    def _dispatch(self, unit, found_pr):
        road = {unit["id"]: unit}
        started = []
        with patch.object(o, "paid_allowed", return_value=True), \
             patch.object(o, "find_existing_pr", return_value=found_pr), \
             patch.object(o, "jev_size_check", return_value={"action": "run_as_is", "source": "rule"}), \
             patch.object(o, "git", return_value=(1, "")), \
             patch.object(o, "start_build", side_effect=lambda u, s, r: started.append(u) or {"unit": u}), \
             patch.object(o, "finish_build"):
            o.dispatch(road, {"events": [], "tokens_today": 0})
        return road[unit["id"]], started

    def test_todo_reviewer_fix_skips_recovery_and_existing_pr_builds_once(self):
        unit = {"id": "F1", "status": "todo", "review_verdict": "fix", "pr": 77,
                "paths": ["p/f"], "tokens": 0, "attempts": 0}
        self.assertTrue(o.repair_requested(unit))
        road = {"F1": unit}
        with patch.object(o, "recover_branch") as recover:
            o.recover_units(road, {}, {"events": []})
        recover.assert_not_called()
        got, started = self._dispatch(unit, 77)
        self.assertEqual(len(started), 1)
        self.assertIs(started[0], unit)
        self.assertEqual(got["pr"], 77)

    def test_mismatched_existing_pr_fails_safely(self):
        unit = {"id": "F2", "status": "todo", "repair_required": True, "pr": 77,
                "paths": ["p/f"], "tokens": 0, "attempts": 0}
        got, started = self._dispatch(unit, 88)
        self.assertEqual(started, [])
        self.assertEqual(got["status"], "parked")
        self.assertIn("identity changed", got["reason"])

    def test_recovery_skips_split_and_blocked_units(self):
        road = {
            "A": {"id": "A", "status": "todo", "attempts": 1, "split_requested": True},
            "B": {"id": "B", "status": "todo", "attempts": 1, "blocked_reason": "hold"},
        }
        with patch.object(o, "recover_branch") as recover:
            o.recover_units(road, {}, {"events": []})
        recover.assert_not_called()


class PersistenceAndPlannerTest(unittest.TestCase):
    def test_feedback_round_trip_preserves_escaping_and_retry_float(self):
        root = tmpdir("roadmap-roundtrip-")
        repo_units, live_units = root / "units.yaml", root / "live.yaml"
        repo_units.write_text("version: 1\nunits:\n  - id: F1\n    title: F1\n    status: todo\n")
        unit = {"id": "F1", "title": "F1", "status": "todo",
                "feedback": 'quote "comma, line\\path\nnext', "provider_retry_at": 123.5,
                "attempts": 1, "tokens": 2}
        with patch.object(o, "REPO_UNITS", repo_units), patch.object(o, "LIVE_UNITS", live_units), \
             patch.object(o, "STATE_JSON", root / "state.json"):
            o.save_roadmap({"F1": unit})
            loaded = o.load_roadmap({})
        self.assertEqual(loaded["F1"]["feedback"], unit["feedback"])
        self.assertEqual(loaded["F1"]["provider_retry_at"], 123.5)

    def test_promoted_candidate_cannot_escape_approved_parent_paths(self):
        root = tmpdir("planner-parent-")
        (root / "contract.md").write_text("approved")
        parent = {"id": "F1", "status": "design", "planning_ready": True,
                  "planning_paths": ["internal/allowed"],
                  "planning_acceptance": ["done"], "planning_tests": ["check"],
                  "planning_context": "contract.md"}
        plan = ("units:\n  - id: F1a\n    title: child\n    size: S\n"
                "    paths: [internal/escape]\n    acceptance: [done]\n"
                "    tests: [check]\n")
        with patch.object(o, "REPO", root):
            self.assertFalse(o.apply_planner_output({}, {}, parent, plan,
                                                    old_id="F1", mode="promote"))


if __name__ == "__main__":
    unittest.main()

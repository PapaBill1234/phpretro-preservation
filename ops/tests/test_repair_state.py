"""Frozen-state migration preserves historical accounting and is idempotent."""
import copy
from unittest.mock import patch

from harness import REPO
from test_maintenance import Isolated, state, unit
import orchestrator as o
import repair_state as r


class RepairStateTest(Isolated):
    def test_reconciliation_preserves_counters_and_unrelated_rows(self):
        road = {"F38": unit("F38", status="parked", tokens=54, attempts=2, pr=66),
                "F39a": unit("F39a", tokens=91, attempts=2, pr=89),
                "QA3": unit("QA3", tokens=8), "F49": unit("F49", status="design"),
                "F33": unit("F33", status="design-blocked", tokens=12),
                "KEEP": unit("KEEP", status="merged", tokens=6)}
        st = state(tokens_today=230, provider_errors=0, provider_pause_reason="old")
        before = copy.deepcopy((road, st))
        with patch.object(o, "REPO", REPO):
            revised, newst = r.repaired(road, st, 90, "a" * 40)
        self.assertEqual((road, st), before)
        self.assertEqual(newst["tokens_today"], 230)
        self.assertNotIn("provider_pause_reason", newst)
        for uid, original in road.items():
            self.assertEqual(revised[uid]["tokens"], original["tokens"])
            self.assertEqual(revised[uid]["attempts"], original["attempts"])
        self.assertEqual(revised["KEEP"], road["KEEP"])
        self.assertEqual(revised["F39a"]["pr"], 90)
        self.assertFalse(revised["F33"]["planning_ready"])
        self.assertTrue(revised["F49"]["planning_ready"])
        self.assertEqual(revised["F61"]["depends_on"], ["F18"])

    def test_requires_stop_and_applies_once_without_new_paid_runs(self):
        o.REPO_UNITS.write_text("units:\n" + o.dump_unit_yaml(unit("F18", status="merged")))
        with self.assertRaises(o.control.IntegrityError):
            r.apply(90, "a" * 40)
        o.STOP_FILE.touch()
        with patch.object(o, "REPO", REPO):
            self.assertTrue(r.apply(90, "a" * 40))
            self.assertFalse(r.apply(90, "a" * 40))
        self.assertTrue(o.STOP_FILE.exists())
        o.sh.assert_not_called()
        self.assertEqual(o.control.ledger_records(o.STATE_DIR), [])

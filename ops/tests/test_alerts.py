"""Failure alerts: the streak boundary and the re-nag window.

Only failures alert; a healthy run sends nothing, an unchanged condition set is
held until the re-nag window, and a CHANGE alerts immediately. Delivery is
monkeypatched, so nothing is sent.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone

from harness import tmpdir

import nightly as n


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class StreakBoundaryTest(unittest.TestCase):
    """A single failed night must not alert; two in a row must."""

    def setUp(self):
        n.STATE_DIR.mkdir(parents=True, exist_ok=True)
        if n.NIGHTLY_HISTORY.exists():
            n.NIGHTLY_HISTORY.unlink()
        self._saved_send = n.send_alert
        self.sent = []
        n.send_alert = lambda text: (self.sent.append(text), (True, "stub"))[1]

    def tearDown(self):
        n.send_alert = self._saved_send

    def _add(self, name: str, ok: bool):
        n.append_line(n.NIGHTLY_HISTORY,
                      {"name": name, "ok": ok, "started": _iso(datetime.now(timezone.utc)),
                       "finished": _iso(datetime.now(timezone.utc))})

    def test_one_failure_is_not_an_alert(self):
        self._add("selfcheck", False)
        self.assertEqual(n.trailing_failures(None, "selfcheck"), 1)
        conds = n.active_conditions()
        self.assertFalse(any("selfcheck check failed" in c for c in conds), conds)

    def test_two_failures_in_a_row_alert(self):
        self._add("selfcheck", False)
        self._add("selfcheck", False)
        self.assertEqual(n.trailing_failures(None, "selfcheck"), 2)
        conds = n.active_conditions()
        self.assertTrue(any("selfcheck check failed 2x in a row" in c for c in conds), conds)

    def test_a_success_breaks_the_streak(self):
        self._add("selfcheck", False)
        self._add("selfcheck", False)
        self._add("selfcheck", True)
        self.assertEqual(n.trailing_failures(None, "selfcheck"), 0)

    def test_three_failures_report_the_full_count(self):
        for _ in range(3):
            self._add("integration", False)
        conds = n.active_conditions()
        self.assertTrue(any("integration check failed 3x in a row" in c for c in conds), conds)


class AlertGateTest(unittest.TestCase):
    def setUp(self):
        n.STATE_DIR.mkdir(parents=True, exist_ok=True)
        for p in (n.ALERT_STATE, n.NIGHTLY_HISTORY, n.NIGHTLY_JSON):
            if p.exists():
                p.unlink()
        self._saved_send = n.send_alert
        self.sent = []
        n.send_alert = lambda text: (self.sent.append(text), (True, "stub"))[1]
        # Force exactly one known condition: a long-past last merge.
        self._saved_merge_age = n.last_merge_age_hours
        n.last_merge_age_hours = lambda: 99.0

    def tearDown(self):
        n.send_alert = self._saved_send
        n.last_merge_age_hours = self._saved_merge_age

    def test_no_conditions_sends_nothing(self):
        n.last_merge_age_hours = lambda: 0.1
        res = n.alerts()
        self.assertEqual(self.sent, [])
        self.assertFalse(res["sent"])

    def test_first_occurrence_alerts(self):
        res = n.alerts()
        self.assertEqual(len(self.sent), 1)
        self.assertTrue(res["sent"])
        self.assertIn("no merge", self.sent[0])

    def test_unchanged_conditions_do_not_re_alert(self):
        n.alerts()
        self.assertEqual(len(self.sent), 1)
        n.alerts()
        self.assertEqual(len(self.sent), 1, "an unchanged condition set must be held")

    def test_renag_window_sends_again(self):
        n.alerts()
        led = n.read_json(n.ALERT_STATE, {})
        old = datetime.now(timezone.utc) - timedelta(seconds=n.ALERT_RENAG + 60)
        led["last"]["sent_at"] = _iso(old)
        n.write_json(n.ALERT_STATE, led)
        n.alerts()
        self.assertEqual(len(self.sent), 2, "the re-nag window must resend")

    def test_forced_alert_ignores_the_window(self):
        n.alerts()
        n.alerts(force=True)
        self.assertEqual(len(self.sent), 2)

    def test_a_new_condition_alerts_immediately(self):
        n.alerts()
        self.assertEqual(len(self.sent), 1)
        # Add a second condition (STOP file present) - the set changed.
        n.STOP_FILE.parent.mkdir(parents=True, exist_ok=True)
        n.STOP_FILE.write_text("halt\n")
        try:
            n.alerts()
            self.assertEqual(len(self.sent), 2)
            self.assertIn("STOP", self.sent[1])
        finally:
            n.STOP_FILE.unlink()


class CapConditionTest(unittest.TestCase):
    def setUp(self):
        n.STATE_DIR.mkdir(parents=True, exist_ok=True)
        if n.STOP_FILE.exists():
            n.STOP_FILE.unlink()

    def test_cap_hit_is_a_condition(self):
        n.write_json(n.UNITS_STATE, {"merged_today": n.MAX_MERGE_PER_DAY,
                                     "tokens_today": 0, "events": []})
        conds = n.active_conditions()
        self.assertTrue(any("merge cap hit" in c for c in conds), conds)

    def test_below_cap_is_not_a_condition(self):
        n.write_json(n.UNITS_STATE, {"merged_today": n.MAX_MERGE_PER_DAY - 1,
                                     "tokens_today": 0, "events": []})
        conds = n.active_conditions()
        self.assertFalse(any("merge cap hit" in c for c in conds), conds)


if __name__ == "__main__":
    unittest.main()

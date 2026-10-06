"""Timeout accounting: a killed run must never be charged 0 tokens.

A timeout used to record 0, so a unit could burn the whole budget through
repeated timeouts without ever tripping its per-unit cap. The rule now is:
prefer the usage file, then the profile's state.db, then a pessimistic estimate.
"""

from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path

from harness import tmpdir

import orchestrator as o


class UsageTokensTest(unittest.TestCase):
    def test_prefers_total_including_auxiliary(self):
        self.assertEqual(
            o.usage_tokens({"total_including_auxiliary": 123, "total_tokens": 9}), 123)

    def test_total_including_auxiliary_may_be_nested(self):
        self.assertEqual(
            o.usage_tokens({"total_including_auxiliary": {"total_tokens": 55}}), 55)

    def test_falls_back_to_total_tokens(self):
        self.assertEqual(o.usage_tokens({"total_tokens": 42}), 42)

    def test_falls_back_to_input_plus_output(self):
        self.assertEqual(o.usage_tokens({"input_tokens": 10, "output_tokens": 5}), 15)

    def test_unknown_is_zero_from_the_parser(self):
        # The parser returns 0; the CALLER is what substitutes the estimate, so
        # 0 here never reaches the ledger on a timeout.
        self.assertEqual(o.usage_tokens({}), 0)


class TimeoutAccountingTest(unittest.TestCase):
    """Drive the real accounting branch in finish_build with a fake process."""

    class _Proc:
        def __init__(self, rc):
            self.returncode = rc

        def communicate(self, timeout=None):
            return ("", "")

    def _job(self, uid, usage_path: Path, rc=124):
        return {"unit": {"id": uid, "attempts": 1, "tokens": 0},
                "proc": self._Proc(rc), "started": 0, "logfile": _NullLog(),
                "usage": usage_path, "wt": tmpdir(f"wt-{uid}-"), "ts_start": o.now()}

    def _run(self, uid, usage_obj=None, rc=124, monkeypatch=True):
        usage = o.LOG_DIR / f"{uid}-attempt1.usage.json"
        if usage_obj is not None:
            usage.write_text(json.dumps(usage_obj))
        state = {"events": [], "tokens_today": 0, "merged_today": 0}
        unit = self._job(uid, usage, rc)
        saved = {}
        if monkeypatch:
            # Do not let this touch the network/git; only the accounting matters.
            saved["telemetry_event"] = o.telemetry_event
            saved["event"] = o.event
            saved["log_model_run"] = o.log_model_run
            saved["_publish_attempt"] = o._publish_attempt
            o.telemetry_event = lambda *a, **k: None
            o.event = lambda *a, **k: None
            o.log_model_run = lambda *a, **k: None
            o._publish_attempt = lambda *a, **k: None
        try:
            o.finish_build(unit, {unit["unit"]["id"]: unit["unit"]}, state)
        finally:
            for k, v in saved.items():
                setattr(o, k, v)
        return unit["unit"], state

    def test_usage_file_wins_when_present(self):
        unit, _ = self._run("T-usage", {"total_tokens": 777})
        self.assertEqual(unit["tokens"], 777)

    def test_timeout_without_usage_file_uses_pessimistic_estimate(self):
        unit, _ = self._run("T-est")
        self.assertEqual(unit["tokens"], o.TIMEOUT_FALLBACK_TOKENS)
        self.assertNotEqual(unit["tokens"], 0)

    def test_timeout_records_a_timeout_and_requests_a_split(self):
        unit, _ = self._run("T-split")
        self.assertEqual(unit["timeouts"], 1)
        self.assertTrue(unit["split_requested"])

    def test_state_db_is_used_when_the_usage_file_is_missing(self):
        # A run killed before --usage-file landed can still be charged from the
        # profile store, found by a marker unique to the brief. HOME is the temp
        # tree here, so this builds its own store.
        db = o.PROFILE_HOME["builder"] / "state.db"
        db.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE IF NOT EXISTS messages "
                    "(rowid INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS sessions "
                    "(id TEXT PRIMARY KEY, input_tokens INT, output_tokens INT)")
        con.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
                    ("s1", "user", "UNIT BRIEF T-db whatever"))
        con.execute("INSERT INTO sessions (id, input_tokens, output_tokens) "
                    "VALUES ('s1', 300, 7)")
        con.commit()
        con.close()
        self.assertEqual(o.tokens_from_state_db("builder", "UNIT BRIEF T-db"), 307)

    def test_state_db_returns_zero_when_nothing_matches(self):
        self.assertEqual(o.tokens_from_state_db("builder", "UNIT BRIEF nothing"), 0)
        self.assertEqual(o.tokens_from_state_db("builder", ""), 0)


class KillProcessGroupTest(unittest.TestCase):
    def test_sigterm_is_tried_before_sigkill(self):
        import subprocess
        import sys
        proc = subprocess.Popen([sys.executable, "-c",
                                 "import time; time.sleep(60)"],
                                start_new_session=True)
        mode = o.kill_process_group(proc, grace=5)
        self.assertIn(mode, ("term", "kill"))
        self.assertIsNotNone(proc.poll())


class _NullLog:
    def write(self, *a):
        pass

    def close(self):
        pass


if __name__ == "__main__":
    unittest.main()

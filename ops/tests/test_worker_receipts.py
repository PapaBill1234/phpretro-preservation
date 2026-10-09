"""Real subprocess receipts/cancellation and WAL-aware accounting recovery."""
import json
import os
import signal
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from harness import tmpdir
from test_maintenance import Isolated, state, unit
import orchestrator as o
import integrity as control
import worker


class WorkerSupervisorTest(unittest.TestCase):
    def test_timeout_flushes_sidecar_before_durable_completion(self):
        root = tmpdir("supervisor-")
        usage = root / "usage.json"
        script = ("import signal,time,json; from pathlib import Path\n"
                  "def stop(*args):\n"
                  " Path(" + repr(str(usage)) + ").write_text(json.dumps({'input_tokens':10,'output_tokens':3,'total_tokens':13,'api_calls':1}))\n"
                  " raise SystemExit(0)\n"
                  "signal.signal(signal.SIGTERM,stop)\nwhile True: time.sleep(.05)\n")
        path = root / "receipt.json"
        control.atomic_json(path, {"run_id": "fixture", "command": [sys.executable, "-c", script],
            "cwd": str(root), "profile_home": str(root), "usage_path": str(usage),
            # Allow interpreter startup and handler installation on a loaded
            # host before exercising timeout/flush, rather than racing exec.
            "timeout": 1, "grace": 2, "reserved_tokens": 100})
        result = subprocess.run([sys.executable, str(Path(worker.__file__)), str(path)],
                                capture_output=True, text=True, timeout=12)
        self.assertEqual(result.returncode, 124, result.stderr)
        receipt = json.loads(path.read_text())
        self.assertEqual(receipt["status"], "complete")
        self.assertEqual(receipt["usage"]["total_tokens"], 13)
        self.assertTrue(receipt["usage"]["usage_complete"])
        self.assertNotIn("command", receipt)

    def test_wal_snapshot_matches_unique_run_and_does_not_double_reasoning(self):
        root = tmpdir("wal-")
        db = root / "state.db"
        con = sqlite3.connect(db)
        self.addCleanup(con.close)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("CREATE TABLE messages(session_id TEXT,role TEXT,content TEXT)")
        con.execute("CREATE TABLE sessions(id TEXT,input_tokens INT,output_tokens INT,cache_read_tokens INT,cache_write_tokens INT,reasoning_tokens INT,api_call_count INT)")
        con.executemany("INSERT INTO messages VALUES (?,?,?)", [("old", "user", "UNIT BRIEF X RUN ID old"), ("new", "user", "UNIT BRIEF X RUN ID new")])
        con.executemany("INSERT INTO sessions VALUES (?,?,?,?,?,?,?)", [("old",9000,4,0,0,0,1),("new",10,20,3,2,17,2)])
        con.commit()  # Remains in WAL while this connection is open.
        snap = worker.usage_snapshot(root / "absent.json", db, "RUN ID new")
        self.assertEqual(snap["total_tokens"], 35)
        self.assertEqual(snap["reasoning_tokens"], 17)
        self.assertEqual(snap["api_calls"], 2)
        self.assertFalse(snap["usage_complete"])

    def test_malformed_sidecar_never_becomes_measured_zero(self):
        root = tmpdir("partial-")
        path = root / "usage.json"
        for value in ("{", '[]', '{"total_tokens":-1}', '{"input_tokens":true}'):
            path.write_text(value)
            snap = worker.usage_snapshot(path, root / "absent.db", "RUN ID fixture")
            self.assertFalse(snap["usage_complete"])
            self.assertEqual(o.accounted_usage(snap)["accounted_tokens"], o.TIMEOUT_FALLBACK_TOKENS)

    def test_generic_command_timeout_uses_sigterm_and_keeps_output(self):
        code = "import signal,time\ndef stop(*a):\n print('flushed',flush=True)\n raise SystemExit(0)\nsignal.signal(signal.SIGTERM,stop)\ntime.sleep(30)"
        rc, output = o.sh([sys.executable, "-c", code], timeout=.2)
        self.assertEqual(rc, 124)
        self.assertIn("flushed", output)


class ReceiptRecoveryTest(Isolated):
    def receipt(self, st, data, **kw):
        rid = o.admit_paid(st, unit(), "builder")
        path = o.prepare_worker(rid, st, "builder", o.MODEL["luna"], ["fixture"], self.repo,
                                o.LOG_DIR / (rid + ".usage.json"), 10, 1)
        rec = json.loads(path.read_text())
        rec.update(status="complete", rc=130, usage=data, **kw)
        control.atomic_json(path, rec)
        return rid

    def test_complete_receipt_settles_exactly_once(self):
        rid = self.receipt(state(), {"total_tokens":17,"api_calls":1,"usage_complete":True})
        o.settle_worker_receipts()
        o.settle_worker_receipts()
        rows = control.ledger_records(o.STATE_DIR)
        self.assertEqual(sum(r.get("record_type")=="run" and r.get("run_id")==rid for r in rows), 1)
        self.assertFalse(control.accounting(rows,o.now()[:10],o.TIMEOUT_FALLBACK_TOKENS)["unsettled"])

    def test_active_receipt_defers_without_relaunch_or_settlement(self):
        self.receipt(state(), {}, worker_pid=99, worker_identity="identity")
        with patch.object(worker, "alive", return_value=True), self.assertRaises(o.WorkerBusy):
            o.settle_worker_receipts()
        self.assertEqual(len(control.ledger_records(o.STATE_DIR)), 1)
        o.sh.assert_not_called()

    def test_partial_checkpoint_is_labeled_and_charged_conservatively(self):
        self.receipt(state(), {"total_tokens":27,"api_calls":1,"usage_complete":False})
        o.settle_worker_receipts()
        row = control.ledger_records(o.STATE_DIR)[-1]
        self.assertEqual(row["charged_tokens"], o.TIMEOUT_FALLBACK_TOKENS)
        self.assertFalse(row["usage_complete"])
        self.assertIsNone(row["cost_estimate"])

    def test_stale_pid_identity_is_not_adopted(self):
        self.assertFalse(worker.alive(os.getpid(), "stale-boot:1"))

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process identity and groups required")
    def test_supervisor_sigkill_recovery_stops_child_and_charges_flushed_usage_once(self):
        root = tmpdir("orphan-child-")
        usage = root / "usage.json"
        ready = root / "ready"
        script = ("import signal,time,json; from pathlib import Path\n"
                  "def stop(*a):\n"
                  " Path(" + repr(str(usage)) + ").write_text(json.dumps({'input_tokens':11,'output_tokens':7,'total_tokens':18,'api_calls':1}))\n"
                  " raise SystemExit(0)\n"
                  "signal.signal(signal.SIGTERM,stop)\n"
                  "Path(" + repr(str(ready)) + ").write_text('ready')\n"
                  "while True: time.sleep(.05)\n")
        st = state()
        rid = o.admit_paid(st, unit(), "builder")
        path = o.prepare_worker(rid, st, "builder", o.MODEL["luna"],
                                [sys.executable, "-c", script], root, usage, 120, 500)
        proc = subprocess.Popen([sys.executable, str(Path(worker.__file__)), str(path)],
                                cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        def cleanup_supervisor():
            if proc.poll() is None:
                proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        self.addCleanup(cleanup_supervisor)
        child_file = worker.child_path(path)
        def cleanup_child():
            if child_file.exists():
                data = json.loads(child_file.read_text())
                if worker.alive(data.get("child_pid"), data.get("child_identity")):
                    try:
                        os.killpg(data["child_pid"], signal.SIGKILL)
                    except (KeyError, ProcessLookupError):
                        pass
                    deadline = time.monotonic() + 5
                    while worker.alive(data.get("child_pid"), data.get("child_identity")) and time.monotonic() < deadline:
                        time.sleep(.05)
        self.addCleanup(cleanup_child)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not child_file.exists():
            time.sleep(.02)
        self.assertTrue(child_file.exists(), "bootstrap did not persist child identity")
        while time.monotonic() < deadline and not ready.exists():
            time.sleep(.02)
        self.assertTrue(ready.exists(), "child did not install TERM handler")
        child = json.loads(child_file.read_text())
        self.assertTrue(worker.alive(child["child_pid"], child["child_identity"]))
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)

        o.settle_worker_receipts()
        o.settle_worker_receipts()
        rows = control.ledger_records(o.STATE_DIR)
        settled = [r for r in rows if r.get("record_type") == "run" and r.get("run_id") == rid]
        self.assertEqual(len(settled), 1)
        self.assertEqual(settled[0]["charged_tokens"], 18)
        self.assertFalse(worker.alive(child["child_pid"], child["child_identity"]))

    @unittest.skipUnless(sys.platform.startswith("linux"), "flock supervisor requires Linux")
    def test_duplicate_worker_invocation_does_not_relaunch_child(self):
        root = tmpdir("duplicate-worker-")
        marker = root / "launched"
        script = ("from pathlib import Path; import time\n"
                  "p=Path(" + repr(str(marker)) + "); p.write_text(p.read_text()+'x' if p.exists() else 'x')\n"
                  "time.sleep(2)\n")
        path = root / "receipt.json"
        control.atomic_json(path, {"run_id": "duplicate", "command": [sys.executable, "-c", script],
            "cwd": str(root), "profile_home": str(root), "usage_path": str(root / "usage.json"),
            "timeout": 10, "grace": .2, "reserved_tokens": 100})
        first = subprocess.Popen([sys.executable, str(Path(worker.__file__)), str(path)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        def cleanup_first():
            if first.poll() is None:
                first.kill()
            try:
                first.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        self.addCleanup(cleanup_first)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not marker.exists():
            time.sleep(.02)
        self.assertTrue(marker.exists())
        second = subprocess.run([sys.executable, str(Path(worker.__file__)), str(path)],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(second.returncode, 75)
        first.wait(timeout=10)
        self.assertEqual(marker.read_text(), "x")

    def test_completed_receipt_uses_yesterdays_completion_day(self):
        rid = self.receipt(state(), {"total_tokens": 9, "api_calls": 1, "usage_complete": True},
                           completed_at=time.time() - 86400)
        o.settle_worker_receipts()
        row = next(r for r in control.ledger_records(o.STATE_DIR)
                   if r.get("record_type") == "run" and r.get("run_id") == rid)
        self.assertLess(row["ts_end"][:10], o.now()[:10])

    @unittest.skipUnless(sys.platform.startswith("linux"), "process groups require Linux")
    def test_term_ignoring_tool_process_is_gone_before_receipt_completes(self):
        root = tmpdir("term-ignore-")
        script = ("import subprocess,sys,time\n"
                  "subprocess.Popen([sys.executable,'-c',\"import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)\"])\n"
                  "time.sleep(30)\n")
        path = root / "receipt.json"
        control.atomic_json(path, {"run_id": "term-ignore", "command": [sys.executable, "-c", script],
            "cwd": str(root), "profile_home": str(root), "usage_path": str(root / "usage.json"),
            "timeout": .3, "grace": .1, "reserved_tokens": 100})
        result = subprocess.run([sys.executable, str(Path(worker.__file__)), str(path)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 124, result.stderr)
        receipt = json.loads(path.read_text())
        self.assertEqual(receipt["status"], "complete")
        self.assertFalse(worker.group_alive(receipt["child_pid"]))


if __name__ == "__main__":
    unittest.main()

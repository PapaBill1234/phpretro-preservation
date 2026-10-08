"""Synthetic user-systemd worker service guards (Linux only)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import unittest
import uuid
from unittest.mock import patch

from harness import tmpdir
import integrity as control
import worker
from test_maintenance import Isolated, state, unit
import orchestrator as o


def _manager_available() -> bool:
    if not sys.platform.startswith("linux") or shutil.which("systemd-run") is None:
        return False
    result = subprocess.run(["systemctl", "--user", "show", "--property=Version"],
                            env=worker.bus_env(), capture_output=True, text=True)
    return result.returncode == 0


@unittest.skipUnless(_manager_available(), "user systemd manager unavailable")
class WorkerServiceTest(unittest.TestCase):
    def setUp(self):
        self.root = tmpdir("worker-service-")
        self.run_id = str(uuid.uuid4())
        self.name = "phpretro-run-" + self.run_id + ".service"
        self.marker = self.root / "ran"
        self.usage = self.root / "usage.json"
        self.child_info = self.root / "child.json"
        self.path = self.root / "receipt.json"
        self.addCleanup(self._cleanup_unit)

    def _cleanup_unit(self):
        subprocess.run(["systemctl", "--user", "stop", self.name], env=worker.bus_env(),
                       capture_output=True, timeout=15)
        subprocess.run(["systemctl", "--user", "reset-failed", self.name], env=worker.bus_env(),
                       capture_output=True, timeout=15)

    def _script(self, *, ignore_term=False):
        handler = "signal.signal(signal.SIGTERM, signal.SIG_IGN)" if ignore_term else (
            "def stop(*a):\n Path(" + repr(str(self.usage)) +
            ").write_text(json.dumps({'total_tokens': 7, 'api_calls': 1}))\n raise SystemExit(0)\n"
            "signal.signal(signal.SIGTERM, stop)")
        child = ("p=subprocess.Popen([sys.executable, '-c', \"import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)\"], start_new_session=True)\n"
                 "Path(" + repr(str(self.child_info)) + ").write_text(json.dumps({'pid':p.pid}))\n")
        return ("import signal,time,json,subprocess,sys; from pathlib import Path\n" + handler + "\n"
                + child + "Path(" + repr(str(self.marker)) + ").write_text('ran')\n"
                + "while True: time.sleep(.05)\n")

    def _manifest(self, command, timeout=.4, grace=.2):
        control.atomic_json(self.path, {"run_id": self.run_id, "unit_name": self.name,
            "command": [sys.executable, "-c", command], "cwd": str(self.root),
            "profile_home": str(self.root), "usage_path": str(self.usage),
            "timeout": timeout, "grace": grace, "reserved_tokens": 100})

    def test_timeout_flushes_sidecar_and_drains_term_ignoring_descendant(self):
        self._manifest(self._script(), timeout=.4, grace=.2)
        result = subprocess.run([sys.executable, str(Path(worker.__file__)), str(self.path)],
                                env=worker.bus_env(), capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 124, result.stderr)
        receipt = json.loads(self.path.read_text())
        self.assertEqual(receipt["status"], "complete")
        self.assertTrue(self.usage.exists())
        self.assertEqual(json.loads(self.usage.read_text())["total_tokens"], 7)
        child_pid = json.loads(self.child_info.read_text())["pid"]
        self.assertFalse(worker.process_identity(child_pid))
        self.assertEqual(worker.unit_state(self.name), "inactive")

    def test_cancel_marker_blocks_late_exec(self):
        self._manifest("from pathlib import Path; Path(" + repr(str(self.marker)) + ").write_text('ran')")
        manifest = json.loads(self.path.read_text())
        manifest.update(status="running", worker_pid=os.getpid(), worker_identity=worker.process_identity(os.getpid()))
        control.atomic_json(self.path, manifest)
        worker.cancel_launch(self.path, manifest)
        self.assertEqual(worker.exec_service(self.path), 130)
        self.assertFalse(self.marker.exists())

    def test_cancelled_late_systemd_exec_never_runs_command(self):
        command = [sys.executable, "-c", "from pathlib import Path; Path(" + repr(str(self.marker)) + ").write_text('ran')"]
        self._manifest("ignored")
        manifest = json.loads(self.path.read_text())
        manifest.update(status="running", worker_pid=os.getpid(), worker_identity=worker.process_identity(os.getpid()), command=command)
        control.atomic_json(self.path, manifest)
        worker.cancel_launch(self.path, manifest)
        result = subprocess.run(["systemd-run", "--user", "--quiet", "--wait", "--collect",
                                 "--unit=" + self.name, "--", sys.executable,
                                 str(Path(worker.__file__).resolve()), "--exec", str(self.path.resolve())],
                                env=worker.bus_env(), capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.marker.exists())


class ReceiptServiceRecoveryTest(Isolated):
    @unittest.skipUnless(_manager_available(), "user systemd manager unavailable")
    def test_killed_supervisor_service_recovers_and_settles_once(self):
        root = tmpdir("service-recovery-")
        usage = root / "usage.json"
        ready = root / "ready"
        command = ("import signal,time,json; from pathlib import Path\n"
                   "def stop(*a):\n Path(" + repr(str(usage)) + ").write_text(json.dumps({'total_tokens': 13, 'api_calls': 1}))\n raise SystemExit(0)\n"
                   "signal.signal(signal.SIGTERM, stop)\n"
                   "Path(" + repr(str(ready)) + ").write_text('ready')\n"
                   "while True: time.sleep(.05)\n")
        st = state()
        rid = o.admit_paid(st, unit(), "builder")
        name = "phpretro-run-" + rid + ".service"
        path = o.prepare_worker(rid, st, "builder", o.MODEL["luna"],
                                [sys.executable, "-c", command], root, usage, 30, 0.2)
        rec = json.loads(path.read_text())
        rec["unit_name"] = name
        rec["grace"] = .2
        control.atomic_json(path, rec)
        proc = subprocess.Popen([sys.executable, str(Path(worker.__file__)), str(path)],
                                env=worker.bus_env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: proc.kill() if proc.poll() is None else None)
        self.addCleanup(lambda: subprocess.run(["systemctl", "--user", "stop", name],
                                               env=worker.bus_env(), capture_output=True, timeout=15))
        child = worker.child_path(path)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not ready.exists():
            time.sleep(.05)
        self.assertTrue(child.exists())
        self.assertTrue(ready.exists(), "service must install its flush handler before supervisor kill")
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)
        with patch.object(o, "TERM_GRACE", .1):
            o.settle_worker_receipts()
            o.settle_worker_receipts()
        rows = control.ledger_records(o.STATE_DIR)
        self.assertEqual(sum(r.get("record_type") == "run" and r.get("run_id") == rid for r in rows), 1)
        settled = next(r for r in rows if r.get("record_type") == "run" and r.get("run_id") == rid)
        self.assertEqual(settled["charged_tokens"], 13)
        self.assertEqual(worker.unit_state(name), "inactive")

    def test_mismatched_checked_unit_rejected_before_command(self):
        path = self.root / "receipt.json"
        bad = dict(run_id=str(uuid.uuid4()), unit_name="phpretro-run-" + str(uuid.uuid4()) + ".service",
                   command=[sys.executable, "-c", "raise SystemExit(99)"], cwd=str(self.root),
                   profile_home=str(self.root))
        control.atomic_json(path, bad)
        with self.assertRaises(control.IntegrityError):
            worker.launch_child(path)
        self.assertFalse(worker.child_path(path).exists())


if __name__ == "__main__":
    unittest.main()

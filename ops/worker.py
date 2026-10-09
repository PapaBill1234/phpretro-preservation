#!/usr/bin/env python3
"""Durable stdlib supervisor for one paid run. Never loads credentials.

The controller writes a private manifest before launch. This process survives
a controller exit, enforces the original deadline/token allowance, checkpoints
only usage counters, and terminates the agent gracefully. Receipts let the next
controller cycle settle an interrupted run without launching it twice.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
import re

import integrity as control

COUNTERS = ("input_tokens", "output_tokens", "cache_read_tokens",
            "cache_write_tokens", "reasoning_tokens", "total_tokens", "api_calls")
_stopping = False


def child_path(path):
    return path.with_suffix(".child.json")


def claim(path):
    import fcntl
    fh = path.with_suffix(".lock").open("a")
    os.chmod(fh.name, 0o600)
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fh.close()
        return None
    return fh


def launch_child(path):
    """Persist our identity BEFORE exec: no paid process can be untracked."""
    manifest = json.loads(path.read_text())
    if manifest.get("unit_name"):
        checked_unit(manifest["unit_name"], manifest["run_id"])
    control.atomic_json(child_path(path), {"run_id": manifest["run_id"],
        "child_pid": os.getpid(), "child_identity": process_identity(os.getpid())})
    if not alive(manifest.get("worker_pid"), manifest.get("worker_identity")):
        return 130
    os.chdir(manifest["cwd"])
    if manifest.get("runtime") != "openhands":
        os.environ["HERMES_HOME"] = manifest["profile_home"]
    command = manifest["command"]
    if manifest.get("unit_name"):
        name = checked_unit(manifest["unit_name"], manifest["run_id"])
        command = ["systemd-run", "--user", "--quiet", "--wait", "--pipe", "--collect",
            "--service-type=exec", "--unit=" + name,
            "--working-directory=" + manifest["cwd"],
            "--property=KillMode=control-group",
            "--property=Slice=phpretro-inference.slice",
            "--property=MemoryMax=512M",
            "--property=TasksMax=96",
            # The supervisor owns timeout provenance; this is a crash backstop.
            "--property=RuntimeMaxSec=" + str(manifest["timeout"] + manifest["grace"] + 5),
            "--property=TimeoutStopSec=" + str(manifest["grace"]),
            "--setenv=HOME=" + str(Path.home()),
            "--setenv=PATH=" + os.environ.get("PATH", "/usr/bin:/bin"),
            "--", sys.executable,
            str(Path(__file__).resolve()), "--exec", str(path.resolve())]
        os.environ.update(bus_env())
    os.execvpe(command[0], command, os.environ)


def checked_unit(name, run_id=None):
    if not isinstance(name, str) or not re.fullmatch(r"phpretro-run-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\.service", name):
        raise control.IntegrityError("invalid worker service identity")
    if run_id is not None and name != "phpretro-run-" + run_id + ".service":
        raise control.IntegrityError("worker service does not belong to receipt")
    return name


def cancel_path(path):
    return path.with_suffix(".cancel.json")


def cancel_launch(path, manifest):
    if manifest.get("unit_name"):
        checked_unit(manifest["unit_name"], manifest["run_id"])
    control.atomic_json(cancel_path(path), {"run_id": manifest["run_id"]})


def exec_service(path):
    """A late manager registration may never start a cancelled paid command.

    Cancellation is persisted before draining the systemd-run requester. A
    service already through this guard is registered and caught by the final
    stop; a service registered later sees the durable cancellation marker.
    """
    manifest = json.loads(path.read_text())
    checked_unit(manifest["unit_name"], manifest["run_id"])
    if (cancel_path(path).exists() or manifest.get("status") != "running"
            or not alive(manifest.get("worker_pid"), manifest.get("worker_identity"))):
        return 130
    os.chdir(manifest["cwd"])
    if manifest.get("runtime") != "openhands":
        os.environ["HERMES_HOME"] = manifest["profile_home"]
    command = manifest["command"]
    os.execvpe(command[0], command, os.environ)


def bus_env():
    env = dict(os.environ)
    runtime = "/run/user/" + str(os.getuid())
    env.update(XDG_RUNTIME_DIR=runtime, DBUS_SESSION_BUS_ADDRESS="unix:path=" + runtime + "/bus")
    return env


def unit_state(name):
    result = subprocess.run(["systemctl", "--user", "show", checked_unit(name),
        "--property=ActiveState", "--property=LoadState"], env=bus_env(),
        capture_output=True, text=True, timeout=10)
    values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if values.get("LoadState") == "not-found":
        return "inactive"
    if not values.get("ActiveState"):
        raise control.IntegrityError("worker user service manager unavailable")
    return values["ActiveState"]


def stop_unit(name):
    if unit_state(name) not in ("inactive", "failed"):
        result = subprocess.run(["systemctl", "--user", "stop", checked_unit(name)],
            env=bus_env(), capture_output=True, timeout=45)
        if result.returncode:
            raise control.IntegrityError("worker service stop failed")
    if unit_state(name) not in ("inactive", "failed"):
        raise control.IntegrityError("worker service is not quiescent")


def process_identity(pid):
    try:
        # starttime follows the closing ')' in /proc/PID/stat. PID alone is
        # insufficient: a reboot or PID reuse must never adopt another process.
        stat = Path(f"/proc/{int(pid)}/stat").read_text().rsplit(")", 1)[1].split()
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        return boot + ":" + stat[19] if stat[0] != "Z" else ""
    except (OSError, ValueError, TypeError, IndexError):
        return ""


def alive(pid, identity):
    return bool(identity and process_identity(pid) == identity)


def usage_snapshot(path, db, marker, runtime="hermes"):
    """Final sidecar preferred; otherwise a short, read-only WAL-aware query.

    Hermes canonical input excludes cache buckets; reasoning is inside output
    (agent/usage_pricing.py:627-638). A DB snapshot is a lower bound, not a final
    bill: counters may be queued and auxiliary calls may be absent.
    """
    try:
        if path.is_file() and path.stat().st_size <= 1024 * 1024:
            raw = json.loads(path.read_text())
            if not isinstance(raw, dict):
                raise ValueError("invalid usage")
            data = {k: raw[k] for k in COUNTERS if k in raw}
            for k, v in data.items():
                control.nonnegative(v, k)
            aux = raw.get("total_including_auxiliary")
            if isinstance(aux, dict):
                data["total_including_auxiliary"] = {"total_tokens": control.nonnegative(aux["total_tokens"])}
                v = aux.get("estimated_cost_usd")
                if isinstance(v, (int, float)) and not isinstance(v, bool) and __import__("math").isfinite(v) and v >= 0:
                    data["total_including_auxiliary"]["estimated_cost_usd"] = v
            elif isinstance(aux, int) and not isinstance(aux, bool):
                data["total_including_auxiliary"] = control.nonnegative(aux)
            # Preserve only typed billing/session metadata, never arbitrary text.
            for k in ("estimated_cost_usd",):
                v = raw.get(k)
                if isinstance(v, (int, float)) and not isinstance(v, bool) and __import__("math").isfinite(v) and v >= 0:
                    data[k] = v
            for k in ("cost_status", "model", "provider", "session_id", "runtime"):
                v = raw.get(k)
                if isinstance(v, str) and __import__("re").fullmatch(r"[A-Za-z0-9_.:/-]{1,120}", v):
                    data[k] = v
            data.update(accounting_source="openhands-usage" if runtime == "openhands" else "usage-file",
                        usage_complete=raw.get("usage_complete") is True if runtime == "openhands" else True,
                        input_includes_cache=False)
            if runtime == "openhands":
                data["runtime"] = "openhands"
            # Missing totals/parts are not evidence of a zero-spend run.
            if "total_tokens" not in data and not all(k in data for k in ("input_tokens", "output_tokens")):
                raise ValueError("incomplete usage")
            return data
    except (OSError, ValueError, KeyError, control.IntegrityError):
        pass
    if runtime == "openhands" or not db.is_file() or not marker:
        return {"accounting_source": "unknown", "usage_complete": False,
                **({"runtime": "openhands"} if runtime == "openhands" else {})}
    con = None
    try:
        # immutable=1 hides WAL updates and must not be used on the live DB.
        con = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=0.2)
        row = con.execute("SELECT session_id FROM messages WHERE role='user' "
                          "AND instr(content,?)>0 ORDER BY rowid DESC LIMIT 1", (marker,)).fetchone()
        if not row:
            return {"accounting_source": "unknown", "usage_complete": False}
        cols = {r[1] for r in con.execute("PRAGMA table_info(sessions)")}
        names = [k for k in COUNTERS if k in cols and k != "total_tokens"]
        if "api_call_count" in cols:
            names.append("api_call_count")
        if not names:
            return {"accounting_source": "unknown", "usage_complete": False}
        values = con.execute("SELECT " + ",".join(names) + " FROM sessions WHERE id=?", (row[0],)).fetchone()
        data = {k: control.nonnegative(v or 0) for k, v in zip(names, values or [])}
        if "api_call_count" in data:
            data["api_calls"] = data.pop("api_call_count")
        data["total_tokens"] = sum(data.get(k, 0) for k in
                                   ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"))
        data.update(accounting_source="state-db-partial", usage_complete=False, input_includes_cache=False)
        return data
    except (OSError, ValueError, sqlite3.Error, control.IntegrityError):
        return {"accounting_source": "unknown", "usage_complete": False}
    finally:
        if con is not None:
            con.close()


def group_alive(pgid):
    # Exclude zombies: they cannot write or spend, and their parent may reap
    # later. A live group member must leave before accounting/review resumes.
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            try:
                fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                if fields[0] != "Z" and int(fields[2]) == pgid:
                    return True
            except (OSError, ValueError, IndexError):
                pass
    return False


def tracked_group_alive(pgid, identity):
    """An orphan's group can survive its leader; never adopt a reused PID."""
    if not isinstance(pgid, int) or not isinstance(identity, str) or ":" not in identity:
        return False
    current = process_identity(pgid)
    if current and current != identity:
        return False
    boot, start = identity.rsplit(":", 1)
    try:
        if Path("/proc/sys/kernel/random/boot_id").read_text().strip() != boot:
            return False
        started = int(start)
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                if fields[0] != "Z" and int(fields[2]) == pgid and int(fields[3]) == pgid and int(fields[19]) >= started:
                    return True
            except (OSError, ValueError, IndexError):
                pass
    except (OSError, ValueError):
        pass
    return False


def stop(proc, grace):
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return "term"
    deadline = time.monotonic() + grace
    while group_alive(proc.pid) and time.monotonic() < deadline:
        proc.poll()
        time.sleep(.1)
    method = "term"
    if group_alive(proc.pid):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        method = "kill"
    proc.wait(timeout=10)
    deadline = time.monotonic() + 10
    while group_alive(proc.pid) and time.monotonic() < deadline:
        time.sleep(.1)
    if group_alive(proc.pid):
        raise control.IntegrityError("worker group is not quiescent")
    return method


def handle_stop(signum, frame):
    global _stopping
    _stopping = True


def supervise(path):
    global _stopping
    _stopping = False
    lease = claim(path)
    if lease is None:
        return 75  # A second invocation cannot launch the same paid run.
    manifest = json.loads(path.read_text())
    if manifest.get("status") == "complete":
        lease.close()
        return manifest["rc"]
    if manifest.get("status", "prepared") != "prepared":
        lease.close()
        return 75  # Dead workers are settled by recovery, never relaunched.
    if manifest.get("unit_name"):
        checked_unit(manifest["unit_name"], manifest["run_id"])
    marker = "RUN ID " + manifest["run_id"]
    manifest.update(status="running", worker_pid=os.getpid(), worker_identity=process_identity(os.getpid()))
    control.atomic_json(path, manifest)
    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)
    try:
        proc = subprocess.Popen([sys.executable, str(Path(__file__)), "--child", str(path)], cwd=manifest["cwd"],
                                env={**os.environ, "HERMES_HOME": manifest["profile_home"]},
                                start_new_session=True)
    except OSError:
        manifest.update(status="complete", rc=127, completed_at=time.time(), usage={"total_tokens": 0, "api_calls": 0,
                         "usage_complete": True, "accounting_source": "not-launched"})
        manifest.pop("command", None)
        control.atomic_json(path, manifest)
        return 127
    manifest.update(child_pid=proc.pid, child_identity=process_identity(proc.pid))
    control.atomic_json(path, manifest)
    deadline = time.monotonic() + manifest["timeout"]
    rc = None
    try:
        checkpoint_at = 0
        data = {}
        while proc.poll() is None:
            if time.monotonic() >= checkpoint_at:
                data = usage_snapshot(Path(manifest["usage_path"]), Path(manifest["profile_home"]) / "state.db", marker, manifest.get("runtime", "hermes"))
                manifest["usage"] = data
                control.atomic_json(path, manifest)
                checkpoint_at = time.monotonic() + 5
            aux = data.get("total_including_auxiliary")
            total = aux.get("total_tokens", 0) if isinstance(aux, dict) else aux or 0
            total = max(total, data.get("total_tokens", 0))
            if _stopping or time.monotonic() >= deadline or total >= manifest["reserved_tokens"]:
                rc = 130 if _stopping else 124
                break
            time.sleep(.1)
    finally:
        # A leader may exit with tool children alive. Drain them before the
        # receipt lets review/recovery touch this checkout.
        cancel_launch(path, manifest)
        stop(proc, manifest["grace"])
        if manifest.get("unit_name"):
            stop_unit(checked_unit(manifest["unit_name"], manifest["run_id"]))
        if manifest.get("runtime") == "openhands":
            import sandbox
            sandbox.cleanup(manifest["run_id"])
        if rc is None and proc.returncode != 0 and time.monotonic() >= deadline:
            rc = 124
        manifest.update(status="complete", rc=proc.returncode if rc is None else rc,
                        usage=usage_snapshot(Path(manifest["usage_path"]),
                            Path(manifest["profile_home"]) / "state.db", marker, manifest.get("runtime", "hermes")), completed_at=time.time())
        manifest.pop("command", None)
        control.atomic_json(path, manifest)
        lease.close()
    return manifest["rc"]


if __name__ == "__main__":
    if sys.argv[1] == "--exec":
        sys.exit(exec_service(Path(sys.argv[2])))
    if sys.argv[1] == "--child":
        sys.exit(launch_child(Path(sys.argv[2])))
    sys.exit(supervise(Path(sys.argv[1])))

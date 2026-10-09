"""Credential-free Docker tools and gates; trusted host owns Git and inference."""
from __future__ import annotations

import contextlib
import fcntl
import fnmatch
import io
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import tarfile
import tempfile
import time

import integrity as control
import runtime_policy

OPS = runtime_policy.OPS
UID = 65532


def container_name(rid):
    if not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", rid):
        raise control.IntegrityError("invalid sandbox identity")
    return "phpretro-oh-" + rid


def docker(*args, timeout=60, input_bytes=None):
    result = subprocess.run(["docker", *map(str, args)], input=input_bytes,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
                            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")})
    if result.returncode:
        raise control.IntegrityError("Docker operation failed: " + result.stderr.decode("utf-8", "replace")[-600:])
    return result.stdout


def inspect(rid):
    name = container_name(rid)
    result = subprocess.run(["docker", "container", "inspect", name], capture_output=True, timeout=15)
    if result.returncode:
        if "No such" in result.stderr.decode("utf-8", "replace"):
            return None
        raise control.IntegrityError("cannot establish sandbox state")
    data = json.loads(result.stdout)[0]
    if data.get("Config", {}).get("Labels", {}).get("phpretro.run_id") != rid:
        raise control.IntegrityError("sandbox ownership mismatch")
    return data


def cleanup(rid):
    if inspect(rid) is not None:
        docker("rm", "--force", container_name(rid), timeout=45)
    assert_absent(rid)


def assert_absent(rid):
    if inspect(rid) is not None:
        raise control.IntegrityError("sandbox still exists; retain reservation")


@contextlib.contextmanager
def heavy_lane():
    path = OPS / "locks" / "heavy.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def admission_width(state, ceiling=2):
    policy = runtime_policy.load()
    now = time.time()
    mem = dict((k, int(v.split()[0]) * 1024) for k, v in
               (line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines()))
    counters = [int(v) for v in Path("/proc/stat").read_text().splitlines()[0].split()[1:9]]
    idle, total = counters[3] + counters[4], sum(counters)
    previous = state.get("host_cpu_sample")
    load = 0.0
    if previous and total > previous[1]:
        load = 1 - (idle - previous[0]) / (total - previous[1])
    state["host_cpu_sample"] = [idle, total]
    pressure = Path("/proc/pressure/memory").read_text()
    full = re.search(r"full avg10=([0-9.]+)", pressure)
    critical = mem.get("MemAvailable", 0) < policy["minimum_available_memory_bytes"]
    stressed = critical or load >= policy["host_cpu_ceiling"] or (full and float(full[1]) >= 1.0)
    if stressed:
        state.pop("host_stable_since", None)
        state.setdefault("host_pressure_since", now)
        if critical:
            state["builder_width"] = 1
            return 0  # Wait for headroom; never kill a paid call to reduce load.
        if now - state["host_pressure_since"] >= policy["pressure_after_seconds"]:
            state["builder_width"] = 1
    else:
        state.pop("host_pressure_since", None)
        state.setdefault("host_stable_since", now)
        if now - state["host_stable_since"] >= policy["restore_after_seconds"]:
            state["builder_width"] = 2
    state.setdefault("builder_width", 2)
    state["host_resource_observation"] = {"available_memory": mem.get("MemAvailable"), "cpu_fraction": load, "at": now}
    return min(ceiling, state["builder_width"])


def safe_files(root):
    result = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if relative == ".git" or relative.startswith((".git/", "frontend/dist/", "bin/", "dist/")) or any(p in path.parts for p in ("node_modules", "__pycache__")):
            continue
        if path.is_symlink():
            raise control.IntegrityError("symlink in exported source: " + relative)
        if path.is_file():
            if path.stat().st_size > 8 * 1024 * 1024:
                raise control.IntegrityError("oversized exported source: " + relative)
            result[relative] = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
    return result


class Sandbox:
    def __init__(self, rid, source, *, writable=False, paths=(), base="origin/main", initial_files=None):
        self.rid, self.name = rid, container_name(rid)
        self.source = Path(source).resolve()
        self.paths = tuple(paths)
        self.writable = writable
        self.stage = OPS / "sandboxes" / rid / "repo"
        self.before = {}
        self.base = base
        self.initial_files = initial_files or {}

    def prepare(self):
        if inspect(self.rid) is not None or self.stage.exists():
            raise control.IntegrityError("sandbox identity already exists; reconcile instead of relaunching")
        self.stage.parent.mkdir(parents=True, mode=0o700)
        # Git is controller-owned; the disposable clone has no origin or hooks.
        subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(self.source), str(self.stage)], check=True)
        head = subprocess.check_output(["git", "-C", str(self.source), "rev-parse", self.base], text=True).strip()
        subprocess.run(["git", "-C", str(self.stage), "remote", "remove", "origin"], check=True)
        subprocess.run(["git", "-C", str(self.stage), "update-ref", "refs/remotes/origin/main", head], check=True)
        # Include repair edits; never copy host configuration, credentials or caches.
        raw = subprocess.check_output(["git", "-C", str(self.source), "ls-files", "-z", "--cached", "--others", "--exclude-standard"])
        for value in raw.split(b"\0"):
            if not value:
                continue
            relative = value.decode()
            src, dest = self.source / relative, self.stage / relative
            if src.is_symlink():
                raise control.IntegrityError("symlink source is not an accepted artifact")
            if src.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
            elif dest.exists():
                dest.unlink()
        for relative, content in self.initial_files.items():
            if not control.safe_path(relative, (".git/",)):
                raise control.IntegrityError("unsafe controller input path")
            (self.stage / relative).write_text(content)
        self.before = safe_files(self.stage)
        if (self.stage / "frontend").is_dir():
            (self.stage / "frontend" / "node_modules").symlink_to("/opt/frontend/node_modules")
        policy = runtime_policy.load()
        args = ["create", "--name", self.name, "--label", "phpretro.run_id=" + self.rid,
                "--label", "phpretro.role=worker", "--network=none", "--read-only",
                "--user", str(UID) + ":" + str(UID), "--cap-drop=ALL", "--security-opt", "no-new-privileges",
                "--pids-limit", str(policy["container_pids"]), "--memory", policy["container_memory"],
                "--memory-swap", policy["container_memory"], "--cgroup-parent", policy["cgroup_parent"],
                "--tmpfs", "/tmp:rw,exec,nosuid,nodev,size=512m,uid=65532,gid=65532",
                "--tmpfs", "/home/worker:rw,nosuid,nodev,size=64m,uid=65532,gid=65532",
                "--mount", "type=bind,src=" + str(self.stage) + ",dst=/repo" + ("" if self.writable else ",readonly"),
                "--workdir", "/repo", policy["image"], "sleep", "infinity"]
        # Ownership is confined to this disposable source tree, never the host checkout.
        subprocess.run(["sudo", "-n", "chown", "-R", f"{UID}:{UID}", str(self.stage)], check=True)
        docker(*args)
        docker("start", self.name)
        data = inspect(self.rid)
        pid = data["State"]["Pid"]
        group = Path(f"/proc/{pid}/cgroup").read_text()
        expected = subprocess.check_output(["systemctl", "show", policy["cgroup_parent"],
                                            "--property=ControlGroup", "--value"], text=True, timeout=10).strip()
        actual = next((line.split(":", 2)[2] for line in group.splitlines() if line.startswith("0::")), "")
        if not expected or expected == "/" or not actual.startswith(expected + "/"):
            cleanup(self.rid)
            raise control.IntegrityError("container escaped the controlled build slice")
        parent = Path("/sys/fs/cgroup") / expected.lstrip("/")
        memory = (parent / "memory.max").read_text().strip()
        quota, period = (parent / "cpu.max").read_text().split()
        if memory == "max" or int(memory) > 2800 * 1024 * 1024 or quota == "max" or int(quota) / int(period) > 1.5:
            cleanup(self.rid)
            raise control.IntegrityError("build slice resource limits are missing or exceed policy")
        return self

    def execute(self, command, timeout=300):
        if not isinstance(command, str) or len(command) > 20000:
            raise control.IntegrityError("invalid sandbox command")
        timeout = max(1, min(int(timeout), 1800))
        with heavy_lane():
            try:
                proc = subprocess.Popen(["docker", "exec", self.name, "timeout", "--kill-after=5",
                                         str(timeout), "bash", "-c", command],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")})
                tail, count, limited = bytearray(), 0, False
                try:
                    deadline = time.monotonic() + timeout + 15
                    with selectors.DefaultSelector() as stream:
                        stream.register(proc.stdout, selectors.EVENT_READ)
                        while True:
                            if time.monotonic() >= deadline:
                                limited = True
                                break
                            if not stream.select(.1):
                                continue
                            chunk = os.read(proc.stdout.fileno(), 65536)
                            if not chunk:
                                break
                            count += len(chunk)
                            tail.extend(chunk)
                            del tail[:-65536]
                            if count > 4 * 1024 * 1024:
                                limited = True
                                break
                finally:
                    if not limited and proc.poll() is None:
                        try:
                            proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            limited = True
                    if proc.poll() is None:
                        proc.kill()
                    proc.wait(timeout=10)
                    proc.stdout.close()
                return (124 if limited else proc.returncode), tail.decode("utf-8", "replace")
            finally:
                # Namespace restart drains detached/background descendants before
                # releasing the global lane. No paid inference lives in the container.
                docker("restart", "--time", "2", self.name, timeout=30)

    def export(self):
        # End the untrusted namespace before interpreting accepted artifacts.
        cleanup(self.rid)
        subprocess.run(["sudo", "-n", "chown", "-R", f"{os.getuid()}:{os.getgid()}", str(self.stage)], check=True)
        after = safe_files(self.stage)
        changed = sorted(k for k in set(self.before) | set(after) if self.before.get(k) != after.get(k))
        forbidden = ("ops/", ".github/", ".agents/", "skills/", "AGENTS.md", "scripts/check.sh", ".go-version")
        for path in changed:
            if not control.safe_path(path, forbidden) or not any(path == p or path.startswith(p.rstrip("/") + "/") or fnmatch.fnmatchcase(path, p) for p in self.paths):
                raise control.IntegrityError("sandbox export outside unit ownership: " + path)
        # Validate every artifact before touching the trusted checkout.
        for path in changed:
            src, dest = self.stage / path, self.source / path
            if not dest.resolve().is_relative_to(self.source) or dest.is_symlink():
                raise control.IntegrityError("unsafe checkout destination")
            if src.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                fd, temporary = tempfile.mkstemp(prefix=".export-", dir=dest.parent)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(src.read_bytes())
                        os.fchmod(stream.fileno(), 0o755 if src.stat().st_mode & 0o111 else 0o644)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temporary, dest)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
            elif dest.exists():
                dest.unlink()
        return changed

    def close(self):
        cleanup(self.rid)
        if self.stage.exists():
            subprocess.run(["sudo", "-n", "chown", "-R", f"{os.getuid()}:{os.getgid()}", str(self.stage)], check=True)
            shutil.rmtree(self.stage.parent)


def check(source, timeout=1800):
    box = Sandbox(control.identity(), source, writable=True)
    try:
        box.prepare()
        return box.execute("bash scripts/check.sh", timeout)
    except (OSError, subprocess.SubprocessError, control.IntegrityError) as exc:
        return 1, "Isolated check unavailable: " + str(exc)
    finally:
        box.close()


def quality(source, base, unit, floor=60, timeout=1800):
    body = json.dumps({"base": "origin/main", "unit": unit, "floor": floor})
    box = Sandbox(control.identity(), source, writable=True, base=base,
                  initial_files={".phpretro-quality.json": body})
    try:
        box.prepare()
        command = "python3 ops/quality.py --evaluate-json .phpretro-quality.json"
        rc, output = box.execute(command, timeout)
        if rc:
            return {"ok": False, "reason": "isolated quality unavailable", "detail": output[-2000:]}
        return json.loads(output.splitlines()[-1])
    except (OSError, ValueError, subprocess.SubprocessError, control.IntegrityError) as exc:
        return {"ok": False, "reason": "isolated quality unavailable: " + str(exc)}
    finally:
        box.close()

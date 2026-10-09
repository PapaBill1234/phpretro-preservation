#!/usr/bin/env python3
"""Nightly integration check, pipeline self-check, and failure alerts.

Three independent jobs, all run from this file:

* ``--integration``  build the server, start it on a spare port, request every
  main route (status + a key string per route), stop it. Result -> nightly.json.
* ``--selfcheck``    run the orchestrator's ``--selftest``, ``bash -n`` every
  hook, and drive the pre-push hook through a REAL git push in a scratch repo
  (protected path refused, in-scope push allowed, push to main refused). The
  real repository and its branches are never touched.
* ``--alerts``       send a one-line message ONLY when something is wrong:
  no merge in 24h, a cap was hit, the STOP file exists, a nightly check failed
  twice in a row, or disk is over 85%. No success messages.

The orchestrator reads ``nightly.json`` and renders the pass/fail lines into
``STATE.md``; it also opens a fix unit for a failing route. This script never
writes ``STATE.md`` itself (the orchestrator owns that file and would clobber
it), and it never writes the unit roadmap (the orchestrator owns that too).

stdlib + subprocess only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
REPO = Path(os.environ.get("PHPRETRO_REPO", HOME / "phpretro-preservation"))
OPS = Path(os.environ.get("PHPRETRO_OPS", HOME / "phpretro-ops"))
STATE_DIR = OPS / "state"
NIGHTLY_JSON = STATE_DIR / "nightly.json"
NIGHTLY_HISTORY = STATE_DIR / "nightly-history.jsonl"
NIGHTLY_MD = STATE_DIR / "nightly-last.md"
NIGHTLY_LOG_DIR = OPS / "logs" / "nightly"
UNITS_STATE = STATE_DIR / "units.state.json"
ALERT_STATE = STATE_DIR / "alerts.json"
STOP_FILE = OPS / "STOP"
# The merge-cap revert override, written by ops/orchestrator.py's throughput
# guard. Read here (never imported) so alerting does not depend on the
# orchestrator module.
MERGE_CAP_FILE = STATE_DIR / "merge-cap.json"

HERMES = shutil.which("hermes") or str(HOME / ".local" / "bin" / "hermes")
GO_TOOLBIN = os.environ.get("PHPRETRO_TOOLBIN", str(HOME / ".local" / "go-bin"))

def read_env_var(name: str) -> str:
    """Dedicated service environment only; never load interactive credentials."""
    return os.environ.get(name, "").strip()


# Alert delivery. ntfy needs no account and no token on the public server; the
# topic name is the only secret, set in the dedicated alert service environment.
def alert_topic() -> str:
    return (read_env_var("PHPRETRO_ALERT_TOPIC")
            or os.environ.get("PHPRETRO_ALERT_TOPIC", "").strip()
            or read_env_var("NTFY_TOPIC")
            or os.environ.get("NTFY_TOPIC", "").strip())


ALERT_TARGET_PREFIX = "ntfy"
# Re-nag a still-broken state at most this often (seconds); a CHANGE in the set
# of active conditions always alerts immediately.
ALERT_RENAG = int(os.environ.get("PHPRETRO_ALERT_RENAG", str(6 * 3600)))
NO_MERGE_HOURS = float(os.environ.get("PHPRETRO_NO_MERGE_HOURS", "24"))
DISK_PCT = float(os.environ.get("PHPRETRO_DISK_PCT", "85"))
# Caps mirror ops/orchestrator.py; kept as plain numbers so alerting does not
# depend on importing the orchestrator.
MAX_MERGE_PER_DAY = int(os.environ.get("PHPRETRO_MAX_MERGE_PER_DAY", "30"))
MERGE_CAP_REVERTED = int(os.environ.get("PHPRETRO_MERGE_CAP_REVERTED", "12"))
DAILY_TOKEN_CAP = int(os.environ.get("PHPRETRO_DAILY_TOKEN_CAP", "60000000"))
PER_UNIT_TOKEN_CAP = int(os.environ.get("PHPRETRO_UNIT_TOKEN_CAP", "3000000"))

# Every route the server serves today, with the status and the key string that
# proves the right handler answered. Update when a unit adds a route.
ROUTES = [
    ("/healthz", 200, '"status":"ok"'),
    ("/", 200, "<!doctype html>"),
    ("/home", 200, '"username":"DemoUser"'),
    ("/account", 200, '"status":"synthetic"'),
    ("/community", 200, '"Name":"Demo room"'),
    ("/articles", 200, '"Title":"Synthetic article"'),
    ("/api/profile", 200, '"username":"DemoUser"'),
    ("/api/auth/failed", 200, '"Status":200'),
    ("/api/auth/success", 200, '"/security_check?page=0"'),
    ("/api/session/post-logout", 200, '"Confirmation"'),
    ("/not-a-route", 404, "404"),
]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sh(cmd, cwd=None, timeout=600, env=None) -> tuple[int, str]:
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    try:
        p = subprocess.Popen(cmd, cwd=str(cwd) if cwd else None, env=full_env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, start_new_session=True)
    except OSError as exc:
        return 127, f"cannot execute {cmd[0]}: {exc}"
    out = ""
    try:
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, out or ""
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            p.communicate(timeout=30)
        except Exception:
            pass
        return 124, (out or "") + f"\n[killed after {timeout}s]"


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


def effective_merge_cap() -> int:
    """The merge cap in force: 30 normally, or the revert value (12).

    Mirrors ops/orchestrator.py's ``effective_merge_cap`` so alerting uses the
    same number the dispatcher enforces. The revert override is recorded by the
    orchestrator's throughput guard in ``state/merge-cap.json``.
    """
    rec = read_json(MERGE_CAP_FILE, {})
    if isinstance(rec, dict) and rec.get("reverted"):
        try:
            return int(rec.get("value") or MERGE_CAP_REVERTED)
        except (TypeError, ValueError):
            return MERGE_CAP_REVERTED
    return MAX_MERGE_PER_DAY


def write_json(path, data) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=1, sort_keys=True))


# --------------------------------------------------------------------------
# Integration check
# --------------------------------------------------------------------------

def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def export_tree(dest: Path) -> tuple[bool, str]:
    """Export origin/main into ``dest`` without touching the working tree.

    Read-only: ``git archive`` writes a tar stream to stdout and is piped
    straight into the extractor, so nothing changes in the repository and no
    worktree is added. The stream is binary, so it is not decoded as text.
    """
    sh(["git", "fetch", "origin"], cwd=REPO, timeout=300)
    p = subprocess.Popen(["git", "archive", "--format=tar", "origin/main"], cwd=str(REPO),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        with tarfile.open(fileobj=p.stdout, mode="r|") as tf:
            tf.extractall(dest)
    except Exception as exc:
        p.kill()
        return False, f"cannot unpack origin/main: {exc}"
    _, err = p.communicate(timeout=120)
    if p.returncode != 0:
        return False, f"git archive origin/main failed: {err.decode('utf-8', 'replace')[-400:]}"
    return True, ""


def build_server(tree: Path) -> tuple[bool, str, Path]:
    gopin = ""
    vf = tree / ".go-version"
    if vf.exists():
        gopin = vf.read_text().strip()
    env = {"PATH": f"{GO_TOOLBIN}:{os.environ.get('PATH', '')}"}
    if gopin:
        env["GOTOOLCHAIN"] = f"go{gopin}"
    binpath = tree / "phpretro-server"
    rc, out = sh(["go", "build", "-o", str(binpath), "./cmd/phpretro"], cwd=tree,
                 timeout=900, env=env)
    if rc != 0 or not binpath.exists():
        return False, out[-1500:], binpath
    return True, out[-500:], binpath


def wait_ready(port: int, tries: int = 40) -> bool:
    for _ in range(tries):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def probe_routes(port: int) -> list:
    results = []
    for path, want_status, want_key in ROUTES:
        url = f"http://127.0.0.1:{port}{path}"
        status, body, err = 0, "", ""
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                status, body = r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            status, body = e.code, e.read().decode("utf-8", "replace")
        except Exception as exc:
            err = str(exc)
        ok = (status == want_status) and (want_key in body) and not err
        results.append({"path": path, "want_status": want_status, "status": status,
                        "key": want_key, "key_found": want_key in body,
                        "error": err, "ok": ok,
                        "body": body[:300]})
    return results


def integration_check() -> dict:
    if os.environ.get("PHPRETRO_INSIDE_SANDBOX") == "1":
        return _integration_check_host()
    import sandbox
    import integrity as control
    box = sandbox.Sandbox(control.identity(), REPO, writable=True)
    try:
        box.prepare()
        rc, output = box.execute("PHPRETRO_INSIDE_SANDBOX=1 PHPRETRO_REPO=/repo python3 -c 'import sys,json; sys.path.insert(0,\"ops\"); import nightly; print(json.dumps(nightly.integration_check()))'", 1800)
        if rc:
            raise RuntimeError("isolated nightly command failed")
        return json.loads(output.splitlines()[-1])
    except Exception as exc:
        return {"name": "integration", "ok": False, "started": now(), "finished": now(), "error": type(exc).__name__, "routes": []}
    finally:
        box.close()


def _integration_check_host() -> dict:
    started = now()
    tmp = Path(tempfile.mkdtemp(prefix="phpretro-nightly-"))
    proc = None
    try:
        tree = tmp / "tree"
        tree.mkdir()
        ok, out = export_tree(tree)
        if not ok:
            return {"name": "integration", "ok": False, "started": started,
                    "finished": now(), "error": out, "routes": []}
        ok, build_out, binpath = build_server(tree)
        if not ok:
            return {"name": "integration", "ok": False, "started": started,
                    "finished": now(), "error": "server build failed:\n" + build_out,
                    "routes": []}
        port = free_port()
        proc = subprocess.Popen([str(binpath)], cwd=str(tree),
                                env={**os.environ, "PORT": str(port)},
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, start_new_session=True)
        if not wait_ready(port):
            return {"name": "integration", "ok": False, "started": started,
                    "finished": now(),
                    "error": f"server did not answer /healthz on port {port}", "routes": []}
        routes = probe_routes(port)
        failing = [r for r in routes if not r["ok"]]
        return {"name": "integration", "kind": "synthetic-smoke", "capture_verified": False,
                "ok": not failing, "started": started,
                "finished": now(), "port": port,
                "error": "" if not failing else "route checks failed",
                "routes": routes,
                "failing_routes": [r["path"] for r in failing]}
    except Exception as exc:
        return {"name": "integration", "ok": False, "started": started,
                "finished": now(), "error": f"integration check crashed: {exc}",
                "routes": []}
    finally:
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=10)
            except Exception:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    pass
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# Pipeline self-check
# --------------------------------------------------------------------------

def check_ops_tests() -> dict:
    """Run the ops/ regression suite (ops/tests/run_all.sh).

    Runs with PHPRETRO_SKIP_OPS_TESTS=1 so the orchestrator's --selftest does
    not run it a second time in the same job; the suite is the check here.
    ``PHPRETRO_SUITE_DEPTH`` is bumped so the suite's own meta-tests (which spawn
    the suite) do not recurse.
    """
    script = Path(os.environ.get("PHPRETRO_OPS_TESTS",
                                 REPO / "ops" / "tests" / "run_all.sh"))
    if not script.exists():
        return {"name": "ops/tests/run_all.sh", "ok": False,
                "detail": f"missing {script}"}
    depth = int(os.environ.get("PHPRETRO_SUITE_DEPTH", "0")) + 1
    rc, out = sh(["bash", str(script)], cwd=REPO, timeout=900,
                 env={"PHPRETRO_SKIP_OPS_TESTS": "1",
                      "PHPRETRO_SUITE_DEPTH": str(depth)})
    ok = rc == 0 and "ops/tests: PASS" in out
    return {"name": "ops/tests/run_all.sh", "ok": ok,
            "detail": (out.strip() or f"rc={rc}")[-400:]}


def check_selftest() -> dict:
    orch = REPO / "ops" / "orchestrator.py"
    if not orch.exists():
        return {"name": "orchestrator --selftest", "ok": False,
                "detail": f"missing {orch}"}
    # The ops/ suite is check_ops_tests()'s job; skip the copy inside selftest so
    # the nightly job runs it exactly once (and still fails if it fails).
    rc, out = sh(["python3", str(orch), "--selftest"], cwd=REPO, timeout=180,
                 env={"PHPRETRO_SKIP_OPS_TESTS": "1"})
    ok = rc == 0 and "selftest OK" in out
    return {"name": "orchestrator --selftest", "ok": ok,
            "detail": (out.strip() or f"rc={rc}")[-400:]}


def check_hook_syntax() -> dict:
    hooks = sorted((REPO / "ops" / "hooks").glob("*"))
    hooks = [h for h in hooks if h.is_file()]
    if not hooks:
        return {"name": "bash -n hooks", "ok": False, "detail": "no hooks found"}
    bad = []
    for h in hooks:
        rc, out = sh(["bash", "-n", str(h)], timeout=60)
        if rc != 0:
            bad.append(f"{h.name}: {out.strip()[-160:]}")
    return {"name": "bash -n hooks", "ok": not bad,
            "detail": "ok: " + ", ".join(h.name for h in hooks) if not bad
            else "; ".join(bad)}


def check_hook_real_push() -> dict:
    """Drive the pre-push hook through REAL git pushes in a scratch repository.

    A fresh temp repo and a bare temp remote are used; the project repository
    and its branches are only read (the hook file is executed in place)."""
    hook_dir = REPO / "ops" / "hooks"
    hook = hook_dir / "pre-push"
    if not hook.exists():
        return {"name": "pre-push hook (real push)", "ok": False,
                "detail": f"missing {hook}"}
    root = Path(tempfile.mkdtemp(prefix="phpretro-hookcheck-"))
    origin = root / "origin.git"
    repo = root / "repo"
    env = {**os.environ, "GIT_AUTHOR_NAME": "nightly", "GIT_AUTHOR_EMAIL": "nightly@local",
           "GIT_COMMITTER_NAME": "nightly", "GIT_COMMITTER_EMAIL": "nightly@local",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    results = []

    def git(*args, cwd=repo):
        return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)

    def must(*args, cwd=repo):
        p = git(*args, cwd=cwd)
        if p.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()}")
        return p.stdout.strip()

    def push(refspec):
        p = subprocess.run(["git", "push", *refspec], cwd=repo, env=env,
                           capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr

    try:
        subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True, env=env)
        repo.mkdir()
        must("init", "-q")
        (repo / "internal").mkdir()
        (repo / "internal" / "ok.go").write_text("package internal\n")
        (repo / "ops").mkdir()
        (repo / "ops" / "orchestrator.py").write_text("# pipeline\n")
        must("add", "-A"); must("commit", "-qm", "base"); must("branch", "-M", "main")
        must("remote", "add", "origin", str(origin))
        # seed main with the hook OFF, as in reality (the pipeline merges to main)
        p = subprocess.run(["git", "-c", "core.hooksPath=", "push", "-q", "origin", "main"],
                           cwd=repo, env=env, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"seed main: {p.stderr.strip()}")
        must("fetch", "-q", "origin")
        must("config", "core.hooksPath", str(hook_dir))   # hook on for unit pushes
        origin_main = must("rev-parse", "origin/main")

        # 1. a unit branch that edits a protected path must be refused
        must("checkout", "-q", "-B", "unit/T1", "origin/main")
        (repo / "ops" / "orchestrator.py").write_text("# tampered\n")
        must("add", "-A"); must("commit", "-qm", "edit ops")
        rc, out = push(["origin", "HEAD:refs/heads/unit/T1"])
        results.append({"case": "protected path refused", "ok": rc != 0 and "protected paths" in out,
                        "detail": out.strip()[-200:]})

        # 2. an in-scope unit push must be allowed
        must("checkout", "-q", "-B", "unit/T2", "origin/main")
        (repo / "internal" / "ok.go").write_text("package internal\n// work\n")
        must("commit", "-aqm", "in scope")
        rc, out = push(["origin", "HEAD:refs/heads/unit/T2"])
        results.append({"case": "in-scope push allowed", "ok": rc == 0,
                        "detail": out.strip()[-200:]})

        # 3. a push to main must be refused
        must("checkout", "-q", "main")
        (repo / "internal" / "ok.go").write_text("package internal\n// main change\n")
        must("commit", "-aqm", "main change")
        rc, out = push(["origin", "main"])
        results.append({"case": "push to main refused", "ok": rc != 0 and "protected branch" in out,
                        "detail": out.strip()[-200:]})
        _ = origin_main
    except Exception as exc:
        return {"name": "pre-push hook (real push)", "ok": False,
                "detail": f"harness error: {exc}", "cases": results}
    finally:
        shutil.rmtree(root, ignore_errors=True)

    return {"name": "pre-push hook (real push)",
            "ok": bool(results) and all(r["ok"] for r in results), "cases": results,
            "detail": "; ".join(f"{r['case']}={'ok' if r['ok'] else 'FAIL'}" for r in results)}


def selfcheck() -> dict:
    started = now()
    checks = [check_selftest(), check_ops_tests(), check_hook_syntax(),
              check_hook_real_push()]
    return {"name": "selfcheck", "ok": all(c["ok"] for c in checks),
            "started": started, "finished": now(), "checks": checks}


# --------------------------------------------------------------------------
# Ledger + STATE.md handoff
# --------------------------------------------------------------------------

def load_ledger() -> dict:
    """The latest result per job, in the required shape.

    ``nightly.json`` is ``{"integration": {ts,pass,details}, "selfcheck":
    {ts,pass,details}}``. History lives in ``nightly-history.jsonl`` (one line
    per run) so the JSON file stays small and is never rewritten as a growing
    document. A legacy ``history`` key is tolerated on read.
    """
    led = read_json(NIGHTLY_JSON, {})
    if not isinstance(led, dict):
        led = {}
    led.pop("history", None)
    return led


def history_entries() -> list:
    """Every entry in nightly-history.jsonl, oldest first (rotated files too)."""
    entries = []
    files = sorted(STATE_DIR.glob(f"{NIGHTLY_HISTORY.stem}-*{NIGHTLY_HISTORY.suffix}")) \
        + [NIGHTLY_HISTORY]
    for f in files:
        try:
            for line in f.read_text().splitlines():
                if line.strip():
                    entries.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            continue
    return entries


def trailing_failures(_history, name: str) -> int:
    """How many of the most recent nightly runs of ``name`` failed in a row."""
    n = 0
    for entry in reversed(history_entries()):
        if entry.get("name") != name:
            continue
        if entry.get("ok"):
            break
        n += 1
    return n


def record(entry: dict) -> None:
    """Store a job result: nightly.json in the required shape, plus history."""
    led = load_ledger()
    # The required shape carries pass/details; keep the richer record too, so
    # the STATE.md renderer keeps its per-route and per-check detail.
    led[entry["name"]] = {"ts": entry.get("finished") or entry.get("started") or now(),
                          "pass": bool(entry.get("ok")),
                          "details": {k: v for k, v in entry.items()
                                      if k not in ("name", "ok")}}
    led["updated"] = now()
    write_json(NIGHTLY_JSON, led)
    # Append-only history, one line per run.
    append_line(NIGHTLY_HISTORY, entry)
    NIGHTLY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    write_json(NIGHTLY_LOG_DIR / f"{entry['name']}-{stamp}.json", entry)


def append_line(path: Path, record_obj: dict) -> None:
    """Append one JSON line, rotating first if the month changed."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    rotate_if_stale(path)
    try:
        with path.open("a") as fh:
            fh.write(json.dumps(record_obj, sort_keys=True, default=str) + "\n")
    except OSError:
        pass


def rotate_if_stale(path: Path) -> None:
    """Move a log aside as ``<stem>-YYYY-MM<suffix>`` when it is a month old."""
    if not path.exists():
        return
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        return
    if mtime.strftime("%Y-%m") == datetime.now(timezone.utc).strftime("%Y-%m"):
        return
    rotated = path.with_name(f"{path.stem}-{mtime.strftime('%Y-%m')}{path.suffix}")
    n = 1
    while rotated.exists():
        rotated = path.with_name(f"{path.stem}-{mtime.strftime('%Y-%m')}-{n}{path.suffix}")
        n += 1
    try:
        shutil.move(str(path), str(rotated))
    except OSError:
        pass


def write_detail_md() -> None:
    led = load_ledger()
    lines = ["# Nightly checks (latest)", "", f"updated: {led.get('updated', '?')}", ""]
    for name in ("integration", "selfcheck"):
        e = led.get(name)
        if not e:
            continue
        state_txt = "PASS" if e.get("pass") else "FAIL"
        d = e.get("details") or {}
        lines += [f"## {name}: {state_txt}", "",
                  f"- run: {e.get('ts', '?')}",
                  f"- consecutive failures: {trailing_failures(None, name)}"]
        if name == "integration":
            if d.get("error"):
                lines.append(f"- error: {d['error']}")
            for r in d.get("routes", []):
                mark = "ok" if r["ok"] else "FAIL"
                lines.append(f"- [{mark}] {r['path']} -> {r['status']} "
                             f"(want {r['want_status']}, key {r['key']!r} "
                             f"found={r['key_found']})")
        else:
            for c in d.get("checks", []):
                lines.append(f"- [{'ok' if c['ok'] else 'FAIL'}] {c['name']}: {c.get('detail','')}")
                for case in c.get("cases", []):
                    lines.append(f"    - [{'ok' if case['ok'] else 'FAIL'}] {case['case']}")
        lines.append("")
    NIGHTLY_MD.write_text("\n".join(lines) + "\n")


def run_job(name: str) -> dict:
    if name == "integration":
        entry = integration_check()
    elif name == "selfcheck":
        entry = selfcheck()
    else:
        raise SystemExit(f"unknown job {name}")
    record(entry)
    write_detail_md()
    print(f"[{now()}] {name}: {'PASS' if entry['ok'] else 'FAIL'}")
    return entry


# --------------------------------------------------------------------------
# Alerts
# --------------------------------------------------------------------------

def disk_percent() -> float:
    try:
        u = shutil.disk_usage("/")
        return 100.0 * u.used / u.total
    except Exception:
        return 0.0


def last_merge_age_hours() -> float | None:
    st = read_json(UNITS_STATE, {})
    stamps = []
    for e in st.get("events", []):
        if "MERGED PR" in str(e.get("msg", "")):
            stamps.append(e.get("ts", ""))
    if not stamps:
        return None
    try:
        newest = max(datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                     for s in stamps if s)
    except Exception:
        return None
    return (datetime.now(timezone.utc) - newest).total_seconds() / 3600.0


def active_conditions() -> list:
    conds = []
    if STOP_FILE.exists():
        conds.append("STOP file present (dispatch halted)")
    age = last_merge_age_hours()
    if age is None:
        conds.append("no merge recorded yet")
    elif age >= NO_MERGE_HOURS:
        conds.append(f"no merge in {age:.1f}h")
    st = read_json(UNITS_STATE, {})
    merged = int(st.get("merged_today", 0))
    tokens = int(st.get("tokens_today", 0))
    cap = effective_merge_cap()
    if merged >= cap:
        conds.append(f"merge cap hit ({merged}/{cap})")
    if tokens >= DAILY_TOKEN_CAP:
        conds.append(f"daily token cap hit ({tokens}/{DAILY_TOKEN_CAP})")
    for name in ("integration", "selfcheck"):
        n = trailing_failures(None, name)
        if n >= 2:
            conds.append(f"{name} check failed {n}x in a row")
    d = disk_percent()
    if d >= DISK_PCT:
        conds.append(f"disk {d:.0f}% used")
    return conds


def send_alert(text: str) -> tuple[bool, str]:
    """One line to the configured target. ntfy: no account, no token."""
    topic = alert_topic()
    if not topic:
        return False, "no alert target configured (set NTFY_TOPIC in ~/.hermes/.env)"
    target = f"{ALERT_TARGET_PREFIX}:{topic}"
    rc, out = sh([HERMES, "send", "--to", target, "--quiet", text], timeout=90)
    return rc == 0, (out.strip() or f"rc={rc}")


def alerts(force: bool = False) -> dict:
    conds = active_conditions()
    led = load_ledger()
    alerts_led = read_json(ALERT_STATE, {"last": {}, "sent": []})
    prev = set(alerts_led.get("last", {}).get("conditions", []))
    last_sent = alerts_led.get("last", {}).get("sent_at", "")
    changed = set(conds) != prev

    due = changed
    if conds and not due and last_sent:
        try:
            age = (datetime.now(timezone.utc)
                   - datetime.strptime(last_sent, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                   ).total_seconds()
            due = age >= ALERT_RENAG
        except Exception:
            due = True

    result = {"name": "alerts", "ok": True, "started": now(), "finished": now(),
              "conditions": conds, "sent": False, "detail": "no conditions"}
    if not conds:
        result["detail"] = "nothing wrong; no message sent"
        alerts_led["last"] = {"conditions": [], "sent_at": last_sent}
        write_json(ALERT_STATE, alerts_led)
        record(result); write_detail_md()
        return result

    if not (due or force):
        result["detail"] = f"conditions unchanged; holding until the {ALERT_RENAG}s re-nag window"
        record(result); write_detail_md()
        return result

    line = "phpretro ALERT: " + "; ".join(conds)
    ok, detail = send_alert(line)
    result["sent"] = ok
    result["ok"] = ok
    result["detail"] = f"sent={ok} ({detail}) :: {line}" if ok else f"send failed: {detail}"
    alerts_led["last"] = {"conditions": conds, "sent_at": now() if ok else last_sent}
    alerts_led["sent"] = (alerts_led.get("sent", []) + [{"ts": now(), "ok": ok, "line": line}])[-50:]
    write_json(ALERT_STATE, alerts_led)
    record(result); write_detail_md()
    print(f"[{now()}] alerts: {'sent' if ok else 'FAILED'} :: {line if ok else detail}")
    return result


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="PHP-Retro nightly checks and alerts")
    ap.add_argument("--integration", action="store_true")
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--alerts", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force-alert", action="store_true",
                    help="send even if the condition set is unchanged")
    ap.add_argument("--print-conditions", action="store_true")
    args = ap.parse_args()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if args.print_conditions:
        print(json.dumps(active_conditions(), indent=1))
        return 0
    ran = False
    passed = True
    if args.all or args.integration:
        passed = bool(run_job("integration").get("ok")) and passed; ran = True
    if args.all or args.selfcheck:
        passed = bool(run_job("selfcheck").get("ok")) and passed; ran = True
    if args.all or args.alerts:
        passed = bool(alerts(force=args.force_alert).get("ok")) and passed; ran = True
    if not ran:
        ap.error("choose --integration, --selfcheck, --alerts or --all")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

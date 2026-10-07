#!/usr/bin/env python3
"""PHP-Retro autonomous unit pipeline.

Decisions are made here, in a script, with zero tokens. Agents only write,
review or plan code. Every merge goes through ``scripts/check.sh`` and a
serialized merge queue; nothing waits on a human.

stdlib + subprocess only. One cycle per invocation (systemd timer every 2
minutes, ``flock`` so cycles never overlap).

Usage:
    ops/orchestrator.py --once        run one cycle (systemd ExecStart)
    ops/orchestrator.py --status      print the live state and exit
    ops/orchestrator.py --selftest    exercise the YAML subset parser
"""

from __future__ import annotations

import argparse
import fcntl
import fnmatch
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import integrity as control
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

HOME = Path.home()
REPO = Path(os.environ.get("PHPRETRO_REPO", HOME / "phpretro-preservation"))
OPS = Path(os.environ.get("PHPRETRO_OPS", HOME / "phpretro-ops"))
WORK = Path(os.environ.get("PHPRETRO_WORK", HOME / "work"))
GH_REPO = os.environ.get("PHPRETRO_GH_REPO", "PapaBill1234/phpretro-preservation")
# Ref the units branch from. In production this is origin/main. While the
# pipeline's own commit is still on a feature branch, PHPRETRO_BASE_REF points
# at that branch so units can run the not-yet-merged scripts/check.sh.
BASE_REF = os.environ.get("PHPRETRO_BASE_REF", "origin/main")

MAX_PARALLEL = int(os.environ.get("PHPRETRO_MAX_PARALLEL", "4"))
RUN_TIMEOUT = int(os.environ.get("PHPRETRO_RUN_TIMEOUT", "1500"))       # 25 min
CHECK_TIMEOUT = int(os.environ.get("PHPRETRO_CHECK_TIMEOUT", "1800"))
# GitHub Actions is ADVISORY. scripts/check.sh, run on the exact rebased head
# under the merge lock, is the authoritative gate. A queued / cancelled /
# missing Actions run is logged and never blocks a merge, and no cycle waits
# CI_TIMEOUT for a runner that may never be assigned.
CI_TIMEOUT = int(os.environ.get("PHPRETRO_CI_TIMEOUT", "1800"))
CI_ADVISORY = os.environ.get("PHPRETRO_CI_ADVISORY", "1") == "1"
CI_ADVISORY_WAIT = int(os.environ.get("PHPRETRO_CI_ADVISORY_WAIT", "120"))
# The authoritative gate runs on the server under the merge lock, not in CI.
MERGE_GATE_IS_LOCAL = True
MERGE_GATE_DESCRIPTION = ("scripts/check.sh on the exact rebased head, "
                          "under the merge lock (authoritative); "
                          "GitHub Actions = advisory only")
PER_UNIT_TOKEN_CAP = int(os.environ.get("PHPRETRO_UNIT_TOKEN_CAP", "6000000"))
DAILY_TOKEN_CAP = int(os.environ.get("PHPRETRO_DAILY_TOKEN_CAP", "60000000"))
# Throughput (item 1). The base daily merge cap is 30; token caps are unchanged.
# The cap is auto-reverted to 12 when the nightly integration check OR the
# nightly self-check has failed twice in a row (see apply_merge_cap_guard).
MAX_MERGE_PER_DAY = int(os.environ.get("PHPRETRO_MAX_MERGE_PER_DAY", "30"))
MERGE_CAP_REVERTED = int(os.environ.get("PHPRETRO_MERGE_CAP_REVERTED", "12"))
MAX_ATTEMPTS = 4            # luna x2, deepseek x1, sol x1, then parked
PLANNER_RETRIES = 2
DIFF_LINE_CAP = 700
# Quality safeguards (see ops/quality.py).
COVERAGE_FLOOR = float(os.environ.get("PHPRETRO_COVERAGE_FLOOR", "60"))
TOOLBIN = os.environ.get("PHPRETRO_TOOLBIN", str(HOME / ".local" / "go-bin"))
# One refactor unit per this many merged units (item 5).
REFACTOR_EVERY = int(os.environ.get("PHPRETRO_REFACTOR_EVERY", "8"))
# Weekly audit cap (item 4); the audit is a single read-only agent run.
AUDIT_TOKEN_CAP = int(os.environ.get("PHPRETRO_AUDIT_TOKEN_CAP", "3000000"))
# A run we had to kill is charged this much when the real usage cannot be
# recovered, so a unit that repeatedly times out still trips its token cap.
TIMEOUT_FALLBACK_TOKENS = int(os.environ.get("PHPRETRO_TIMEOUT_FALLBACK_TOKENS", "1000000"))
# SIGTERM the process group, wait this long for --usage-file to land, then KILL.
TERM_GRACE = int(os.environ.get("PHPRETRO_TERM_GRACE", "20"))
# On timeout / no-change the planner splits the unit instead of retrying it at
# the same size; every replacement entry must be size S or M.
SPLIT_MAX_UNITS = int(os.environ.get("PHPRETRO_SPLIT_MAX_UNITS", "3"))

# Paths a builder may never touch, whatever the unit lists. Enforced twice:
# the orchestrator discards a diff that touches them, and ops/hooks/pre-push
# refuses to publish one.
PROTECTED_PREFIXES = (
    "ops/",
    ".github/workflows/",
    ".agents/skills/",
    "skills/",
)
PROTECTED_FILES = (
    "AGENTS.md",
    "scripts/check.sh",
)
# The diff guard can be turned off for debugging, but never silently: every
# dispatch while it is off appends a guard_disabled event (telemetry item 2).
GUARD_DISABLED = bool(os.environ.get("PHPRETRO_GUARD_DISABLED"))

PROVIDER = "custom:a6api"
MODEL = {
    "luna": "gpt-6-luna",
    "deepseek": "deepseek-v4.1-flash",
    "sol": "gpt-6.1-sol",
}
LADDER = ["luna", "luna", "deepseek", "sol"]
PROFILE_HOME = {name: HOME / ".hermes" / "profiles" / name
                for name in ("builder", "reviewer", "planner", "auditor")}
HERMES = shutil.which("hermes") or str(HOME / ".local" / "bin" / "hermes")

# Paths whose diff escalates to a Sol second review (auth / session / schema).
SENSITIVE = ("internal/authflow", "internal/session", "internal/account",
             "internal/polaris", "internal/profile/settings", "internal/staff", "migrations")

STATE_DIR = OPS / "state"
LOG_DIR = OPS / "logs"
BRIEF_DIR = OPS / "briefs"
LOCK_DIR = OPS / "locks"
STOP_FILE = OPS / "STOP"
STATE_JSON = STATE_DIR / "units.state.json"
STATE_MD = STATE_DIR / "STATE.md"
LIVE_UNITS = STATE_DIR / "units.live.yaml"
REPO_UNITS = REPO / "units.yaml"
NIGHTLY_JSON = STATE_DIR / "nightly.json"
# The raised merge cap's revert override lives outside the repo, like all other
# runtime state, so the cap can be lowered without a deploy.
MERGE_CAP_FILE = STATE_DIR / "merge-cap.json"

RUNNABLE = ("todo", "building", "pr_open", "queued")


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    print(f"[{now()}] {msg}", flush=True)


def ensure_dirs() -> None:
    for d in (STATE_DIR, LOG_DIR, BRIEF_DIR, LOCK_DIR, WORK):
        d.mkdir(parents=True, exist_ok=True)


def sh(cmd, cwd=None, timeout=600, env=None, check=False):
    """Run a command, capturing stdout+stderr. Returns (rc, output)."""
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
        rc = p.returncode
    except subprocess.TimeoutExpired:
        with_suppress(lambda: os.killpg(os.getpgid(p.pid), signal.SIGKILL))
        with_suppress(lambda: p.communicate(timeout=30))
        out, rc = (out or "") + f"\n[orchestrator] killed after {timeout}s timeout\n", 124
    if check and rc != 0:
        raise RuntimeError(f"{cmd[0]} failed rc={rc}: {out[-2000:]}")
    return rc, (out or "")


def with_suppress(fn):
    try:
        fn()
    except Exception:
        pass


def git(*args, cwd=None, timeout=300):
    return sh(["git", *args], cwd=cwd or REPO, timeout=timeout)


def git_out(*args, cwd=None, timeout=300) -> str:
    rc, out = git(*args, cwd=cwd, timeout=timeout)
    return out.strip() if rc == 0 else ""


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


def write_json(path, data) -> None:
    control.atomic_json(Path(path), data)


# --------------------------------------------------------------------------
# units.yaml subset parser (no PyYAML: stdlib only)
# --------------------------------------------------------------------------

def _split_flow(s: str):
    parts, buf, quote = [], [], None
    for ch in s:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch == ",":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def _scalar(s: str):
    s = s.strip()
    if s == "":
        return ""
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [] if not inner else [_scalar(x) for x in _split_flow(inner)]
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1].replace('\\"', '"')
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    return s


def parse_yaml(text: str) -> dict:
    """Parse the units.yaml subset.

    Top-level scalars, and ``units:`` as a list of mappings. A mapping's value
    is a scalar, an inline flow list (``[a, b]``), or a block list::

        acceptance:
          - one
          - two

    Indentation separates the three levels (unit, key, list item) but the exact
    widths are inferred from the document, because a model that emits block
    lists tends to indent them differently from the hand-written roadmap. The
    earlier version treated every ``- `` line as a new unit, which silently
    turned a block list into bogus units.
    """
    doc: dict = {}
    units: list = []
    current = None
    in_units = False
    unit_indent = None
    pending_key = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if not in_units:
            m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
            if not m:
                continue
            key, val = m.group(1), m.group(2)
            if key == "units" and val == "":
                doc["units"] = units
                in_units = True
                continue
            doc[key] = _scalar(val) if val else {}
            continue
        if line.startswith("-"):
            if unit_indent is None or indent <= unit_indent:
                # A new unit starts only at the unit-list indent.
                unit_indent = indent
                current = {}
                units.append(current)
                pending_key = None
                rest = line[1:].strip()
                if rest:
                    km = re.match(r"^([\w-]+):\s*(.*)$", rest)
                    if km:
                        current[km.group(1)] = _scalar(km.group(2))
                continue
            # A deeper `- item` is a value of the key that opened the list.
            item = line[1:].strip()
            if pending_key is not None and current is not None and item:
                if not isinstance(current.get(pending_key), list):
                    current[pending_key] = []
                current[pending_key].append(_scalar(item))
            continue
        km = re.match(r"^([\w-]+):\s*(.*)$", line)
        if km and current is not None:
            key, val = km.group(1), km.group(2)
            if val == "":
                current[key] = []
                pending_key = key
            else:
                current[key] = _scalar(val)
                pending_key = None
    if in_units:
        doc["units"] = units
    return doc


STATE_KEYS = ("status", "pr", "attempts", "tokens", "wall_s", "model", "reason",
              "review_rounds", "conflict_rounds", "planner_retries", "branch",
              "feedback", "split_requested", "fixes_route", "audit_finding",
              "kind", "fidelity", "severity", "updated", "timeouts", "shrinks",
              "size_check_at", "size_action", "size_source", "run_id", "revision_id",
              "review_head", "review_model", "review_verdict", "review_id", "review2_id", "review2_head",
              "review2_model", "review2_verdict", "delivery_commit", "provider_retry_at", "review_admission_denied")
DEF_KEYS = ("title", "depends_on", "paths", "tests", "acceptance", "fixtures",
            "fidelity_notes", "size", "design_doc", "unclear_semantics")


def dump_unit_yaml(unit: dict) -> str:
    """Serialise one unit. State keys are written too - dropping them would lose
    a unit's PR number and attempt count between cycles."""
    lines = [f"  - id: {unit.get('id','')}"]
    for key in DEF_KEYS + STATE_KEYS:
        if key not in unit:
            continue
        val = unit[key]
        if isinstance(val, list):
            lines.append(f"    {key}: [{', '.join(_flow_item(v) for v in val)}]")
        elif isinstance(val, str):
            lines.append(f'    {key}: {_quote(val)}')
        elif isinstance(val, bool):
            lines.append(f"    {key}: {'true' if val else 'false'}")
        else:
            lines.append(f"    {key}: {val}")
    return "\n".join(lines)


def _quote(s: str) -> str:
    escaped = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{escaped}"'


def _flow_item(v) -> str:
    if isinstance(v, str):
        return _quote(v)
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


# --------------------------------------------------------------------------
# Roadmap + state
# --------------------------------------------------------------------------

def validated_units(path: Path) -> dict:
    doc = parse_yaml(path.read_text())
    rows = doc.get("units")
    if not isinstance(rows, list) or not rows:
        raise control.IntegrityError("invalid/empty units snapshot: " + path.name)
    ids = set()
    for u in rows:
        uid = u.get("id")
        if not isinstance(uid, str) or uid in ids or not u.get("title") or "status" not in u:
            raise control.IntegrityError("partial/duplicate unit snapshot: " + path.name)
        ids.add(uid)
        for key in ("tokens", "attempts", "pr"):
            control.nonnegative(u.get(key, 0), key)
    return doc


def load_roadmap(state: dict) -> dict:
    """Repo units.yaml defines the roadmap; the live copy carries runtime state."""
    doc = validated_units(REPO_UNITS)
    repo_units = doc.get("units", [])
    if not LIVE_UNITS.exists() and STATE_JSON.exists():
        raise control.IntegrityError("established runtime units missing")
    live_doc = validated_units(LIVE_UNITS) if LIVE_UNITS.exists() else {"units": []}
    live = {u["id"]: u for u in live_doc.get("units", [])}
    for u in repo_units:
        uid = u.get("id")
        if not uid:
            continue
        if uid not in live:
            live[uid] = dict(u)
            live[uid].setdefault("status", "todo")
            live[uid].setdefault("attempts", 0)
            live[uid].setdefault("tokens", 0)
            live[uid].setdefault("review_rounds", 0)
            live[uid].setdefault("conflict_rounds", 0)
            live[uid].setdefault("planner_retries", 0)
            live[uid].setdefault("reason", "")
            live[uid].setdefault("pr", 0)
            live[uid].setdefault("model", "")
            live[uid].setdefault("branch", "")
            live[uid].setdefault("updated", now())
        else:
            # keep runtime state, refresh the definition fields
            for key in ("title", "depends_on", "paths", "tests", "acceptance",
                        "fixtures", "fidelity_notes", "size", "design_doc",
                        "unclear_semantics"):
                if key in u:
                    live[uid][key] = u[key]
    for uid, value in state.get("ledger_unit_tokens", {}).items():
        if uid in live:
            live[uid]["tokens"] = max(int(live[uid].get("tokens", 0)), value)
    for uid, value in state.get("ledger_unit_attempts", {}).items():
        if uid in live:
            live[uid]["attempts"] = value
    strip_advisory_deps(live)
    return live


def save_roadmap(roadmap: dict) -> None:
    body = "\n".join(dump_unit_yaml(roadmap[k]) for k in sorted(roadmap))
    text = "version: 1\nunits:\n" + body + "\n"
    def validate(value):
        rows = parse_yaml(value).get("units", [])
        if len(rows) != len(roadmap) or {u["id"] for u in rows} != set(roadmap):
            raise control.IntegrityError("roadmap serialization lost identity")
        for u in rows:
            for key in ("tokens", "attempts", "pr"):
                control.nonnegative(u.get(key, 0), key)
    control.atomic_text(LIVE_UNITS, text, validate)


def load_state() -> dict:
    today = now()[:10]
    rows = control.ledger_records(STATE_DIR)
    ledger = control.accounting(rows, today, TIMEOUT_FALLBACK_TOKENS)
    try:
        st = control.validate_state(json.loads(STATE_JSON.read_text()))
    except (OSError, ValueError, control.IntegrityError):
        if not rows:
            if STATE_JSON.exists() or LIVE_UNITS.exists():
                raise control.IntegrityError("accounting corrupt/missing and ledger unavailable")
            st = {"day": today, "tokens_today": 0, "merged_today": 0, "events": []}
        else:
            st = {"day": today, "tokens_today": ledger["tokens_today"],
                  "merged_today": ledger["merged_today"], "events": [],
                  "accounting_recovered": now(), "accounting_version": 2}
    if st["day"] == today:
        st["tokens_today"] = max(st["tokens_today"], ledger["tokens_today"])
        st["merged_today"] = max(st["merged_today"], ledger["merged_today"])
    if st["day"] != today:
        st["day"] = today
        st["tokens_today"] = ledger["tokens_today"]
        st["merged_today"] = ledger["merged_today"]
    st.setdefault("events", [])
    st.setdefault("reservations", {})
    # A previously launched, unaccounted worker is never relaunched. Recovery
    # requires its immutable usage sidecar or explicit conservative settlement.
    if ledger["unsettled"]:
        raise control.IntegrityError("unsettled paid runs; reconcile usage before dispatch")
    st["reservations"] = {}
    st["ledger_unit_tokens"] = ledger["unit_tokens"]
    st["ledger_unit_attempts"] = ledger["unit_attempts"]
    return st


def rollover(state: dict) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.get("day") != today:
        state["day"] = today
        state["merged_today"] = 0
        state["tokens_today"] = 0


def event(state: dict, msg: str) -> None:
    state["events"].append({"ts": now(), "msg": msg})
    state["events"] = state["events"][-200:]
    log(msg)


def add_tokens(state: dict, unit: dict, tokens: int) -> None:
    rollover(state)
    unit["tokens"] = int(unit.get("tokens", 0)) + int(tokens or 0)
    state["tokens_today"] = int(state.get("tokens_today", 0)) + int(tokens or 0)
    if state["tokens_today"] > DAILY_TOKEN_CAP or unit["tokens"] > PER_UNIT_TOKEN_CAP:
        raise control.IntegrityError("actual usage exceeded daily/per-unit cap; dispatch stopped")


# --------------------------------------------------------------------------
# Quality safeguards (ops/quality.py)
# --------------------------------------------------------------------------

def _load_quality():
    """Import ops/quality.py lazily. It is a sibling of this file."""
    try:
        import importlib.util
        qpath = Path(__file__).with_name("quality.py")
        spec = importlib.util.spec_from_file_location("phpretro_quality", qpath)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {qpath}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as exc:
        log(f"quality module unavailable: {exc}")
        return None


_TELEMETRY_MOD = None
_TT_GUARD_MOD = None


def _load_tt_guard():
    """Import ops/tt_guard.py once (the builder context-engine guard)."""
    global _TT_GUARD_MOD
    if _TT_GUARD_MOD is not None:
        return _TT_GUARD_MOD
    try:
        import importlib.util
        gpath = Path(__file__).with_name("tt_guard.py")
        spec = importlib.util.spec_from_file_location("phpretro_tt_guard", gpath)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {gpath}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _TT_GUARD_MOD = mod
        return mod
    except Exception as exc:
        log(f"tt_guard: unavailable ({exc})")
        return None


def tt_lines() -> list:
    """STATE.md's Token Terminator section: marker + the cost/quality verdict."""
    mod = _load_tt_guard()
    if mod is None:
        return ["- tt_guard module unavailable"]
    try:
        return list(mod.summary_lines())
    except Exception as exc:
        return [f"- tt_guard reporting error: {exc}"]


def _tt_revert(reason: str) -> bool:
    """Explicit maintenance only: deselect and uninstall; no cycle call."""
    cfg = HOME / ".hermes" / "profiles" / "builder" / "config.yaml"
    try:
        text = cfg.read_text()
        changed = re.sub(r"(?m)^([ \t]*engine:)[ \t]*token-terminator[ \t]*$", r"\1 compressor", text)
        if text != changed:
            control.atomic_text(cfg, changed)
        if tt_engine() == "token-terminator":
            return False
    except OSError:
        return False
    venvpy = _hermes_venv_python()
    if venvpy:
        uv = shutil.which("uv") or str(HOME / ".hermes" / "tools" / "uv-0.12.3-linux-x64" / "uv")
        rc, _ = sh([uv, "pip", "uninstall", "--python", str(venvpy), "token-terminator"], timeout=300)
        if rc or _venv_has(venvpy, "token_terminator"):
            return False
    telemetry_event("parked", "", "token-terminator deselected/uninstalled by owner maintenance")
    return True


def _hermes_venv_python() -> Path | None:
    """The dependency venv python Hermes activates (where the package lives).

    ``hermes --print-runtime-command`` names the *launcher* interpreter; the
    third-party dependency environment is a separate uv-managed venv that
    ``hermes_bootstrap.activate_dependencies()`` selects at boot. So the right
    target is the venv that actually contains the distribution, not the launcher.
    """
    base = HOME / ".hermes" / "installs"
    candidates = sorted(base.glob("*/environments/*/venv/bin/python"))
    for cand in candidates:
        if (cand.parent.parent / "lib").exists() and _venv_has(cand, "rtk_hermes_plus"):
            return cand
    if candidates:
        return candidates[-1]
    return None


def _venv_has(venv_python: Path, package: str) -> bool:
    """True when the venv's site-packages contains ``package`` (or its dist)."""
    lib = venv_python.parent.parent / "lib"
    try:
        for sp in lib.glob("python*/site-packages"):
            if (sp / package).is_dir() or list(sp.glob(f"{package}-*.dist-info")):
                return True
    except OSError:
        pass
    return False


def tt_engine() -> str:
    """The builder profile's configured context engine ('' if unset)."""
    mod = _load_telemetry()
    if mod is None:
        return ""
    return mod._context_engine_from_config("builder")


def _tt_auto_revert() -> None:
    """Revert the engine if the guard says it did not pay off. Never raises."""
    mod = _load_tt_guard()
    if mod is None:
        return
    try:
        st = mod.record()
    except Exception as exc:
        log(f"tt_guard: check failed: {exc}")
        return
    if st.get("revert") and tt_engine():
        _tt_revert(st.get("verdict") or "guard did not pay off")


def _load_telemetry():
    """Import ops/telemetry.py once. It is a sibling of this file.

    Cached: every state change appends an event, and re-reading the module on
    each one would add a file read per event for no benefit.
    """
    global _TELEMETRY_MOD
    if _TELEMETRY_MOD is not None:
        return _TELEMETRY_MOD
    try:
        import importlib.util
        tpath = Path(__file__).with_name("telemetry.py")
        spec = importlib.util.spec_from_file_location("phpretro_telemetry", tpath)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {tpath}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _TELEMETRY_MOD = mod
        return mod
    except Exception as exc:
        log(f"telemetry module unavailable: {exc}")
        return None


def telemetry_event(kind: str, unit: str, reason: str = "", **extra) -> None:
    """Append a state change to events.jsonl (telemetry item 2). Never raises."""
    if kind not in ("dispatched", "built", "gate_pass", "gate_fail", "pr_opened",
                    "review_verdict", "merged", "parked", "split", "escalated",
                    "timeout", "provider_error", "guard_disabled"):
        kind = "other"
    mod = _load_telemetry()
    if mod is None:
        return
    try:
        mod.log_event(kind, unit or "", reason, **extra)
    except Exception as exc:
        log(f"telemetry: event log failed: {exc}")


_JEV_MOD = None
_JEV_MISS: set = set()


def _load_jev():
    """Import ops/jev.py once. Never raises: Jev is optional routing help."""
    global _JEV_MOD
    if _JEV_MOD is not None:
        return _JEV_MOD
    try:
        import importlib.util
        jpath = Path(__file__).with_name("jev.py")
        spec = importlib.util.spec_from_file_location("phpretro_jev", jpath)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {jpath}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _JEV_MOD = mod
        return mod
    except Exception as exc:
        log(f"jev module unavailable: {exc}")
        return None


def jev_size_check(unit: dict) -> dict:
    """Item 2a. Never raises; falls back to the rule when Jev is unavailable."""
    mod = _load_jev()
    if mod is None:
        return {"action": "run_as_is", "source": "rule"}
    try:
        return mod.size_check(unit)
    except control.IntegrityError:
        raise
    except Exception as exc:
        log(f"jev (a) error: {exc}")
        return {"action": "run_as_is", "source": "rule"}


def jev_triage(unit: dict, output: str, attempt: int, at_last_rung: bool) -> dict:
    """Item 2b. Never raises; falls back to the rule when Jev is unavailable."""
    mod = _load_jev()
    if mod is None:
        return {"action": "retry_same", "source": "rule"}
    try:
        return mod.triage(unit, output, attempt, MAX_ATTEMPTS, at_last_rung)
    except control.IntegrityError:
        raise
    except Exception as exc:
        log(f"jev (b) error: {exc}")
        return {"action": "retry_same", "source": "rule"}


def jev_review_gate(unit: dict, diff: str, tests_pass: bool) -> dict:
    """Item 2c. Never raises; on any problem the reviewer runs as before."""
    mod = _load_jev()
    if mod is None:
        return {"skip": False, "source": "rule", "reason": "unavailable"}
    try:
        return mod.review_gate(unit, diff, tests_pass)
    except Exception as exc:
        log(f"jev (c) error: {exc}")
        return {"skip": False, "source": "rule", "reason": f"error: {exc}"}


def jev_note_miss(reason: str) -> list:
    """Item 4: attribute a nightly failure / fix unit to recent Jev skips."""
    mod = _load_jev()
    if mod is None:
        return []
    try:
        return mod.note_miss_recent(reason)
    except Exception as exc:
        log(f"jev miss-note error: {exc}")
        return []


def jev_note_merged(unit: dict) -> None:
    """Item 4: track merged-unit tokens for the (a)+(b) median comparison."""
    mod = _load_jev()
    if mod is None:
        return
    try:
        mod.record_merged(unit.get("id", ""), unit_tokens(unit))
    except Exception as exc:
        log(f"jev merged-note error: {exc}")


def go_pin() -> str:
    try:
        return (REPO / ".go-version").read_text().strip()
    except Exception:
        return ""


def quality_gate(wt: Path, unit: dict, state: dict, base: str) -> dict:
    """Run items 1-3 for the attempt in ``wt``. Never raises.

    Returns the quality report (``{"ok", "reason", "checks", "coverage",
    "fidelity"}``), or a permissive stub if the module is missing so a broken
    import cannot wedge the pipeline.
    """
    mod = _load_quality()
    if mod is None:
        return {"ok": False, "reason": "quality module unavailable",
                "checks": {}, "coverage": None, "fidelity": "unknown"}
    env = {"PATH": f"{TOOLBIN}:{os.environ.get('PATH','')}"}
    pin = go_pin()
    if pin:
        env["GOTOOLCHAIN"] = f"go{pin}"
    try:
        return mod.evaluate(wt, base, unit, env=env, floor=COVERAGE_FLOOR)
    except Exception as exc:
        return {"ok": False, "reason": f"quality gate error: {exc}",
                "checks": {}, "coverage": None, "fidelity": "unknown"}


# --------------------------------------------------------------------------
# Hermes agent calls
# --------------------------------------------------------------------------

# Skill names as registered (Hermes resolves -s by plain name in the active
# profile's skills/ dir, not by path).
SKILL_NAME = {"builder": "unit-builder", "reviewer": "unit-reviewer",
              "planner": "unit-planner", "auditor": "unit-auditor"}


class BudgetDenied(RuntimeError):
    pass


class DeliveryUnavailable(RuntimeError):
    pass


def paid_allowed(state: dict, unit: dict | None, role: str) -> bool:
    rollover(state)
    if STOP_FILE.exists() or state.get("dispatch_disabled"):
        return False
    if int(state.get("provider_errors", 0)) >= 3 or float(state.get("provider_retry_at", 0)) > time.time():
        return False
    if int(state.get("tokens_today", 0)) >= DAILY_TOKEN_CAP:
        return False
    if int(state.get("merged_today", 0)) >= effective_merge_cap(state):
        return False
    if unit and int(unit.get("tokens", 0)) >= PER_UNIT_TOKEN_CAP:
        return False
    return True


def admit_paid(state: dict, unit: dict | None, role: str, *, limit=None) -> str:
    if not paid_allowed(state, unit, role):
        raise BudgetDenied(f"{role}: STOP, provider pause or budget admission denied")
    reservations = state.setdefault("reservations", {})
    used = int(unit.get("tokens", 0)) if unit else 0
    uid = unit.get("id", "") if unit else ""
    allowance = min(PER_UNIT_TOKEN_CAP - used, AUDIT_TOKEN_CAP if role == "audit" else PER_UNIT_TOKEN_CAP)
    if limit is not None:
        allowance = min(allowance, limit)
    held = sum(r["reserved_tokens"] for r in reservations.values())
    held_unit = sum(r["reserved_tokens"] for r in reservations.values() if uid and r.get("unit") == uid)
    if allowance <= 0 or held + int(state.get("tokens_today", 0)) + allowance > DAILY_TOKEN_CAP or used + held_unit + allowance > PER_UNIT_TOKEN_CAP:
        raise BudgetDenied(f"{role}: in-flight allowance exceeds a cap")
    rid = control.identity()
    rec = {"record_type": "reservation", "run_id": rid, "role": role,
           "unit": uid, "reserved_tokens": allowance, "ts_start": now()}
    control.append_record(STATE_DIR / "runs.jsonl", rec)
    reservations[rid] = rec
    write_json(STATE_JSON, state)
    return rid


def release_paid(state: dict, rid: str) -> None:
    state.setdefault("reservations", {}).pop(rid, None)


def note_provider(state: dict, failed: bool, uid: str = "") -> None:
    if failed:
        count = int(state.get("provider_errors", 0)) + 1
        state["provider_errors"] = count
        state["provider_retry_at"] = time.time() + min(900, 30 * 2 ** min(count - 1, 5))
        event(state, f"provider outage {count}/3; retry with backoff; dispatch {'paused' if count >= 3 else 'deferred'}")
        telemetry_event("provider_error", uid, f"provider backoff; consecutive={count}")
    else:
        state["provider_errors"] = 0
        state["provider_retry_at"] = 0
    write_json(STATE_JSON, state)


def bootstrap_accounting(state: dict, roadmap: dict) -> None:
    if state.get("accounting_version") == 2:
        return
    summary = control.accounting(control.ledger_records(STATE_DIR), state["day"], TIMEOUT_FALLBACK_TOKENS)
    per = {uid: max(0, int(u.get("tokens", 0)) - summary["unit_tokens"].get(uid, 0)) for uid, u in roadmap.items()}
    control.append_record(STATE_DIR / "runs.jsonl", {
        "record_type": "baseline", "day": state["day"], "ts": now(),
        "tokens_today": max(0, state["tokens_today"] - summary["tokens_today"]),
        "merged_today": max(0, state["merged_today"] - summary["merged_today"]),
        "unit_tokens": {uid: value for uid, value in per.items() if value},
        "unit_attempts": {uid: int(u.get("attempts", 0)) for uid, u in roadmap.items()},
        "source": "validated pre-maintenance counters; historical ledger predates complete coverage"})
    state["accounting_version"] = 2
    write_json(STATE_JSON, state)


def hermes_run(profile: str, model: str, prompt: str, toolsets: str,
               cwd: Path, tag: str, timeout: int, *, unit: str = "", attempt=None,
               role: str = "", outcome: str = "other", state=None, budget_unit=None) -> tuple[int, str, dict]:
    role = role or _role_for_profile(profile)
    if state is None:
        raise control.IntegrityError("paid role missing accounting state")
    try:
        rid = admit_paid(state, budget_unit, role)
    except BudgetDenied as exc:
        return 75, str(exc), {"total_tokens": 0, "api_calls": 0, "admission_denied": True}
    usage = LOG_DIR / f"{tag}-{rid}.usage.json"
    env = {"HERMES_HOME": str(PROFILE_HOME[profile])}
    cmd = [HERMES, "-z", prompt, "--usage-file", str(usage), "-m", model,
           "--provider", PROVIDER, "--reasoning", "low", "-t", toolsets,
           "-s", SKILL_NAME[profile], "--in", str(cwd), "--accept-hooks"]
    ts_start = now()
    rc, out = sh(cmd, cwd=cwd, timeout=timeout, env=env)
    data = read_json(usage, {}) or {}
    explicit_zero = data.get("api_calls") == 0 and data.get("total_tokens") == 0
    charge = usage_tokens(data) if data else TIMEOUT_FALLBACK_TOKENS
    if charge <= 0 and not explicit_zero:
        charge = TIMEOUT_FALLBACK_TOKENS
    data["accounted_tokens"] = charge
    outage = control.provider_error(rc, out)
    log_model_run(role, model, unit, attempt, rc,
                  "provider_error" if outage else outcome if outcome != "other" else _outcome_for_rc(rc),
                  data, profile, toolsets, ts_start, now(), run_id=rid, charged_tokens=charge)
    allowance = state["reservations"][rid]["reserved_tokens"]
    release_paid(state, rid)
    if charge > allowance:
        raise control.IntegrityError("paid role exceeded reserved token allowance")
    if outage or rc == 0:
        note_provider(state, outage, unit)
    return rc, out, data


def _role_for_profile(profile: str) -> str:
    return {"builder": "builder", "reviewer": "reviewer",
            "planner": "planner", "auditor": "audit"}.get(profile, "other")


def _outcome_for_rc(rc) -> str:
    if rc is None:
        return "other"
    if rc == 124:
        return "timeout"
    if rc != 0:
        return "provider_error"
    return "other"


def log_model_run(role: str, model: str, unit: str, attempt, rc, outcome: str,
                  usage: dict, profile: str = "", toolsets: str = "",
                  ts_start: str = "", ts_end: str = "", *, run_id="", charged_tokens=None,
                  provider_override="") -> None:
    mod = _load_telemetry()
    if mod is None:
        raise control.IntegrityError("required accounting ledger unavailable")
    rec = mod.build_run(
        ts_start=ts_start or now(), ts_end=ts_end or now(), role=role, model=model,
        unit=unit or "", attempt=attempt, rc=rc, outcome=outcome, usage=usage or {},
        provider=provider_override or PROVIDER, flags=mod.default_flags(profile, toolsets,
                    session=str((usage or {}).get("session_id") or "")))
    rec["run_id"] = run_id or control.identity()
    rec["record_type"] = "run"
    if charged_tokens is not None:
        rec["charged_tokens"] = charged_tokens
    mod.log_run(rec)


def usage_tokens(usage: dict) -> int:
    if "accounted_tokens" in usage:
        return int(usage["accounted_tokens"])
    for key in ("total_including_auxiliary", "total_tokens"):
        val = usage.get(key)
        if isinstance(val, dict):
            val = val.get("total_tokens")
        if isinstance(val, int):
            return val
    return int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0) + int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)


def kill_process_group(proc, grace: int = TERM_GRACE) -> str:
    """Stop a runaway agent run without losing its accounting.

    SIGKILL on the process group (the old behaviour) prevents Hermes from
    writing ``--usage-file``, so a killed run was recorded as 0 tokens - which
    is exactly when a unit is burning budget. Send SIGTERM first, give the
    agent ``grace`` seconds to flush the usage file, then SIGKILL whatever is
    left. Returns ``term`` or ``kill`` for the log.
    """
    pgid = None
    with_suppress(lambda: None)
    try:
        pgid = os.getpgid(proc.pid)
    except Exception:
        pgid = None
    if pgid is None:
        with_suppress(lambda: proc.kill())
        return "kill"
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return "term"
    try:
        proc.wait(timeout=grace)
        return "term"
    except subprocess.TimeoutExpired:
        pass
    with_suppress(lambda: os.killpg(pgid, signal.SIGKILL))
    with_suppress(lambda: proc.wait(timeout=30))
    return "kill"


def tokens_from_state_db(profile: str, marker: str = "") -> int:
    """Tokens of the session a killed run left in the profile's state.db.

    Fallback for a run killed before ``--usage-file`` landed. The run's session
    is found by a marker unique to its brief (``UNIT BRIEF <id>``), so a
    concurrent run's spend is never charged to it. Returns 0 when nothing is
    found; the caller then applies a pessimistic estimate.
    """
    db = PROFILE_HOME.get(profile, Path()) / "state.db"
    if not db.exists() or not marker:
        return 0
    con = None
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True, timeout=20)
        row = con.execute(
            "SELECT session_id FROM messages WHERE content LIKE ? "
            "ORDER BY rowid DESC LIMIT 1", (f"%{marker}%",)).fetchone()
        if not row:
            return 0
        sid = row[0]
        cols = {r[1] for r in con.execute("PRAGMA table_info(sessions)")}
        fields = [c for c in ("input_tokens", "output_tokens", "cache_read_tokens",
                              "reasoning_tokens") if c in cols]
        if not fields:
            return 0
        expr = " + ".join(f"COALESCE({c},0)" for c in fields)
        row = con.execute(f"SELECT {expr} FROM sessions WHERE id = ?", (sid,)).fetchone()
        return int(row[0]) if row and row[0] else 0
    except Exception:
        return 0
    finally:
        if con is not None:
            with_suppress(con.close)


def normalize_verdict(raw) -> str:
    return raw if raw in ("pass", "fix", "block") else "unavailable"


def reviewer_model_for(author: str) -> str:
    """A reviewer never shares the author's model family."""
    return MODEL["deepseek"] if author in (MODEL["luna"], MODEL["sol"]) else MODEL["luna"]


# --------------------------------------------------------------------------
# Worktrees
# --------------------------------------------------------------------------

def unit_branch(unit: dict) -> str:
    return unit.get("branch") or f"unit/{unit['id']}"


def worktree_path(unit: dict) -> Path:
    return WORK / unit["id"]


def ensure_worktree(unit: dict) -> Path:
    path = worktree_path(unit)
    branch = unit_branch(unit)
    git("fetch", "origin")
    if path.exists() and (path / ".git").exists():
        # Reused worktree. A retry continues from the previous attempt's commits
        # when there are any; with none, re-point the branch at the current base
        # so the worktree actually contains the pipeline (scripts/check.sh).
        ahead = git_out("rev-list", "--count", f"{BASE_REF}..HEAD", cwd=path)
        head = git_out("rev-parse", "HEAD", cwd=path)
        base = git_out("rev-parse", BASE_REF)
        if ahead == "0" and head != base:
            git("checkout", "-B", branch, BASE_REF, cwd=path)
            log(f"{unit['id']}: re-pointed stale worktree at {BASE_REF}")
        return path
    if path.exists():
        shutil.rmtree(path)
    rc, out = git("worktree", "add", "-B", branch, str(path), BASE_REF)
    if rc != 0:
        raise RuntimeError(f"cannot create worktree for {unit['id']}: {out}")
    return path


def drop_worktree(unit: dict) -> None:
    path = worktree_path(unit)
    git("worktree", "remove", "--force", str(path))
    with_suppress(lambda: shutil.rmtree(path))


# --------------------------------------------------------------------------
# Briefs
# --------------------------------------------------------------------------

def unit_block(unit: dict) -> str:
    return "\n".join(dump_unit_yaml(unit).strip().splitlines())


def builder_brief(unit: dict, attempt: int, model: str, feedback: str) -> str:
    paths = "\n".join(f"- {p}" for p in unit.get("paths", [])) or "- (none listed)"
    tests = "\n".join(f"- {t}" for t in unit.get("tests", [])) or "- scripts/check.sh"
    acc = "\n".join(f"- {a}" for a in unit.get("acceptance", [])) or "- (none listed)"
    fixtures = "\n".join(f"- {f}" for f in unit.get("fixtures", [])) or "- (none)"
    return f"""UNIT BRIEF {unit['id']} - {unit.get('title','')}
attempt {attempt} of {MAX_ATTEMPTS} (model {model})

## Unit entry (from units.yaml)
{unit_block(unit)}

## Paths you may touch (nothing else)
{paths}

## Tests to run
{tests}

## Acceptance (all must hold)
{acc}

## Fixtures / evidence
{fixtures}

## Fidelity notes
{unit.get('fidelity_notes','') or '(none)'}

## Previous attempt feedback
{feedback or '(first attempt - nothing to repair)'}

## Rules
Read only this brief and the listed paths; never explore the wider repository.
Write the tests first, from the fixtures above, and cite in each test the
evidence file the assertion comes from. Implement until they pass. Then run
`bash scripts/check.sh` in this worktree and fix every failure it reports -
it is the only gate. Commit with `unit({unit['id']}): <what changed>`.
Write `docs/units/{unit['id']}.md` (30 lines maximum): what works, what is
guessed, how to run it. Where evidence is missing, build from fixtures and
label it "fidelity: guessed". Never edit AGENTS.md, skills, CI or ops/.
Never ask questions; choose the safest reasonable option and record it.

## Quality safeguards (the pipeline enforces these; a failure re-runs the unit)
1. Tests must exercise the change: with your implementation removed the new
   tests must FAIL. A test that passes without the code is rejected as
   "tests do not exercise the change".
2. Coverage: `go test -cover` on the changed files must reach {COVERAGE_FLOOR:.0f}%. Below
   that, add a line to the unit doc beginning `coverage-exempt:` saying why it
   cannot be covered, or extend the tests.
3. Evidence: every new test cites the evidence file or fixture its expected
   values came from, in a comment. Tests built on guessed behaviour are allowed
   only when the unit doc says "fidelity: guessed".
Finish with exactly one JSON line: {{"status":"done|partial","notes":"..."}}
"""


def reviewer_brief(unit: dict, diff: str, model: str) -> str:
    acc = "\n".join(f"- {a}" for a in unit.get("acceptance", []))
    return f"""REVIEW {unit['id']} - {unit.get('title','')}
reviewer model {model}; you are a different family from the author.

## Acceptance bullets the diff must satisfy
{acc}

## Unified diff
{diff}

Output ONLY the JSON verdict object described in your skill.
"""


def planner_brief(unit: dict, mode: str, design_text: str) -> str:
    if mode == "split":
        why = unit.get("reason", "")
        return f"""PLAN-SPLIT {unit['id']} - {unit.get('title','')}

This unit did not deliver: {why}

Current entry:
{unit_block(unit)}

Split it into smaller units so a builder can succeed. Rules:
- each replacement entry is size S or M, never L;
- at most {SPLIT_MAX_UNITS} entries;
- the union of their paths must stay inside the current entry's paths;
- keep the same evidence and fidelity notes; give each entry its own id
  ({unit['id']}a, {unit['id']}b, ...) and its own depends_on.
Output only the YAML block.
"""
    if mode == "rewrite":
        return f"""PLAN-REWRITE {unit['id']} - {unit.get('title','')}

This unit was parked. Recorded reason:
{unit.get('reason','')}

Current entry:
{unit_block(unit)}

Shrink or split it so a builder can succeed, and output the replacement
entries. Output only the YAML block.
"""
    return f"""PLAN-PROMOTE {unit['id']} - {unit.get('title','')}

Design document: {unit.get('design_doc','')}

{design_text}

Promote this design into implementation entries. Split it if it is size L.
Output only the YAML block.
"""


# --------------------------------------------------------------------------
# check.sh and the merge queue
# --------------------------------------------------------------------------

def run_check(wt: Path) -> tuple[int, str]:
    rc, out = sh(["bash", "scripts/check.sh"], cwd=wt, timeout=CHECK_TIMEOUT)
    return rc, out


def tail(text: str, lines: int = 60) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def current_diff(wt: Path) -> str:
    out = git_out("diff", f"{BASE_REF}...HEAD", "--unified=3", cwd=wt)
    if not out:
        out = git_out("diff", BASE_REF, "--unified=3", cwd=wt)
    lines = out.splitlines()
    if len(lines) > DIFF_LINE_CAP:
        lines = lines[:DIFF_LINE_CAP] + [f"... [diff truncated at {DIFF_LINE_CAP} lines]"]
    return "\n".join(lines)


def changed_files(wt: Path) -> list:
    """Every path the attempt changed, committed or not.

    Working-tree changes are included because the guard runs before
    ``commit_if_dirty``: an uncommitted edit to ``ops/`` must still fail the
    attempt, not be committed and then caught.
    """
    files = set()
    for args in (("diff", "--name-only", f"{BASE_REF}...HEAD"),
                 ("diff", "--name-only", "HEAD"),
                 ("ls-files", "--others", "--exclude-standard")):
        for ln in git_out(*args, cwd=wt).splitlines():
            ln = ln.strip()
            if ln:
                files.add(ln)
    return sorted(files)


def guard_violations(files, allowed, unit_id: str = "") -> list:
    """Paths a builder may not touch, or that fall outside the unit's list.

    Two rules: the repository's protected paths (ops/, CI, skills, AGENTS.md,
    scripts/check.sh) are never a builder's to change; and anything the unit
    did not list is out of scope. The unit's own delivery note
    (``docs/units/<unit_id>.md``) is always permitted: the brief requires the
    builder to write it, so a unit whose ``paths`` omit it must not be rejected
    for doing so. Returns a list of ``(path, reason)``.
    """
    allowed = [str(p) for p in (allowed or [])]
    own_doc = f"docs/units/{unit_id}.md" if unit_id else ""
    bad = []
    for f in files:
        if any(f == p or f.startswith(p) for p in PROTECTED_FILES) or \
           any(f.startswith(p) for p in PROTECTED_PREFIXES):
            bad.append((f, "protected path"))
            continue
        if own_doc and f == own_doc:
            continue
        ok = False
        for a in allowed:
            a = a.rstrip("*").rstrip("/")
            if f == a or f.startswith(a + "/"):
                ok = True
                break
        if not ok:
            bad.append((f, "outside the unit's listed paths"))
    return bad


def diff_touches_sensitive(diff: str) -> bool:
    return any(f"a/{p}" in diff or f"b/{p}" in diff for p in SENSITIVE)


def commit_if_dirty(wt: Path, unit: dict, message: str = "") -> bool:
    status = git_out("status", "--porcelain", cwd=wt)
    if not status:
        return False
    git("add", "-A", cwd=wt)
    git("-c", "user.name=PapaBill1234",
        "-c", "user.email=PapaBill1234@users.noreply.github.com",
        "commit", "-m", message or f"unit({unit['id']}): builder output", cwd=wt)
    return True


def discard_changes(wt: Path, unit: dict) -> None:
    """Throw the attempt's changes away and return the worktree to the base.

    Used when the diff-guard rejects a run: a builder that edited ``ops/`` or
    wandered outside its listed paths must not have any of that published, and
    the next attempt must start from a clean branch rather than the rejected
    work.
    """
    git("rebase", "--abort", cwd=wt)
    git("reset", "--hard", BASE_REF, cwd=wt)
    git("clean", "-fdx", cwd=wt)
    log(f"{unit['id']}: discarded the rejected attempt's changes")


def push_and_open_pr(unit: dict, wt: Path, check_out: str, state: dict) -> int:
    branch = unit_branch(unit)
    rc, out = git("push", "-u", "origin", f"HEAD:refs/heads/{branch}", cwd=wt, timeout=300)
    if rc != 0:
        raise RuntimeError(f"push failed: {out[-800:]}")
    title = f"unit({unit['id']}): {unit.get('title','')}"
    body = (f"Automated unit delivery from the ops pipeline.\n\n"
            f"- unit: `{unit['id']}` - {unit.get('title','')}\n"
            f"- attempts: {unit.get('attempts',0)}\n"
            f"- tokens (this unit): {unit.get('tokens',0)}\n\n"
            f"### scripts/check.sh\n```\n{tail(check_out, 40)}\n```\n")
    body_file = BRIEF_DIR / f"{unit['id']}.pr.md"
    body_file.write_text(body)
    rc, out = sh(["gh", "pr", "create", "--repo", GH_REPO, "--base", "main",
                  "--head", branch, "--title", title, "--body-file", str(body_file)],
                 cwd=wt, timeout=180)
    m = re.search(r"/pull/(\d+)", out)
    if rc != 0 or not m:
        rc, out = sh(["gh", "pr", "list", "--repo", GH_REPO, "--head", branch,
                      "--json", "number", "--jq", ".[0].number"], cwd=wt, timeout=120)
        m = re.search(r"(\d+)", out)
    if not m:
        raise RuntimeError(f"cannot open PR: {out[-800:]}")
    return int(m.group(1))


def review_fallback(primary: str, author: str) -> str:
    # Third family prevents an outage retry from becoming self-review.
    for candidate in (MODEL["deepseek"], MODEL["luna"], "claude-sonnet-5.5"):
        if control.model_family(candidate) not in (control.model_family(primary), control.model_family(author)):
            return candidate
    return ""


def second_reviewer_model(author: str, primary: str) -> str:
    """Choose a sensitive-path reviewer from a family unlike both prior roles."""
    for candidate in (MODEL["sol"], MODEL["luna"], MODEL["deepseek"], "claude-sonnet-5.5"):
        family = control.model_family(candidate)
        if family not in (control.model_family(author), control.model_family(primary)):
            return candidate
    return ""


def validated_review(unit: dict, wt: Path, state: dict, model: str, slot: str) -> tuple[str, str, int]:
    head = git_out("rev-parse", "HEAD", cwd=wt)
    if not head:
        return "unavailable", "cannot identify reviewed head", 0
    diff = git_out("diff", f"{BASE_REF}...HEAD", cwd=wt)
    author = unit.get("model") or MODEL["luna"]
    unit.pop(slot + "_head", None)
    unit[slot + "_verdict"] = "unavailable"
    unit["review_admission_denied"] = False
    total, finding = 0, "review unavailable"
    for index in range(2):
        chosen = model if index == 0 else review_fallback(model, author)
        if not chosen:
            break
        prompt = reviewer_brief(unit, diff, chosen) + f"\nExact reviewed head: {head}\nRead-only: never write files.\n"
        rc, out, usage = hermes_run("reviewer", chosen, prompt, "file", wt,
                    f"{unit['id']}-{slot}", 900, unit=unit["id"], attempt=unit.get("attempts"),
                    role="reviewer", state=state, budget_unit=unit)
        if usage.get("admission_denied"):
            unit["review_admission_denied"] = True
        tokens = usage_tokens(usage)
        # Account before a possible fallback, so retry admission sees its spend.
        add_tokens(state, unit, tokens)
        total += tokens
        write_json(STATE_JSON, state)
        verdict, finding = control.review_result(rc, out)
        dirty = git_out("status", "--porcelain", cwd=wt)
        if git_out("rev-parse", "HEAD", cwd=wt) != head or dirty:
            verdict, finding = "unavailable", "reviewer changed reviewed checkout"
        if control.model_family(chosen) == control.model_family(author):
            verdict, finding = "unavailable", "review model shares author family"
        review_id = control.identity()
        control.atomic_json(LOG_DIR / f"{unit['id']}-{slot}-{review_id}.verdict.json",
            {"unit": unit["id"], "head": head, "model": chosen, "verdict": verdict,
             "findings": finding, "rc": rc, "ts": now()})
        if verdict != "unavailable":
            unit[slot + "_id"] = review_id
            unit[slot + "_head"] = head
            unit[slot + "_model"] = chosen
            unit[slot + "_verdict"] = verdict
            return verdict, finding, total
        if usage.get("admission_denied"):
            break
    return "unavailable", finding, total


def approval_valid(unit: dict, slot: str, head: str) -> bool:
    rid = unit.get(slot + "_id", "")
    if not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", rid):
        return False
    rec = read_json(LOG_DIR / f"{unit['id']}-{slot}-{rid}.verdict.json", {})
    valid = (rec.get("unit") == unit["id"] and rec.get("head") == head and
             rec.get("rc") == 0 and rec.get("verdict") == "pass" and
             rec.get("model") == unit.get(slot + "_model"))
    valid = valid and control.model_family(rec.get("model", "")) != control.model_family(unit.get("model") or MODEL["luna"])
    return bool(valid)


def ensure_reviewed(unit: dict, wt: Path, state: dict) -> bool:
    head = git_out("rev-parse", "HEAD", cwd=wt)
    verdict, findings = unit.get("review_verdict"), ""
    if unit.get("review_head") != head or verdict != "pass" or not approval_valid(unit, "review", head):
        verdict, findings, _ = run_review(unit, wt, state, unit.get("model") or MODEL["luna"])
    sensitive = diff_touches_sensitive(git_out("diff", f"{BASE_REF}...HEAD", cwd=wt))
    if verdict == "pass" and sensitive:
        if unit.get("review2_head") != head or unit.get("review2_verdict") != "pass" or not approval_valid(unit, "review2", head):
            second, details, _ = run_second_review(unit, wt, state)
        else:
            second, details = "pass", ""
        if second != "pass":
            verdict, findings = second, details
    telemetry_event("review_verdict", unit["id"], f"review verdict={verdict}", verdict=verdict, head=head[:12])
    if verdict == "unavailable" and (unit.get("review_admission_denied") or int(state.get("provider_errors", 0))):
        unit["status"], unit["reason"] = "pr_open", "review deferred: admission or provider backoff/pause"
        return False
    if verdict != "pass":
        unit["feedback"] = "Reviewer decision to repair:\n" + findings
        unit["reason"] = (f"reviewer {verdict}: " + findings.replace("\n", " | "))[:400]
        if verdict == "fix" and int(unit.get("review_rounds", 0)) < 1 and int(unit.get("attempts", 0)) < MAX_ATTEMPTS:
            unit["review_rounds"] = int(unit.get("review_rounds", 0)) + 1
            unit["status"] = "todo"
        else:
            unit["status"] = "parked"
            telemetry_event("parked", unit["id"], unit["reason"])
        event(state, f"{unit['id']}: review {verdict} -> {unit['status']}")
        return False
    if not head or git_out("rev-parse", "HEAD", cwd=wt) != head or git_out("status", "--porcelain", cwd=wt):
        unit["status"], unit["reason"] = "parked", "unreviewed changed head"
        return False
    return True


def run_review(unit: dict, wt: Path, state: dict, author_model: str) -> tuple[str, str, int]:
    return validated_review(unit, wt, state, reviewer_model_for(author_model), "review")


def run_second_review(unit: dict, wt: Path, state: dict) -> tuple[str, str, int]:
    model = second_reviewer_model(unit.get("model") or MODEL["luna"], unit.get("review_model", ""))
    if not model:
        return "unavailable", "no independent sensitive-path reviewer family", 0
    return validated_review(unit, wt, state, model, "review2")


def strip_required_actions_check(state: dict) -> None:
    # Kept as a compatibility symbol for callers outside this module. It has
    # no authority and performs no GitHub mutation.
    event(state, "branch protection mismatch: protection changes require owner maintenance")


def actions_note(pr: int, tail_len: int = 10) -> str:
    """Best-effort diagnostic snapshot of the PR head's Actions runs.

    Written to ``ACTIONS_NOTE.md`` so the reason a run never went green is
    recorded instead of guessed. Never raises and never waits: a few API calls,
    then it gives up.
    """
    lines = [f"## PR #{pr}", ""]
    rc, out = sh(["gh", "pr", "view", str(pr), "--repo", GH_REPO, "--json",
                  "headRefOid,mergeStateStatus"], timeout=90)
    if rc != 0:
        return "\n".join(lines + ["- cannot read the PR head", ""])
    try:
        head = json.loads(out)["headRefOid"]
    except Exception:
        return "\n".join(lines + ["- cannot parse the PR head", ""])
    lines.append(f"- head: `{head[:12]}`")
    rc, out = sh(["gh", "api", f"repos/{GH_REPO}/commits/{head}/check-runs",
                  "--jq", r'[.check_runs[] | "\(.name) \(.status) \(.conclusion) id=\(.id)"] | join("\n")'],
                 timeout=90)
    runs = [ln for ln in (out or "").splitlines() if ln.strip()] if rc == 0 else []
    lines += ["- check runs: " + ("; ".join(runs) if runs else "(none)"), ""]
    for rid in re.findall(r"id=(\d+)", "\n".join(runs))[:2]:
        rc, ann = sh(["gh", "api", f"repos/{GH_REPO}/check-runs/{rid}/annotations",
                      "--jq", r'[.[] | "\(.annotation_level): \(.message)"] | join("\n")'],
                     timeout=90)
        if rc == 0 and (ann or "").strip():
            lines += [f"- annotation for check-run {rid}:", "```",
                      tail(ann, tail_len), "```", ""]
    rc, out = sh(["gh", "api", f"repos/{GH_REPO}/actions/runs",
                  "-f", "head_sha=" + head, "--jq",
                  r'[.workflow_runs[] | "\(.id) \(.status) \(.conclusion) \(.name)"] | join("\n")'],
                 timeout=90)
    if rc == 0 and (out or "").strip():
        lines += ["- workflow runs for this head:", "```", tail(out, tail_len), "```", ""]
    return "\n".join(lines)


def append_actions_note(pr: int, reason: str, state: dict) -> None:
    """Append the advisory-CI outcome for a PR to ACTIONS_NOTE.md."""
    path = STATE_DIR / "ACTIONS_NOTE.md"
    header = ("# GitHub Actions notes (advisory only)\n\n"
              "Actions is not the merge gate: `scripts/check.sh` on the exact\n"
              "rebased head, under the merge lock, is. This file records what\n"
              "CI did for the record, not as a decision.\n\n")
    if not path.exists():
        path.write_text(header)
    try:
        body = actions_note(pr)
    except Exception as exc:
        body = f"- note collection failed: {exc}\n"
    with path.open("a") as fh:
        fh.write(f"\n### {now()}  {reason}\n\n{body}\n")
    log(f"PR #{pr}: Actions note recorded ({reason})")


def record_actions_observation() -> None:
    """One-off background diagnosis: why the cancelled runs never started.

    Reads the cancelled/cancelled-by-supersession runs, their annotations and
    the workflow's concurrency settings, and writes findings to
    ``ACTIONS_NOTE.md``. Best effort; called once by hand (not every cycle).
    """
    lines = ["# GitHub Actions investigation", "",
             f"observed: {now()}", ""]
    rc, out = sh(["gh", "run", "list", "--repo", GH_REPO, "--limit", "30",
                  "--json", "databaseId,headBranch,status,conclusion,createdAt,event"],
                 timeout=120)
    runs = []
    if rc == 0:
        try:
            runs = json.loads(out or "[]")
        except Exception:
            runs = []
    bad = [r for r in runs if str(r.get("conclusion", "")).lower() in
           ("cancelled", "timed_out", "startup_failure", "failure")]
    lines += [f"- recent runs: {len(runs)}; cancelled/failed: {len(bad)}", ""]
    for r in bad[:6]:
        rid = r.get("databaseId")
        lines += [f"## run {rid} ({r.get('headBranch')}) {r.get('status')}/{r.get('conclusion')}",
                  ""]
        rc, jb = sh(["gh", "api", f"repos/{GH_REPO}/actions/runs/{rid}/jobs",
                     "--jq", r'[.jobs[] | "\(.id) \(.name) \(.status) \(.conclusion) steps=\(.steps|length) runner=\(.runner_name // "none")"] | join("\n")'],
                    timeout=90)
        if rc == 0 and (jb or "").strip():
            lines += ["```", tail(jb, 8), "```"]
        for jid in re.findall(r"^(\d+)", (jb or ""), re.M):
            rc, ann = sh(["gh", "api", f"repos/{GH_REPO}/check-runs/{jid}/annotations",
                          "--jq", r'[.[] | "\(.annotation_level): \(.message)"] | join("\n")'],
                         timeout=90)
            if rc == 0 and (ann or "").strip():
                lines += ["annotations:", "```", tail(ann, 10), "```"]
        lines.append("")
    wf = REPO / ".github/workflows/go-security.yml"
    lines += ["## workflow concurrency settings", "",
              "```", (wf.read_text() if wf.exists() else "(workflow not found)"), "```", ""]
    lines += ["## status page", ""]
    rc, sp = sh(["curl", "-s", "https://www.githubstatus.com/api/v2/status.json"],
                timeout=60)
    lines += ["```", (sp or "(unavailable)").strip()[:800], "```", ""]
    (STATE_DIR / "ACTIONS_NOTE.md").write_text("\n".join(lines) + "\n")
    log("ACTIONS_NOTE.md written")


def ci_advisory(pr: int, state: dict, reason: str = "") -> tuple[bool, str]:
    """Observe CI; never let it decide.

    Returns (clean, detail). ``clean`` is advisory only and its False is never
    a reason to refuse a merge - the caller logs it and proceeds. Waits
    ``CI_ADVISORY_WAIT`` seconds at most for a run that is still going, and
    treats queued/cancelled/missing as 'no opinion'.
    """
    deadline = time.time() + (CI_ADVISORY_WAIT if CI_ADVISORY else 0)
    detail = "no CI run observed"
    while True:
        rc, out = sh(["gh", "pr", "view", str(pr), "--repo", GH_REPO, "--json",
                      "headRefOid"], timeout=90)
        sha = ""
        if rc == 0:
            with_suppress(lambda: None)
            try:
                sha = json.loads(out)["headRefOid"]
            except Exception:
                sha = ""
        if sha:
            rc, out = sh(["gh", "api", f"repos/{GH_REPO}/commits/{sha}/check-runs",
                          "--jq",
                          r'[.check_runs[] | "\(.name) \(.status) \(.conclusion)"] | join("\n")'],
                         timeout=90)
            runs = [ln for ln in (out or "").splitlines() if ln.strip()] if rc == 0 else []
            if runs:
                pending = [r for r in runs if r.split()[1].lower() != "completed"]
                if pending and time.time() < deadline:
                    time.sleep(15)
                    continue
                bad = [r for r in runs
                       if r.split()[2].lower() not in ("success", "neutral", "skipped")]
                detail = f"head {sha[:12]}: " + "; ".join(runs)
                if bad:
                    return False, detail
                return True, detail
        if time.time() >= deadline:
            return False, detail
        time.sleep(15)


def wait_for_checks(pr: int, timeout: int = CI_TIMEOUT) -> tuple[bool, str]:
    """Deprecated: kept only so nothing imports a missing name.

    The pipeline no longer blocks on Actions. Use ``ci_advisory``.
    """
    return ci_advisory(pr, {}, "legacy call")


def merge_queue(unit: dict, wt: Path, state: dict) -> bool:
    """Local gate, quality and independent review on the exact rebased head."""
    with (LOCK_DIR / "merge.lock").open("w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        if STOP_FILE.exists() or int(state.get("merged_today", 0)) >= effective_merge_cap(state):
            return False
        pr = int(unit.get("pr") or 0)
        if not pr:
            unit["status"], unit["reason"] = "parked", "merge has no PR identity"
            return False
        rc, out = git("fetch", "origin", "main", cwd=wt)
        if rc:
            event(state, f"{unit['id']}: fetch failed; merge deferred")
            return False
        rc, out = git("rebase", "origin/main", cwd=wt)
        if rc:
            git("rebase", "--abort", cwd=wt)
            unit["conflict_rounds"] = int(unit.get("conflict_rounds", 0)) + 1
            unit["reason"] = "rebase conflict: " + tail(out, 6)
            unit["status"] = "parked" if unit["conflict_rounds"] > 1 else "todo"
            return False
        violations = [] if GUARD_DISABLED else guard_violations(changed_files(wt), unit.get("paths"), unit["id"])
        if violations:
            unit["status"], unit["reason"] = "parked", "protected/scope paths changed in merge queue"
            return False
        rc, out = run_check(wt)
        control.atomic_text(LOG_DIR / f"{unit['id']}-rebase.check.log", out)
        if rc:
            unit["feedback"] = "scripts/check.sh failed after rebase:\n" + tail(out, 60)
            unit["reason"] = "check.sh failed after rebase"
            unit["status"] = "todo" if int(unit.get("attempts", 0)) < MAX_ATTEMPTS else "parked"
            record_history(unit, "rebase-check-fail")
            return False
        qreport = quality_gate(wt, unit, state, BASE_REF)
        if not qreport.get("ok"):
            unit["status"], unit["reason"] = "parked", "quality gate failed on rebased head"
            return False
        if not ensure_reviewed(unit, wt, state):
            return False
        head = git_out("rev-parse", "HEAD", cwd=wt)
        if unit.get("review_head") != head or unit.get("review_verdict") != "pass" or not approval_valid(unit, "review", head):
            unit["status"], unit["reason"] = "parked", "missing exact-head independent approval"
            return False
        branch = unit_branch(unit)
        if branch == "main" or not branch.startswith("unit/"):
            raise control.IntegrityError("unit merge attempted a non-unit branch")
        rc, out = git("push", "--force-with-lease", "origin", f"HEAD:refs/heads/{branch}", cwd=wt)
        if rc:
            unit["status"], unit["reason"] = "parked", "unit push refused: " + tail(out, 3)
            return False
        ci_clean, ci_detail = ci_advisory(pr, state, "pre-merge")
        append_actions_note(pr, "pre-merge advisory: " + ("green" if ci_clean else "not green"), state)
        if git_out("rev-parse", "HEAD", cwd=wt) != head or git_out("status", "--porcelain", cwd=wt):
            unit["status"], unit["reason"] = "parked", "head changed after review/gate"
            return False
        rc, out = sh(["gh", "pr", "merge", str(pr), "--repo", GH_REPO,
                      "--merge", "--match-head-commit", head, "--delete-branch"], timeout=300)
        if rc:
            unit["status"] = "parked"
            unit["reason"] = "merge refused: " + tail(out, 4).replace("\n", " | ")[:350]
            event(state, f"{unit['id']}: {unit['reason']}; protections unchanged")
            telemetry_event("parked", unit["id"], unit["reason"])
            return False
        control.append_record(STATE_DIR / "runs.jsonl", {"record_type": "delivery", "pr": pr,
            "unit": unit["id"], "head": head, "merged_at": now(), "count_merge": True})
        unit.update(status="merged", updated=now(), delivery_commit=head)
        state["merged_today"] = int(state.get("merged_today", 0)) + 1
        event(state, f"{unit['id']}: MERGED PR #{pr} (head {head[:12]}, gate=check.sh)")
        telemetry_event("merged", unit["id"], f"PR #{pr} merged", pr=pr, head=head[:12], tokens=unit.get("tokens", 0))
        jev_note_merged(unit)
        write_json(STATE_JSON, state)
        git("fetch", "origin", "main")
        drop_worktree(unit)
        return True


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------

def model_for_attempt(attempt: int) -> str:
    idx = min(max(attempt - 1, 0), len(LADDER) - 1)
    return MODEL[LADDER[idx]]


def rung_index(model: str) -> int:
    """Position of a model on the ladder (LAST match, so luna -> 1, not 0)."""
    for i in range(len(LADDER) - 1, -1, -1):
        if MODEL[LADDER[i]] == model:
            return i
    return -1


# Ladder strength order, weakest first. Escalating means the next one up.
_LADDER_ORDER = ["luna", "deepseek", "sol"]


def _next_stronger_model(unit: dict, attempt: int) -> str:
    """The model one step stronger than the unit's current one.

    Falls back to the model the attempt number would have used, so escalation
    is always a real change (never luna -> luna).
    """
    cur = unit.get("model", "")
    tag = next((k for k in _LADDER_ORDER if MODEL[k] == cur), "")
    if tag in _LADDER_ORDER:
        i = _LADDER_ORDER.index(tag)
        if i + 1 < len(_LADDER_ORDER):
            return MODEL[_LADDER_ORDER[i + 1]]
    return model_for_attempt(attempt)


def _apply_failure_triage(unit: dict, state: dict, output: str,
                          outcome_box: dict) -> None:
    """Item 2b: after a failed attempt, Jev may choose the next move.

    Jev only ever picks among options the remaining ladder allows; the
    MAX_ATTEMPTS / token-cap park rule still wins, so Jev cannot extend a
    unit's life. The default (Jev off or unusable) is the existing behaviour.
    """
    uid = unit["id"]
    attempt = int(unit.get("attempts", 1))
    at_last = rung_index(unit.get("model", "")) >= len(LADDER) - 1
    allowed = allowed_triage_names(attempt, at_last)
    tri = jev_triage(unit, output, attempt, at_last)
    action = tri.get("action", "retry_same") if tri.get("source") != "jev" else "retry_same"
    if action not in allowed:
        action = "retry_same"
    src = tri.get("source", "rule")
    log(f"{uid}: triage -> {action} (source={src}, "
        f"p={tri.get('probability')}, allowed={allowed})")

    if action == "park" or attempt >= MAX_ATTEMPTS or unit["tokens"] >= PER_UNIT_TOKEN_CAP:
        unit["status"] = "parked"
        if action == "park":
            unit["reason"] = (f"triage: park (source={src}) | " +
                              str(unit.get("reason", "")))[:400]
        event(state, f"{uid}: parked after {attempt} attempts "
                     f"({unit['tokens']} tokens)")
        telemetry_event("parked", uid, f"triage={action} after {attempt} attempts")
        return
    if action == "split_unit":
        unit["split_requested"] = True
        unit["status"] = "todo"
        telemetry_event("split", uid, f"triage: split_unit (source={src})")
        event(state, f"{uid}: triage -> split_unit")
        return
    if action == "shrink_unit":
        unit["shrinks"] = int(unit.get("shrinks", 0)) + 1
        unit["feedback"] = ("The failure looks structural, not transient: "
                            "implement the smallest coherent slice of this unit "
                            "and stay strictly inside the listed paths.")
        unit["status"] = "todo"
        event(state, f"{uid}: triage -> shrink_unit "
                     f"(shrink {unit['shrinks']})")
        return
    if action == "escalate_model":
        target = _next_stronger_model(unit, attempt)
        unit["model_override"] = target
        unit["status"] = "todo"
        event(state, f"{uid}: triage -> escalate_model ({target})")
        telemetry_event("escalated", uid, f"triage: escalate_model to {target}")
        return
    # retry_same
    unit["status"] = "todo"
    event(state, f"{uid}: triage -> retry_same (attempt {attempt})")


def allowed_triage_names(attempt: int, at_last_rung: bool) -> list:
    """The options the remaining ladder permits; mirrors ops/jev.py."""
    if attempt >= MAX_ATTEMPTS:
        return ["park"]
    opts = ["retry_same", "shrink_unit", "split_unit", "park"]
    if not at_last_rung:
        opts.append("escalate_model")
    return opts


def paths_overlap(a, b) -> bool:
    for x in a or []:
        for y in b or []:
            xs, ys = str(x).rstrip("*").rstrip("/"), str(y).rstrip("*").rstrip("/")
            if xs == ys or xs.startswith(ys + "/") or ys.startswith(xs + "/"):
                return True
    return False


_ADOPT_CHECK_CACHE: dict = {}


def _check_main_cached(head: str) -> tuple[int, str]:
    """check.sh on the repo checkout, once per HEAD. Adoption runs it for every
    already-delivered unit, which would otherwise cost one full gate per unit."""
    if head not in _ADOPT_CHECK_CACHE:
        _ADOPT_CHECK_CACHE[head] = run_check(REPO)
    return _ADOPT_CHECK_CACHE[head]


def adopt_branch_unit(unit: dict, state: dict) -> bool:
    """Adopt a unit whose delivery is already merged into origin/main.

    This is not a merge and does not pretend to be one: nothing is re-derived,
    no commit is invented. It looks up the merged PR for the unit's branch,
    verifies its merge commit is an ancestor of origin/main, runs
    scripts/check.sh on main as the gate, and records the PR. Used for the
    units the pre-pipeline kanban board delivered before this roadmap existed.
    """
    branch = unit.get("branch")
    if not branch:
        return False
    pr_rc, pr_out = sh(["gh", "pr", "list", "--repo", GH_REPO, "--head", branch,
                        "--state", "merged", "--json", "number,mergeCommit",
                        "--jq", ".[0] | .number, .mergeCommit.oid"],
                       cwd=REPO, timeout=120)
    pr, merge_oid = 0, ""
    if pr_rc == 0 and pr_out.strip():
        parts = pr_out.strip().split()
        if parts and parts[0].isdigit():
            pr = int(parts[0])
        if len(parts) > 1:
            merge_oid = parts[1].strip()
    if merge_oid:
        if git("merge-base", "--is-ancestor", merge_oid, "origin/main")[0] != 0:
            return False
    elif git("merge-base", "--is-ancestor", f"origin/{branch}", "origin/main")[0] != 0:
        return False
    head = git_out("rev-parse", "origin/main")
    rc, out = _check_main_cached(head)
    (LOG_DIR / f"{unit['id']}-adopt.check.log").write_text(out)
    if rc != 0:
        unit["reason"] = "delivery is in main but check.sh fails on main"
        unit["status"] = "parked"
        event(state, f"{unit['id']}: cannot adopt - check.sh fails on main")
        return True
    unit["status"] = "merged"
    unit["pr"] = pr
    unit["model"] = "adopted"
    unit["updated"] = now()
    unit["reason"] = (f"adopted: PR #{pr or '?'} ({branch}) merged into origin/main "
                      f"at {head[:12]}; check.sh green on main (no merge re-run)")
    # Adoption does NOT consume the daily merge budget: nothing was merged here.
    event(state, f"{unit['id']}: ADOPTED {branch} (PR #{pr or '?'} already in main "
                 f"{head[:12]})")
    return True


HISTORY_JSON = STATE_DIR / "history.json"


def load_history() -> dict:
    return read_json(HISTORY_JSON, {})


def record_history(unit: dict, outcome: str) -> None:
    hist = load_history()
    entry = {"outcome": outcome, "attempt": int(unit.get("attempts", 0)),
             "ts": now(), "revision_id": control.identity(), "unit": unit["id"],
             "run_id": unit.get("run_id", "")}
    control.append_record(STATE_DIR / "history.jsonl", entry)
    hist[unit["id"]] = entry
    write_json(HISTORY_JSON, hist)


QUALITY_JSON = STATE_DIR / "quality.json"


def rec_quality(unit: dict) -> None:
    """Record one unit's quality outcome for the STATE.md Quality section.

    Kept in its own store, separate from units.state.json, so the numbers
    survive a roadmap rewrite and can be aggregated across all units.
    """
    q = read_json(QUALITY_JSON, {})
    uid = unit["id"]
    prev = q.get(uid, {})
    coverages = list(prev.get("coverages", []))
    cov = (unit.get("quality") or {}).get("coverage")
    if cov is not None:
        coverages.append(cov)
    q[uid] = {
        "fidelity": (unit.get("quality") or {}).get("fidelity") or unit.get("fidelity", ""),
        "coverages": coverages[-20:],
        "ok": (unit.get("quality") or {}).get("ok"),
        "reason": (unit.get("quality") or {}).get("reason", ""),
        "status": unit.get("status", ""),
        "updated": now(),
    }
    q[uid].setdefault("failed_by", prev.get("failed_by", []))
    if (unit.get("quality") or {}).get("ok") is False:
        reason = str((unit.get("quality") or {}).get("reason", ""))
        items = []
        if "exercise the change" in reason:
            items.append("item1")
        if "coverage" in reason.lower() or "evidence" in reason.lower():
            items.append("item3" if "cite" in reason else "item2")
        q[uid]["failed_by"] = list(dict.fromkeys(q[uid]["failed_by"] + items))
    write_json(QUALITY_JSON, q)


def recover_branch(unit: dict, history: dict, state: dict) -> bool:
    """Reuse a branch a previous cycle left behind instead of rebuilding it.

    If the unit's branch exists on origin with commits ahead of BASE_REF and the
    last recorded attempt was not 'no-change', the work is re-gated and requeued
    for the merge queue. Nothing is rebuilt, so a cycle that died between commit
    and merge costs no tokens on the retry.
    """
    branch = unit_branch(unit)
    git("fetch", "origin")
    ahead = git_out("rev-list", "--count", f"{BASE_REF}..refs/remotes/origin/{branch}")
    if not ahead or ahead == "0":
        return False
    wt = attach_worktree(unit)
    rc, out = run_check(wt)
    (LOG_DIR / f"{unit['id']}-recover.check.log").write_text(out)
    if rc != 0:
        # The branch does not pass the gate; hand it back with the tail as
        # feedback so the next builder attempt repairs it. Clear any stale
        # worktree when the branch is behind main: the next attempt must start
        # from the real base, not from a tree stranded on the old head.
        behind = git_out("rev-list", "--count",
                         f"HEAD..{BASE_REF}", cwd=wt)
        if behind and behind != "0":
            drop_worktree(unit)
        unit["feedback"] = "scripts/check.sh failed on the recovered branch:\n" + tail(out, 60)
        record_history(unit, "recovered-fail")
        event(state, f"{unit['id']}: recovered branch fails check.sh; rebuilding")
        return False
    unit["reason"] = f"recovered existing branch {branch} ({ahead} commits ahead)"
    record_history(unit, "recovered")
    if unit.get("pr"):
        unit["status"] = "queued"
        event(state, f"{unit['id']}: recovered PR #{unit['pr']} into the merge queue")
    else:
        pr = push_and_open_pr(unit, wt, out, state)
        unit["pr"] = pr
        unit["status"] = "pr_open"
        event(state, f"{unit['id']}: recovered branch, opened PR #{pr}")
    return True


def attach_worktree(unit: dict) -> Path:
    """Worktree for a unit whose branch already exists on origin (resume path)."""
    path = worktree_path(unit)
    branch = unit_branch(unit)
    git("fetch", "origin")
    if path.exists() and (path / ".git").exists():
        return path
    if path.exists():
        shutil.rmtree(path)
    rc, out = git("worktree", "add", str(path), branch)
    if rc != 0:
        rc, out = git("worktree", "add", str(path), f"origin/{branch}")
    if rc != 0:
        raise RuntimeError(f"cannot attach worktree for {unit['id']}: {out}")
    return path


def resume_open_prs(roadmap: dict, state: dict) -> None:
    """Re-enter the merge queue for units left queued or with an open PR.

    A cycle that ends between 'PR opened' and 'merged' must not lose the PR: the
    next cycle picks it up here, re-runs the gate on the rebased head and merges
    it, one at a time under the same lock.

    This path is deliberately NOT gated by the daily merge cap. The cap exists
    to bound how much NEW work starts in a day (``select_ready`` enforces it);
    the build cost of an already-open PR is sunk, and stranding it is what left
    PR #65/#66 stuck. Merging a handful of already-built PRs cannot exceed the
    cap in any meaningful way (at most MAX_PARALLEL are in flight at once).
    """
    for uid in sorted(roadmap):
        u = roadmap[uid]
        if u.get("status") not in ("queued", "pr_open") or not u.get("pr"):
            continue
        try:
            wt = attach_worktree(u)
            event(state, f"{uid}: resuming merge queue for PR #{u['pr']}")
            merge_queue(u, wt, state)
        except control.IntegrityError:
            raise
        except Exception as exc:
            event(state, f"{uid}: resume failed: {exc}")


def deps_merged(unit: dict, roadmap: dict) -> bool:
    for dep in unit.get("depends_on", []) or []:
        d = roadmap.get(str(dep))
        if d is None or d.get("status") != "merged":
            return False
    return True


# QA units are advisory work: they improve confidence but must never gate
# feature (F) delivery. Only these kinds are advisory; a refactor (RF) unit is
# a normal roadmap entry and is not in this set.
ADVISORY_KINDS = ("audit-fix",)


def is_advisory(unit: dict) -> bool:
    return str(unit.get("id", "")).startswith("QA") or unit.get("kind") in ADVISORY_KINDS


def strip_advisory_deps(live: dict) -> None:
    """Remove advisory (QA) dependencies from non-advisory units, in place.

    An F unit that names a QA unit in ``depends_on`` would be blocked until the
    advisory work merges - exactly the coupling the pipeline must not have. The
    dependency is dropped so the feature unit can proceed; advisory units may
    still depend on each other.
    """
    advisory_ids = {uid for uid, u in live.items() if is_advisory(u)}
    for uid, u in live.items():
        if is_advisory(u):
            continue
        deps = [str(d) for d in (u.get("depends_on") or [])]
        kept = [d for d in deps if d not in advisory_ids]
        if kept != deps:
            u["depends_on"] = kept


def planner_pending(roadmap: dict) -> bool:
    """Can the planner still turn something into real (non-advisory) work?

    True when a design, un-rewritten parked, or split-requested unit is waiting
    on a planner pass. Used to give promotion priority over advisory QA.
    """
    for u in roadmap.values():
        if u.get("status") == "design" and int(u.get("planner_retries", 0)) < PLANNER_RETRIES:
            return True
        if u.get("status") == "parked" and int(u.get("planner_retries", 0)) < PLANNER_RETRIES:
            return True
        if u.get("split_requested") and u.get("status") == "todo" \
                and int(u.get("planner_retries", 0)) < PLANNER_RETRIES:
            return True
    return False


def select_ready(roadmap: dict, state: dict) -> list:
    cap = effective_merge_cap(state)
    if int(state.get("merged_today", 0)) >= cap:
        event(state, f"daily merge cap reached ({cap}); not dispatching")
        return []
    if int(state.get("tokens_today", 0)) >= DAILY_TOKEN_CAP:
        event(state, f"daily token cap reached ({DAILY_TOKEN_CAP}); not dispatching")
        return []
    ready = []
    for uid in sorted(roadmap):
        u = roadmap[uid]
        if u.get("status") != "todo":
            continue
        if u.get("split_requested"):
            # Waiting on the planner to split it into smaller units; rebuilding
            # it whole would just repeat the failure.
            continue
        if not deps_merged(u, roadmap):
            continue
        if int(u.get("attempts", 0)) >= MAX_ATTEMPTS:
            u["status"], u["reason"] = "parked", "four builder launches exhausted"
            continue
        if float(u.get("provider_retry_at", 0)) > time.time():
            continue
        if int(u.get("tokens", 0)) >= PER_UNIT_TOKEN_CAP:
            u["status"] = "parked"
            u["reason"] = f"per-unit token cap {PER_UNIT_TOKEN_CAP} exceeded"
            event(state, f"{uid}: parked on token cap ({u['tokens']})")
            continue
        if adopt_branch_unit(u, state):
            continue
        # (a) pre-dispatch size check (Jev, routing only). A unit that already
        # timed out is never run as is, whatever Jev says. The decision is
        # cached per (attempts, timeouts) so a unit sitting in todo across
        # cycles does not re-ask on every tick.
        stamp = f"{int(u.get('attempts', 0))}:{int(u.get('timeouts', 0))}"
        if u.get("size_check_at") == stamp and u.get("size_action"):
            size = {"action": u["size_action"], "source": u.get("size_source", "rule"),
                    "probability": None}
        else:
            size = jev_size_check(u)
            if size.get("source") == "jev":
                size["advisory_action"] = size.get("action")
                size["action"] = "split" if int(u.get("timeouts", 0)) else "run_as_is"
            u["size_check_at"] = stamp
            u["size_action"] = size["action"]
            u["size_source"] = size.get("source", "rule")
        if size["action"] == "split" and int(u.get("planner_retries", 0)) < PLANNER_RETRIES:
            if not u.get("split_requested"):
                u["split_requested"] = True
                u["reason"] = (f"size check: split "
                               f"(source {size.get('source')}, p={size.get('probability')})")
                telemetry_event("split", uid, f"size check routed to split "
                                              f"(source={size.get('source')})")
                event(state, f"{uid}: size check -> split")
            continue
        if size["action"] == "shrink":
            if int(u.get("shrinks", 0)) < 2:
                u["shrinks"] = int(u.get("shrinks", 0)) + 1
                u["feedback"] = ("The size check found the goal clear but the "
                                 "surface too wide: implement the smallest "
                                 "coherent slice and stay inside the listed paths.")
                event(state, f"{uid}: size check -> shrink "
                             f"(attempt {u['shrinks']}/2)")
            else:
                u["reason"] = "size check kept choosing shrink"
                u["split_requested"] = True
                event(state, f"{uid}: size check -> split (shrink limit reached)")
                continue
        ready.append(u)
    # Advisory (QA) units never compete with real work: they run only when
    # nothing else is ready. If any non-advisory unit is ready this cycle, the
    # advisory ones wait.
    if any(not is_advisory(u) for u in ready):
        ready = [u for u in ready if not is_advisory(u)]
    elif planner_pending(roadmap):
        # Only advisory work is ready, but the planner can still turn design /
        # parked / split units into real F work. Promoting a feature unit beats
        # running advisory QA, so leave the board to the planner this cycle.
        ready = []
    return ready


def start_build(unit: dict, state: dict, roadmap: dict | None = None):
    if unit.get("status") == "merged" or int(unit.get("attempts", 0)) >= MAX_ATTEMPTS:
        raise BudgetDenied("unit already delivered or builder limit reached")
    wt = ensure_worktree(unit)
    rid = admit_paid(state, unit, "builder")
    attempt = int(unit.get("attempts", 0)) + 1
    model = unit.pop("model_override", "") or model_for_attempt(attempt)
    prompt = builder_brief(unit, attempt, model, unit.get("feedback", ""))
    stem = f"{unit['id']}-attempt{attempt}-{rid}"
    control.atomic_text(BRIEF_DIR / (stem + ".md"), prompt)
    usage, log_path = LOG_DIR / (stem + ".usage.json"), LOG_DIR / (stem + ".log")
    logfile = log_path.open("x")
    toolsets = "file,terminal,context_engine"
    cmd = [HERMES, "-z", prompt, "--usage-file", str(usage), "-m", model,
           "--provider", PROVIDER, "--reasoning", "low", "-t", toolsets,
           "-s", SKILL_NAME["builder"], "--in", str(wt), "--accept-hooks"]
    ts_start = now()
    try:
        proc = subprocess.Popen(cmd, cwd=str(wt), env={**os.environ, "HERMES_HOME": str(PROFILE_HOME["builder"])},
                     stdout=logfile, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    except OSError:
        logfile.close()
        log_model_run("builder", model, unit["id"], attempt, 127, "provider_error",
                      {"total_tokens": 0, "api_calls": 0}, ts_start=ts_start,
                      run_id=rid, charged_tokens=0)
        release_paid(state, rid)
        write_json(STATE_JSON, state)
        raise
    unit.update(attempts=attempt, model=model, status="building", updated=now(), run_id=rid)
    save_roadmap(roadmap if roadmap is not None else {unit["id"]: unit})
    telemetry_event("dispatched", unit["id"], f"attempt {attempt} on {model}",
                    attempt=attempt, model=model, run_id=rid)
    log(f"{unit['id']}: dispatch attempt {attempt} on {model}")
    return {"unit": unit, "proc": proc, "started": time.time(), "ts_start": ts_start,
            "logfile": logfile, "log_path": log_path, "usage": usage, "wt": wt, "run_id": rid}


def finish_build(job, roadmap: dict, state: dict) -> None:
    unit, proc = job["unit"], job["proc"]
    uid, wt, usage = unit["id"], job["wt"], job["usage"]
    try:
        # Absolute launch deadline, so waiting behind another merge gives no
        # builder an extra RUN_TIMEOUT window.
        remaining = max(0.01, RUN_TIMEOUT - (time.time() - job["started"]))
        proc.communicate(timeout=remaining)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        kill_process_group(proc)
        rc = 124
    with_suppress(job["logfile"].close)
    wall = int(time.time() - job["started"])
    data = read_json(usage, {}) or {}
    tokens, source = usage_tokens(data), "usage-file"
    if tokens <= 0 and rc == 124:
        tokens = tokens_from_state_db("builder", f"UNIT BRIEF {uid}")
        source = "state.db"
    if tokens <= 0 and not (data.get("api_calls") == 0 and data.get("total_tokens") == 0):
        tokens, source = TIMEOUT_FALLBACK_TOKENS, "pessimistic-estimate"
    output = job.get("log_path")
    output = output.read_text(errors="replace")[-16000:] if output and output.exists() else ""
    outage = control.provider_error(rc, output)
    rid = job.get("run_id") or control.identity()
    outcome = "provider_error" if outage else "timeout" if rc == 124 else "other"
    # Ledger lands BEFORE publication/review. A crash cannot lose builder spend.
    log_model_run("builder", unit.get("model", ""), uid, unit.get("attempts"), rc,
                  outcome, data, "builder", "file,terminal,context_engine",
                  job.get("ts_start", ""), now(), run_id=rid, charged_tokens=tokens)
    release_paid(state, rid)
    add_tokens(state, unit, tokens)
    unit["wall_s"] = int(unit.get("wall_s", 0)) + wall
    unit["updated"] = now()
    if outage:
        unit["attempts"] = max(0, int(unit.get("attempts", 0)) - 1)
        unit["status"] = "todo"
        unit["reason"] = "provider outage; no builder attempt consumed"
        note_provider(state, True, uid)
        save_roadmap(roadmap)
        return
    if rc == 0:
        note_provider(state, False, uid)
    telemetry_event("built", uid, f"rc={rc} {wall}s {tokens} tokens ({source})",
                    attempt=unit.get("attempts"), tokens=tokens, wall_s=wall, run_id=rid)
    if rc == 124:
        unit["timeouts"] = int(unit.get("timeouts", 0)) + 1
        unit["split_requested"] = True
        unit["status"] = "todo" if int(unit.get("attempts", 0)) < MAX_ATTEMPTS else "parked"
        unit["reason"] = f"timed out at {RUN_TIMEOUT}s ({tokens} tokens, {source})"
        telemetry_event("timeout", uid, unit["reason"])
        save_roadmap(roadmap)
        write_json(STATE_JSON, state)
        return
    box = {"v": outcome}
    try:
        if rc not in (0, None):
            unit["reason"] = f"builder exited rc={rc}"
            _apply_failure_triage(unit, state, output, box)
        else:
            _publish_attempt(unit, wt, state, box)
    finally:
        control.append_record(STATE_DIR / "runs.jsonl", {"record_type": "outcome",
            "run_id": rid, "outcome": box["v"], "ts_end": now()})
        save_roadmap(roadmap)
        write_json(STATE_JSON, state)


def _publish_attempt(unit: dict, wt: Path, state: dict, outcome_box: dict) -> None:
    """Judge one builder attempt and carry it to merge, or fail it.

    Sets ``outcome_box["v"]`` to the attempt's telemetry outcome (merged,
    gate_failed, no_change, review_fix, provider_error) so the caller can write
    the builder's run record once the decision is known. Returning early means
    the attempt failed and stays in the unit's own status; returning normally
    means the unit was queued for merge.
    """
    uid = unit["id"]
    # --- diff guard: scope and protected paths ---------------------------
    # Checked on the working tree, before commit_if_dirty, so an uncommitted
    # edit to ops/ still fails the attempt instead of being committed.
    files = changed_files(wt)
    violations = [] if GUARD_DISABLED else guard_violations(files, unit.get("paths"), uid)
    if GUARD_DISABLED:
        telemetry_event("guard_disabled", uid,
                        "PHPRETRO_GUARD_DISABLED is set: the diff guard did not "
                        "run on this attempt")
    if violations:
        outcome_box["v"] = "gate_failed"
        detail = "\n".join(f"- {p}: {why}" for p, why in violations)
        event(state, f"{uid}: DIFF GUARD rejected the attempt:\n{detail}")
        telemetry_event("gate_fail", uid, "diff guard: " + "; ".join(
            f"{p} ({why})" for p, why in violations)[:200])
        (LOG_DIR / f"{uid}-attempt{unit['attempts']}-guard.log").write_text(detail + "\n")
        discard_changes(wt, unit)
        unit["reason"] = "diff guard: " + "; ".join(f"{p} ({why})" for p, why in violations)[:300]
        unit["feedback"] = ("Your diff touched paths you may not change:\n" + detail +
                            "\nNothing from that attempt was kept. Stay inside the listed paths.")
        if unit["attempts"] >= MAX_ATTEMPTS:
            unit["status"] = "parked"
            event(state, f"{uid}: parked after repeated diff-guard rejections")
            telemetry_event("parked", uid, "repeated diff-guard rejections")
        else:
            unit["status"] = "todo"
            event(state, f"{uid}: diff guard -> retry")
        return

    commit_if_dirty(wt, unit)
    ahead = git_out("rev-list", "--count", f"{BASE_REF}..HEAD", cwd=wt)
    if not ahead or ahead == "0":
        outcome_box["v"] = "no_change"
        record_history(unit, "no-change")
        # No change is the same signal as a timeout: the unit is too big or
        # too vague, so the planner splits it instead of it retrying unchanged.
        unit["split_requested"] = True
        unit["feedback"] = "The previous attempt produced no committed change."
        unit["status"] = "todo"
        if unit["attempts"] >= MAX_ATTEMPTS or unit["tokens"] >= PER_UNIT_TOKEN_CAP:
            unit["status"] = "parked"
            unit["reason"] = "no committed change after all ladder attempts"
            telemetry_event("parked", uid, "no committed change after the ladder")
        telemetry_event("no_change", uid, "attempt produced no committed change")
        event(state, f"{uid}: no change produced -> {unit['status']} (split requested)")
        return

    rc, out = run_check(wt)
    (LOG_DIR / f"{uid}-attempt{unit['attempts']}.check.log").write_text(out)
    if rc != 0:
        outcome_box["v"] = "gate_failed"
        unit["feedback"] = ("scripts/check.sh failed:\n" + tail(out, 60))
        unit["reason"] = "check.sh failed: " + tail(out, 3).replace("\n", " | ")
        telemetry_event("gate_fail", uid, "check.sh: " + tail(out, 2).replace("\n", " | ")[:200])
        # (b) failure triage: Jev picks the next move among ladder-legal options.
        _apply_failure_triage(unit, state, tail(out, 80), outcome_box)
        return

    event(state, f"{uid}: check.sh PASSED on attempt {unit['attempts']}")
    telemetry_event("gate_pass", uid, f"check.sh passed on attempt {unit['attempts']}")

    # --- quality safeguards: items 1-3, before anything is published ------
    # A quality failure is an attempt failure: fix it in the worktree and retry,
    # so no PR is opened and nothing reaches the merge queue.
    qreport = quality_gate(wt, unit, state, BASE_REF)
    unit["quality"] = {k: qreport.get(k) for k in ("ok", "reason", "coverage", "fidelity")}
    if qreport.get("coverage") is not None:
        unit.setdefault("coverages", []).append(qreport["coverage"])
    if qreport.get("fidelity"):
        unit["fidelity"] = qreport["fidelity"]
    unit["quality_detail"] = (qreport.get("detail") or "")[:2000]
    rec_quality(unit)
    log(f"{uid}: quality ok={qreport['ok']} coverage={qreport.get('coverage')} "
        f"fidelity={qreport.get('fidelity')} ({qreport.get('reason','')[:80]})")
    if not qreport.get("ok"):
        outcome_box["v"] = "gate_failed"
        unit["feedback"] = ("Quality safeguards rejected the attempt:\n"
                            + (qreport.get("detail") or qreport.get("reason", ""))
                            + "\n\nRepair the tests, not the check. Every new test must fail "
                              "when the implementation is removed (item 1); changed files must "
                              "reach the coverage floor or the unit doc must carry a "
                              "`coverage-exempt:` line (item 2); every new test must cite the "
                              "evidence file or fixture it uses, or the unit doc must say "
                              "`fidelity: guessed` (item 3).")
        unit["reason"] = "quality: " + str(qreport.get("reason", ""))[:280]
        unit["status"] = "todo" if unit["attempts"] < MAX_ATTEMPTS else "parked"
        event(state, f"{uid}: QUALITY rejected the attempt "
                     f"({qreport.get('reason')}) -> {unit['status']}")
        telemetry_event("gate_fail", uid, "quality: " + str(qreport.get("reason",""))[:200])
        if unit["status"] == "parked":
            telemetry_event("parked", uid, "quality safeguards, out of attempts")
        return

    try:
        pr = push_and_open_pr(unit, wt, out, state)
    except Exception as exc:
        outcome_box["v"] = "provider_error"
        unit["status"] = "todo"
        unit["feedback"] = f"delivery failed: {exc}"
        event(state, f"{uid}: PR delivery failed: {exc}")
        telemetry_event("provider_error", uid, f"PR delivery failed: {exc}"[:200])
        return
    unit["pr"] = pr
    unit["status"] = "pr_open"
    unit["updated"] = now()
    event(state, f"{uid}: PR #{pr} opened")
    telemetry_event("pr_opened", uid, f"PR #{pr} opened", pr=pr)

    if not ensure_reviewed(unit, wt, state):
        outcome_box["v"] = "review_fix"
        return

    unit["status"] = "queued"
    if merge_queue(unit, wt, state):
        outcome_box["v"] = "merged"
# --------------------------------------------------------------------------
# Planner
# --------------------------------------------------------------------------

def planner_model(unit: dict) -> str:
    return MODEL["sol"] if unit.get("unclear_semantics") else MODEL["deepseek"]


def apply_planner_output(roadmap: dict, state: dict, unit: dict, out: str,
                          old_id: str = "", mode: str = "") -> bool:
    match = re.search(r"(units:\s*\n(?:.|\n)*)", out)
    text = match.group(1) if match else out
    try:
        doc = parse_yaml(text)
        entries = doc.get("units")
        if entries == [] and mode == "audit":
            return True
        candidate, new_ids = control.validate_plan(
            entries, roadmap, unit, old_id, mode,
            PROTECTED_PREFIXES + PROTECTED_FILES, SPLIT_MAX_UNITS)
    except (ValueError, TypeError, KeyError, control.IntegrityError) as exc:
        if "events" in state:
            event(state, "planner rejected atomically: " + str(exc))
        return False
    for uid in new_ids:
        entry = candidate[uid]
        for key in ("attempts", "tokens", "review_rounds", "conflict_rounds", "planner_retries", "pr"):
            entry[key] = 0
        for key in ("reason", "model", "branch"):
            entry[key] = ""
        entry.setdefault("status", "todo")
        entry["updated"] = now()
    # Update existing objects in place: the caller still owns its parent reference.
    for uid, entry in candidate.items():
        if uid in roadmap:
            roadmap[uid].update(entry)
        else:
            roadmap[uid] = entry
    return True


def maybe_plan(roadmap: dict, state: dict) -> bool:
    """Run one planner pass (split / rewrite / promote) if the board needs it.

    Returns True when the planner was actually invoked (it consumed the cycle's
    one agent call), False otherwise.
    """
    active = [u for u in roadmap.values() if u.get("status") in ("building", "pr_open", "queued")]
    if active:
        return False
    todo = [u for u in roadmap.values() if u.get("status") == "todo"
            and not u.get("split_requested") and deps_merged(u, roadmap)
            and not is_advisory(u)]
    if todo:
        return False
    # A unit that timed out or produced no change gets split into smaller units
    # rather than retried at the same size. This takes precedence over the
    # parked/design queues because it is the failure the pipeline just produced.
    splits = sorted([u for u in roadmap.values()
                     if u.get("split_requested") and u.get("status") == "todo"
                     and int(u.get("planner_retries", 0)) < PLANNER_RETRIES],
                    key=lambda u: u["id"])
    if splits:
        target, mode = splits[0], "split"
    else:
        parked = sorted([u for u in roadmap.values()
                         if u.get("status") == "parked"
                         and int(u.get("planner_retries", 0)) < PLANNER_RETRIES],
                        key=lambda u: u["id"])
        design = sorted([u for u in roadmap.values()
                         if u.get("status") == "design"
                         and int(u.get("planner_retries", 0)) < PLANNER_RETRIES],
                        key=lambda u: u["id"])
        if design:
            target, mode = design[0], "promote"
        elif parked:
            target, mode = parked[0], "rewrite"
        else:
            for u in roadmap.values():
                if u.get("status") == "parked":
                    u["status"] = "parked-final"
                if u.get("status") == "design" and int(u.get("planner_retries", 0)) >= PLANNER_RETRIES:
                    u["status"] = "design-blocked"
            return False

    uid = target["id"]
    if not paid_allowed(state, target, "planner"):
        return False
    target["split_requested"] = False
    model = planner_model(target)
    design_text = ""
    if mode == "promote" and target.get("design_doc"):
        p = REPO / str(target["design_doc"])
        if p.exists():
            design_text = p.read_text()[:12000]
    prompt = planner_brief(target, mode, design_text)
    prompt += ("\nExisting IDs are immutable and reserved: " + ", ".join(sorted(roadmap)) +
               f"\nUse fresh IDs such as {uid}a and {uid}b. Never emit the parent ID. "
               "New entries must have status todo, size S or M, no runtime counters, "
               "no protected paths, and an acyclic dependency graph.\n")
    (BRIEF_DIR / f"{uid}-planner.md").write_text(prompt)
    event(state, f"{uid}: planner ({model}) {mode}")
    role = "planner"
    rc, out, usage = hermes_run("planner", model, prompt, "file", REPO,
                                f"{uid}-planner", 900, unit=uid, role=role, state=state, budget_unit=target)
    tokens = usage_tokens(usage)
    add_tokens(state, target, tokens)
    if usage.get("admission_denied") or control.provider_error(rc, out):
        target["split_requested"] = mode == "split"
        event(state, f"{uid}: planner deferred on provider/admission error")
        return True
    target["planner_retries"] = int(target.get("planner_retries", 0)) + 1
    if rc == 0 and apply_planner_output(roadmap, state, target, out, old_id=uid, mode=mode):
        if mode == "promote":
            target["status"] = "promoted"
        else:
            target["status"] = "parked-final"
        event(state, f"{uid}: planner produced replacement entries")
        if mode == "split":
            telemetry_event("split", uid,
                            f"planner split the unit (retry {target['planner_retries']})")
    else:
        target["reason"] = (target.get("reason", "") + " | planner output rejected")[:400]
        if target["planner_retries"] >= PLANNER_RETRIES:
            if mode == "promote":
                target["status"] = "design-blocked"
            else:
                # The split could not be produced: fall back to the retry ladder
                # rather than silently dropping the unit. Clear split_requested,
                # or select_ready would skip it forever while maybe_plan has no
                # retries left to act on it - a deadlock.
                target["status"] = "todo"
                target["split_requested"] = False
        elif mode == "split":
            target["split_requested"] = True
        event(state, f"{uid}: planner output rejected "
                     f"({target['planner_retries']}/{PLANNER_RETRIES})")
    return True


# --------------------------------------------------------------------------
# Cycle
# --------------------------------------------------------------------------

def dispatch(roadmap: dict, state: dict) -> None:
    if not paid_allowed(state, None, "builder"):
        event(state, "dispatch admission denied: STOP, caps or provider backoff/pause")
        return
    ready = select_ready(roadmap, state)
    if not ready:
        return
    batch, used = [], []
    for u in ready:
        if len(batch) >= MAX_PARALLEL:
            break
        if any(paths_overlap(u.get("paths"), p) for p in used):
            continue
        batch.append(u)
        used.extend(u.get("paths") or [])
    if not batch:
        return
    event(state, "dispatching " + ", ".join(u["id"] for u in batch))
    jobs = []
    for u in batch:
        try:
            jobs.append(start_build(u, state, roadmap))
        except control.IntegrityError:
            raise
        except Exception as exc:
            u["status"] = "todo"
            u["reason"] = f"dispatch error: {exc}"
            event(state, f"{u['id']}: dispatch error: {exc}")
    for job in jobs:
        try:
            finish_build(job, roadmap, state)
        except control.IntegrityError:
            raise
        except Exception as exc:
            u = job["unit"]
            u["status"] = "todo"
            u["reason"] = f"pipeline error: {exc}"
            event(state, f"{u['id']}: pipeline error: {exc}")


def _nightly_entry(name: str) -> dict:
    """One nightly job's latest result, flattened for the renderer.

    nightly.json is ``{name: {ts, pass, details}}``; the readers here want the
    details' fields at the top level, so this merges them in.
    """
    led = read_json(NIGHTLY_JSON, {})
    e = led.get(name) if isinstance(led, dict) else None
    if not isinstance(e, dict):
        return {}
    out = dict(e.get("details") or {})
    out["ts"] = e.get("ts")
    out["ok"] = bool(e.get("pass"))
    return out


def nightly_lines() -> list:
    """Render the nightly integration check and self-check for STATE.md."""
    led = read_json(NIGHTLY_JSON, {})
    if not led:
        return ["- nightly checks: not run yet "
                "(ops/nightly.py --integration --selfcheck)"]
    lines = []
    for name, label in (("integration", "integration"), ("selfcheck", "self-check")):
        e = _nightly_entry(name)
        if not e:
            lines.append(f"- {label}: not run yet")
            continue
        state_txt = "PASS" if e.get("ok") else "FAIL"
        detail = ""
        if name == "integration":
            fading = e.get("failing_routes") or []
            detail = ("routes ok: " + str(len(e.get("routes", []))) if e.get("ok")
                      else "failing: " + ", ".join(fading) if fading
                      else e.get("error", "unknown"))
        else:
            bad = [c["name"] for c in e.get("checks", []) if not c.get("ok")]
            detail = "all checks ok" if e.get("ok") else "failing: " + ", ".join(bad)
        fails = nightly_consecutive_failures(name)
        lines.append(f"- {label}: {state_txt} ({detail})"
                     + (f"; {fails} consecutive failures" if not e.get("ok") else ""))
    return lines


def nightly_consecutive_failures(name: str) -> int:
    """Trailing failures for one nightly job, from nightly-history.jsonl."""
    n = 0
    for entry in reversed(nightly_history()):
        if entry.get("name") != name:
            continue
        if entry.get("ok"):
            break
        n += 1
    return n


def nightly_history() -> list:
    """Every nightly run record, oldest first (nightly-history.jsonl + rotated)."""
    entries = []
    files = sorted(STATE_DIR.glob("nightly-history-*.jsonl")) + \
        [STATE_DIR / "nightly-history.jsonl"]
    for f in files:
        try:
            for line in f.read_text().splitlines():
                if line.strip():
                    entries.append(json.loads(line))
        except (OSError, json.JSONDecodeError):
            continue
    return entries


# --------------------------------------------------------------------------
# Throughput guard (item 1): revert the raised merge cap when nights go red
# --------------------------------------------------------------------------

def _load_merge_cap() -> dict:
    if not MERGE_CAP_FILE.exists():
        return {}
    try:
        rec = json.loads(MERGE_CAP_FILE.read_text())
        if not isinstance(rec, dict) or not isinstance(rec.get("reverted"), bool):
            raise ValueError("invalid merge cap state")
        if rec.get("reverted"):
            value = control.nonnegative(rec.get("value"), "merge cap")
            if value < 1 or value > MERGE_CAP_REVERTED:
                raise ValueError("invalid reverted merge cap")
        return rec
    except (OSError, ValueError) as exc:
        raise control.IntegrityError("merge cap state corrupt; keep STOP") from exc


def effective_merge_cap(state: dict) -> int:
    """The merge cap in force: 30 normally, or the revert value (12).

    The base cap is ``MAX_MERGE_PER_DAY``. It is auto-reverted to
    ``MERGE_CAP_REVERTED`` when the guard has recorded that a nightly check
    failed twice in a row; an explicit override is honored until a later green
    night clears it.
    """
    override = _load_merge_cap()
    if override.get("reverted"):
        try:
            return int(override.get("value") or MERGE_CAP_REVERTED)
        except (TypeError, ValueError):
            return MERGE_CAP_REVERTED
    return MAX_MERGE_PER_DAY


def apply_merge_cap_guard(state: dict) -> None:
    """Revert/restore the raised merge cap from the nightly failure streaks.

    Two consecutive failed nights of EITHER the integration check OR the
    self-check revert the raised cap (30) to ``MERGE_CAP_REVERTED`` (12) and
    record why. A later night where neither check has a 2-in-a-row failure
    clears the revert, restoring the raised cap. Never raises; a missing
    ledger simply leaves the cap as configured.
    """
    integ = nightly_consecutive_failures("integration")
    self_ = nightly_consecutive_failures("selfcheck")
    red = max(integ, self_) >= 2
    rec = _load_merge_cap()
    try:
        if red and not rec.get("reverted"):
            rec = {"reverted": True, "value": MERGE_CAP_REVERTED,
                   "reason": (f"nightly check failed twice in a row "
                              f"(integration={integ}, selfcheck={self_})"),
                   "ts": now()}
            write_json(MERGE_CAP_FILE, rec)
            event(state, f"merge cap reverted to {MERGE_CAP_REVERTED}: "
                         f"nightly failure streak (integration={integ}, "
                         f"selfcheck={self_})")
            telemetry_event("parked", "",
                            f"merge cap reverted to {MERGE_CAP_REVERTED}: "
                            f"nightly failures integration={integ} "
                            f"selfcheck={self_}")
        elif not red and rec.get("reverted"):
            rec = {"reverted": False, "value": MAX_MERGE_PER_DAY,
                   "reason": "nightly checks no longer failing twice in a row",
                   "ts": now()}
            write_json(MERGE_CAP_FILE, rec)
            event(state, f"merge cap restored to {MAX_MERGE_PER_DAY} "
                         f"(nightly checks green)")
    except OSError as exc:
        log(f"merge-cap guard: could not record: {exc}")


def queue_nightly_fixes(roadmap: dict, state: dict) -> None:
    """Turn failing integration routes into planner fix requests, once each.

    A route that is already the subject of an open fix unit is not queued again,
    so a persistent failure does not pile up duplicate units.
    """
    integ = _nightly_entry("integration")
    if integ.get("ok"):
        state["nightly_fix_queue"] = []
        return
    # Item 4: a nightly integration failure counts as a miss against the most
    # recent Jev-skipped review within 24h.
    for missed in jev_note_miss("nightly integration failure"):
        event(state, f"jev: miss counted for {missed} (nightly integration failure)")
    failing = integ.get("failing_routes") or []
    if not failing and integ.get("error"):
        # The server would not build or start: that is a whole-server fix, not
        # a per-route one.
        failing = ["(server did not build or start)"]
    queued = {r.get("route"): r for r in state.get("nightly_fix_queue", [])}
    open_routes = {u.get("fixes_route") for u in roadmap.values()
                   if u.get("fixes_route")
                   and u.get("status") not in ("merged", "parked-final")}
    kept = []
    for route in failing:
        if route in open_routes:
            continue
        if route in queued:
            kept.append(queued[route])
            continue
        detail = integ.get("error", "")
        if not detail:
            for r in integ.get("routes", []):
                if r.get("path") == route and not r.get("ok"):
                    detail = (f"status {r.get('status')} (want {r.get('want_status')}); "
                              f"key {r.get('key')!r} found={r.get('key_found')}")
                    break
        kept.append({"route": route,
                     "title": f"Fix the failing route {route}",
                     "reason": f"nightly integration check: {detail}",
                     "planner_retries": 0})
    state["nightly_fix_queue"] = kept


def maybe_plan_nightly_fix(roadmap: dict, state: dict) -> bool:
    """Ask the planner to open a fix unit for the next failing route.

    Returns True when it ran (whether or not the planner produced a unit).
    """
    if not paid_allowed(state, None, "planner"):
        return False
    queue = state.get("nightly_fix_queue") or []
    if not queue:
        return False
    req = queue[0]
    model = MODEL["deepseek"]
    prompt = f"""PLAN-FIX {req['route']}

The nightly integration check failed for this route:
{req['reason']}

Open one bounded fix unit that makes this route work again. Rules:
- size S or M, never L;
- list only the paths a fix to this route plausibly needs (max 8),
  including docs/units/<id>.md;
- use a fresh id of the form NF<n> (e.g. NF1) that collides with no existing
  unit id;
- output only the YAML block, starting with a top-level `units:` line.
"""
    (BRIEF_DIR / f"NFIX-{abs(hash(req['route'])) % 10000}.md").write_text(prompt)
    event(state, f"nightly: planner ({model}) fix for {req['route']}")
    rc, out, usage = hermes_run("planner", model, prompt, "file", REPO,
                                f"nightly-fix-{abs(hash(req['route'])) % 10000}", 900,
                                unit="", role="planner", state=state)
    tokens = usage_tokens(usage)
    add_tokens(state, {}, tokens)
    if usage.get("admission_denied") or control.provider_error(rc, out):
        event(state, "nightly planner deferred on provider/admission error")
        return True
    req["planner_retries"] = int(req.get("planner_retries", 0)) + 1
    before = set(roadmap)
    ok = False
    if rc == 0:
        ok = apply_planner_output(roadmap, state, req, out, old_id="", mode="fix")
        if ok:
            for uid in set(roadmap) - before:
                roadmap[uid]["fixes_route"] = req["route"]
    if ok:
        state["nightly_fix_queue"] = queue[1:]
        event(state, f"nightly: opened a fix unit for {req['route']}")
    elif req["planner_retries"] >= PLANNER_RETRIES:
        state["nightly_fix_queue"] = queue[1:]
        event(state, f"nightly: could not open a fix unit for {req['route']} "
                     f"after {req['planner_retries']} planner attempts")
    else:
        event(state, f"nightly: planner output rejected for {req['route']} "
                     f"({req['planner_retries']}/{PLANNER_RETRIES})")
    return True


AUDIT_STATE = STATE_DIR / "audit.json"


def audit_bundle(roadmap: dict, limit: int = 10, char_cap: int = 60000) -> str:
    """A read-only text bundle of the last ``limit`` merged units.

    For each unit: its entry, its unit doc, and its diff against the commit
    before its merge. Nothing is written and no branch is touched. Capped at
    ``char_cap`` characters so the audit prompt cannot grow without bound.
    """
    merged = sorted([u for u in roadmap.values() if u.get("status") == "merged"],
                    key=lambda u: u.get("updated", ""))
    recent = merged[-limit:]
    parts = [f"# Last {len(recent)} merged units (read-only audit input)", ""]
    for u in recent:
        pr = int(u.get("pr") or 0)
        parts.append(f"## {u['id']} - {u.get('title','')} (PR #{pr or '?'})")
        parts.append(unit_block(u))
        doc = REPO / "docs" / "units" / f"{u['id']}.md"
        if doc.exists():
            parts.append("### unit doc\n" + doc.read_text()[:1200])
        if pr:
            rc, out = sh(["gh", "pr", "diff", str(pr), "--repo", GH_REPO], timeout=120)
            if rc == 0:
                parts.append("### diff vs its base\n```diff\n" + tail(out, 250) + "\n```")
        else:
            # Adopted units have no PR recorded, so there is no diff to fetch.
            # Give the auditor the actual current code under the unit's paths
            # instead, or it would be reviewing titles with no code at all.
            listing = _paths_listing(str(u.get("paths") or []), char_cap=4000)
            if listing:
                parts.append("### current code under its paths\n```go\n"
                             + listing + "\n```")
        parts.append("")
        if sum(len(p) for p in parts) > char_cap:
            parts.append("... [bundle truncated at the size cap]")
            break
    return "\n".join(parts)[:char_cap]


def _paths_listing(paths, char_cap: int = 4000) -> str:
    """Concatenated, size-capped contents of the .go files under ``paths``."""
    out, used = [], 0
    for pat in paths:
        if not str(pat).startswith("internal/"):
            continue
        base = REPO / str(pat).rstrip("*").rstrip("/")
        files = []
        if base.is_file():
            files = [base]
        elif base.is_dir():
            files = sorted(base.rglob("*.go"))
        for f in files:
            try:
                rel = f.relative_to(REPO)
            except ValueError:
                continue
            text = f.read_text(errors="replace")
            chunk = f"\n// ---- {rel} ----\n{text}"
            if used + len(chunk) > char_cap:
                return "\n".join(out)
            out.append(chunk)
            used += len(chunk)
    return "\n".join(out)


def run_audit(roadmap: dict, state: dict) -> dict:
    """Item 4: read-only weekly audit by gpt-6.1-sol; findings become units.

    Never edits code: it only reads diffs and docs, and writes roadmap entries.
    Capped at AUDIT_TOKEN_CAP tokens; a capped or failed run is recorded and
    retried next week rather than retried immediately.
    """
    if not paid_allowed(state, None, "audit"):
        return {"rc": 75, "tokens": 0, "findings": [], "admission_denied": True}
    model = MODEL["sol"]
    bundle = audit_bundle(roadmap)
    prompt = (f"WEEKLY QUALITY AUDIT\n\nThe last merged units, read-only:\n\n{bundle}\n\n"
              "Report findings as roadmap entries following your skill. One entry per "
              "finding, most severe first. Output ONLY the YAML block: the first line "
              "must be `units:` and nothing may precede or follow it. If there is "
              "nothing worth changing, output exactly `units: []`.")
    (BRIEF_DIR / "weekly-audit.md").write_text(prompt)
    event(state, f"audit: weekly read-only audit ({model})")
    rc, out, usage = hermes_run("auditor", model, prompt, "file", REPO, "weekly-audit", 1200,
                                unit="", role="audit", state=state)
    tokens = usage_tokens(usage)
    # Keep the raw output: a rejected audit must be diagnosable, not just lost.
    with_suppress(lambda: (LOG_DIR / "weekly-audit.out").write_text(
        f"rc={rc} tokens={tokens}\n\n{out}"))
    add_tokens(state, {}, tokens)
    findings = []
    capped = tokens >= AUDIT_TOKEN_CAP
    if rc == 0 and not capped:
        before = set(roadmap)
        # mode="audit" allows `units: []` (nothing to fix) as a valid result.
        if apply_planner_output(roadmap, state, {"id": "AUDIT"}, out, mode="audit"):
            for uid in set(roadmap) - before:
                roadmap[uid].setdefault("kind", "audit-fix")
                findings.append(uid)
        else:
            event(state, "audit: output rejected (no YAML block); see "
                         "logs/weekly-audit.out")
    elif capped:
        event(state, f"audit: hit the {AUDIT_TOKEN_CAP} token cap; findings not parsed")
    else:
        event(state, f"audit: agent run failed rc={rc}")
    aud = read_json(AUDIT_STATE, {})
    aud["last_run"] = now()
    aud["tokens"] = tokens
    aud["findings_open"] = _audit_open(roadmap)
    aud["added"] = findings
    aud["capped"] = capped
    write_json(AUDIT_STATE, aud)
    event(state, f"audit: done, {len(findings)} finding(s) turned into units "
                 f"({tokens} tokens)")
    return aud


def _audit_open(roadmap: dict) -> int:
    """Audit findings still open: audit-fix units not yet merged."""
    return sum(1 for u in roadmap.values()
               if u.get("kind") == "audit-fix"
               and u.get("status") not in ("merged", "parked-final"))


def audit_due(state: dict) -> bool:
    aud = read_json(AUDIT_STATE, {})
    last = aud.get("last_run", "")
    if not last:
        return True
    try:
        age = (datetime.now(timezone.utc)
               - datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
               ).total_seconds()
    except Exception:
        return True
    return age >= 7 * 24 * 3600


def maybe_audit(roadmap: dict, state: dict) -> bool:
    """Run the audit if a week has passed and the board is not busy."""
    if not audit_due(state):
        return False
    active = [u for u in roadmap.values()
              if u.get("status") in ("building", "pr_open", "queued")]
    if active:
        return False
    run_audit(roadmap, state)
    return True


# --------------------------------------------------------------------------
# Item 5: a periodic consistency/refactor unit
# --------------------------------------------------------------------------

def maybe_refactor_unit(roadmap: dict, state: dict) -> bool:
    """After every REFACTOR_EVERY merged units, add one refactor unit.

    The refactor unit fixes the open audit findings and keeps package structure
    consistent. It is a normal roadmap entry, so it goes through check.sh and
    the same quality safeguards.
    """
    merged = [u for u in roadmap.values() if u.get("status") == "merged"]
    # Consumed counter: how many merges the pipeline has already accounted for.
    consumed = int(state.get("refactor_consumed", 0))
    open_refactors = [u for u in roadmap.values()
                      if u.get("kind") == "refactor"
                      and u.get("status") not in ("merged", "parked-final")]
    if open_refactors:
        return False
    if len(merged) - consumed < REFACTOR_EVERY:
        return False
    state["refactor_consumed"] = len(merged)
    aud = read_json(AUDIT_STATE, {})
    findings = [u for u in roadmap.values() if u.get("kind") == "audit-fix"
                and u.get("status") not in ("merged", "parked-final")]
    rid = next_free_id(roadmap, "RF")
    paths = sorted({p for u in findings for p in (u.get("paths") or [])})
    if not paths:
        # Nothing from the audit: a structure-only pass over the packages the
        # recent units touched.
        recent = sorted([u for u in merged], key=lambda u: u.get("updated", ""))[-REFACTOR_EVERY:]
        paths = sorted({p for u in recent for p in (u.get("paths") or [])
                        if str(p).startswith("internal/")})[:8]
    if not paths:
        state["refactor_consumed"] = len(merged)
        return False
    tgt = list(dict.fromkeys(paths))[:8]
    unit = {
        "id": rid,
        "title": "Consistency pass: fix the open audit findings and align package structure",
        "status": "todo",
        "kind": "refactor",
        "severity": "medium",
        "audit_finding": ("open audit findings: "
                          + ", ".join(u["id"] for u in findings) if findings
                          else "structure-only consistency pass"),
        "depends_on": [],
        "paths": tgt + [f"docs/units/{rid}.md"],
        "tests": ["go test ./...", "bash scripts/check.sh"],
        "acceptance": ["the open audit findings are fixed or explicitly ruled out",
                       "package layout and naming follow the neighbours' convention",
                       "no behaviour changes; existing tests still pass"],
        "size": "M",
        "attempts": 0,
    }
    roadmap[rid] = unit
    event(state, f"{rid}: refactor unit queued after {len(merged)} merged units "
                 f"({len(findings)} open audit finding(s))")
    return True


def next_free_id(roadmap: dict, prefix: str) -> str:
    n = 1
    while f"{prefix}{n}" in roadmap:
        n += 1
    return f"{prefix}{n}"


def read_env_var(name: str) -> str:
    """Read a variable from ``~/.hermes/.env`` (the documented ntfy setup)."""
    val = os.environ.get(name, "").strip()
    if val:
        return val
    try:
        for ln in (HOME / ".hermes" / ".env").read_text().splitlines():
            ln = ln.strip()
            if ln.startswith(f"{name}=") and not ln.startswith("#"):
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def alerts_lines() -> list:
    """Render the alert channel, its triggers, and any setup steps for STATE.md."""
    topic = (read_env_var("PHPRETRO_ALERT_TOPIC") or read_env_var("NTFY_TOPIC"))
    led = read_json(STATE_DIR / "alerts.json", {})
    last = led.get("last", {})
    lines = []
    if topic:
        lines.append(f"- channel: ntfy (public server) -> topic `{topic}`")
        lines.append("- trigger conditions (a one-line message is sent only for these): "
                     "no merge in 24h; a cap hit; the STOP file exists; the integration "
                     "check or self-check failed twice in a row; disk over 85%")
        if last.get("sent_at"):
            lines.append(f"- last alert: {last['sent_at']} :: "
                         + "; ".join(last.get("conditions", [])))
        else:
            lines.append("- last alert: none yet")
        lines.append("- to receive: install the ntfy app (https://ntfy.sh/docs/subscribe/phone/), "
                     f"tap +, enter topic `{topic}`. No account or token is needed on the public "
                     "server. The topic name is the only secret - keep it out of screenshots and logs.")
        lines.append("- to make the topic private (optional): reserve it on ntfy.sh, then set "
                     "`NTFY_TOKEN` in ~/.hermes/.env and restart.")
    else:
        lines.append("- channel: NOT configured. No alert can be delivered.")
        lines.append("- setup (no account needed): install the ntfy app "
                     "(https://ntfy.sh/docs/subscribe/phone/) and note your topic name; then add "
                     "`NTFY_TOPIC=<your-topic>` and `NTFY_PUBLISH_TOPIC=<your-topic>` to "
                     "`~/.hermes/.env`; subscribe to that topic in the app. Verify with "
                     "`hermes send --to ntfy:<your-topic> \"test\"`.")
    return lines


def quality_lines(roadmap: dict) -> list:
    """Item 6: the Quality section - guessed count, median coverage, audit
    findings open, units failed by items 1-2."""
    q = read_json(QUALITY_JSON, {})
    # Guessed-fidelity: from the ledger and from the units themselves, so a
    # unit merged before the ledger existed still counts.
    guessed = set()
    for uid, rec in q.items():
        if str(rec.get("fidelity", "")).lower() == "guessed":
            guessed.add(uid)
    for uid, u in roadmap.items():
        if str(u.get("fidelity", "")).lower() == "guessed":
            guessed.add(uid)
    # Median coverage over the last recorded coverage per merged unit.
    covs = []
    for uid, u in roadmap.items():
        if u.get("status") == "merged":
            series = (q.get(uid) or {}).get("coverages") or []
            if series:
                covs.append(series[-1])
    med_cov = _median(covs)
    aud = read_json(AUDIT_STATE, {})
    findings_open = _audit_open(roadmap)
    # Units failed by items 1-2, from the quality ledger's reason text.
    failed1 = sorted(uid for uid, rec in q.items()
                     if "exercise the change" in str(rec.get("reason", "")))
    failed2 = sorted(uid for uid, rec in q.items()
                     if "coverage" in str(rec.get("reason", "")).lower()
                     and "cite" not in str(rec.get("reason", "")))
    failed3 = sorted(uid for uid, rec in q.items()
                     if "cite" in str(rec.get("reason", "")))
    lines = [
        f"- guessed fidelity: {len(guessed)}"
        + (f" ({', '.join(sorted(guessed))})" if guessed else ""),
        f"- median coverage (merged units, changed files): {med_cov}% (n={len(covs)})",
        f"- audit findings open: {findings_open}"
        + (f" (last audit {aud.get('last_run')}, {aud.get('tokens', 0)} tokens)"
           if aud.get("last_run") else " (no audit yet)"),
        f"- units failed by the quality checks: item1 {len(failed1)}, "
        f"item2 {len(failed2)}, item3 {len(failed3)}",
    ]
    if failed1 or failed2 or failed3:
        lines.append(f"- failed units: item1={','.join(failed1) or '-'}, "
                     f"item2={','.join(failed2) or '-'}, item3={','.join(failed3) or '-'}")
    return lines


def unit_tokens(unit: dict) -> int:
    """A unit's total spend: its recorded counter, or its usage logs.

    Early adopted/merged units carry 0 because the runtime counter was added
    after they merged. Their ``*.usage.json`` files are still on disk, so the
    median in the report reads real numbers instead of 0.
    """
    rec = int(unit.get("tokens", 0))
    if rec > 0:
        return rec
    uid = unit.get("id", "")
    total = 0
    for p in sorted(LOG_DIR.glob(f"{uid}-*.usage.json")):
        total += usage_tokens(read_json(p, {}) or {})
    return total


def _median(values) -> int:
    vals = sorted(int(v) for v in values if v)
    if not vals:
        return 0
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) // 2


def telemetry_lines(state: dict) -> list:
    """Item 6: what the telemetry logs hold, and the dashboard note."""
    mod = _load_telemetry()
    lines = []
    if mod is None:
        lines.append("- telemetry module unavailable; numbers fall back to the "
                     "state counter")
        return lines
    try:
        runs = list(mod.read_runs())
    except Exception:
        runs = []
    day = state.get("day", "")
    today = [r for r in runs if str(r.get("ts_start", ""))[:10] == day]
    outcomes: dict = {}
    for r in today:
        o = r.get("outcome", "other")
        outcomes[o] = outcomes.get(o, 0) + 1
    roles: dict = {}
    for r in today:
        ro = r.get("role", "other")
        roles[ro] = roles.get(ro, 0) + 1
    unknown = sum(1 for r in today
                  if r.get("input_tokens") is None or r.get("api_calls") is None)
    lines.append(f"- runs.jsonl: {len(runs)} run(s) total, {len(today)} today "
                 f"({' '.join(f'{k}={v}' for k, v in sorted(roles.items())) or 'none'})")
    lines.append(f"- outcomes today: "
                 + (" ".join(f"{k}={v}" for k, v in sorted(outcomes.items())) or "none")
                 + (f"; {unknown} with unknown token fields (pessimistic estimate used)"
                    if unknown else ""))
    try:
        ev = sum(1 for _ in (STATE_DIR / "events.jsonl").read_text().splitlines())
    except OSError:
        ev = 0
    lines.append(f"- events.jsonl: {ev} event(s)")
    prices = {}
    try:
        prices = mod.load_prices()
    except Exception:
        prices = {}
    luna = (prices.get("gpt-6-luna") or {})
    lines.append("- prices.yaml: input/output per million (ESTIMATE; unit "
                 "uncalibrated)"
                 + (f"; gpt-6-luna {luna.get('input')}/{luna.get('output')}"
                    if luna else ""))
    lines.append("- logs are append-only, rotated monthly, and hold no keys or "
                 "prompts")
    lines.append("- note: the A6API cost dashboard reads these same files "
                 "(runs.jsonl, events.jsonl, nightly.json) for its numbers")
    return lines


def telemetry_day_totals(day: str) -> dict:
    """Today's tokens/runs from runs.jsonl; falls back to the state counter.

    Item 6: STATE.md's numbers come from the telemetry logs. The state counter
    is only used when the log has nothing for the day (for example before the
    telemetry module was installed).
    """
    mod = _load_telemetry()
    if mod is None:
        return {}
    try:
        return mod.totals_for_day(day)
    except Exception:
        return {}


def telemetry_unit_totals() -> dict:
    """Total tokens per unit from runs.jsonl (empty when unavailable)."""
    mod = _load_telemetry()
    if mod is None:
        return {}
    try:
        return mod.unit_token_totals()
    except Exception:
        return {}


def jev_lines() -> list:
    """STATE.md's Jev section: call count, spend, changed rate, disables."""
    mod = _load_jev()
    if mod is None:
        return ["- jev module unavailable; rules only"]
    try:
        lines = list(mod.report_lines())
    except Exception as exc:
        return [f"- jev reporting error: {exc}"]
    try:
        if not mod.api_key():
            lines.append("- setup: " + mod.SETUP_STEPS)
    except Exception:
        pass
    return lines


def report_lines(roadmap: dict, state: dict) -> list:
    """The five-line report: merged, stuck, median tokens/unit, caps, unresolved."""
    merged = sorted(u["id"] for u in roadmap.values() if u.get("status") == "merged")
    stuck = sorted((u["id"], u.get("status", "?")) for u in roadmap.values()
                   if u.get("status") in ("queued", "pr_open", "building", "todo",
                                          "parked", "parked-final",
                                          "design-blocked"))
    # Tokens per unit: prefer the telemetry log's per-unit totals; fall back to
    # the unit's own counter / usage files when the log has nothing for it.
    tel = telemetry_unit_totals()
    delivered = []
    for u in roadmap.values():
        if u.get("status") != "merged":
            continue
        delivered.append(tel.get(u["id"]) or unit_tokens(u))
    med = _median(delivered)
    over_cap = sorted(u["id"] for u in roadmap.values()
                      if int(u.get("tokens", 0)) >= PER_UNIT_TOKEN_CAP)
    # Today's tokens: the telemetry log is the source of truth (item 6).
    day = telemetry_day_totals(state.get("day", ""))
    tokens_today = int(day.get("tokens") or 0)
    tokens_src = "runs.jsonl"
    if not tokens_today:
        tokens_today = int(state.get("tokens_today", 0))
        tokens_src = "state counter"
    over_daily = tokens_today >= DAILY_TOKEN_CAP
    cap = effective_merge_cap(state)
    cap_note = (f" (reverted from {MAX_MERGE_PER_DAY} after two nightly "
                f"failures)" if cap != MAX_MERGE_PER_DAY else "")
    caps = (f"merged {state['merged_today']}/{cap}{cap_note}; "
            f"tokens {tokens_today}/{DAILY_TOKEN_CAP} (from {tokens_src})"
            + ("; DAILY TOKEN CAP HIT" if over_daily else "")
            + f"; per-unit {PER_UNIT_TOKEN_CAP}"
            + (f"; over per-unit cap: {', '.join(over_cap)}" if over_cap else ""))
    unresolved = []
    open_prs = sorted((u["id"], int(u.get("pr") or 0)) for u in roadmap.values()
                      if int(u.get("pr") or 0) and u.get("status") != "merged")
    if open_prs:
        unresolved.append("open PRs not yet merged: " +
                          ", ".join(f"{i} (#{p})" for i, p in open_prs))
    if STOP_FILE.exists():
        unresolved.append("STOP file present")
    if not MERGE_GATE_IS_LOCAL:
        unresolved.append("merge gate is not local")
    splits = sorted(u["id"] for u in roadmap.values() if u.get("split_requested"))
    if splits:
        unresolved.append("awaiting a split: " + ", ".join(splits))
    if not unresolved:
        unresolved.append("none")
    return [
        f"1. Merged ({len(merged)}): "
        + (", ".join(merged) if merged else "nothing yet"),
        f"2. Stuck ({len(stuck)}): "
        + (", ".join(f"{i}={s}" for i, s in stuck) if stuck else "nothing"),
        f"3. Tokens per unit (median of merged): {med} "
        f"(n={len(delivered)}{', from runs.jsonl' if tel else ''})",
        f"4. Caps: {caps}",
        f"5. Unresolved: " + "; ".join(unresolved),
    ]


def diagnosis_lines(roadmap: dict, state: dict) -> list:
    """The five-line diagnosis requested for the STATE.md report.

    Answers, in order: why each parked unit is parked; which F units (F31+) are
    todo/design and what blocks them; whether a cap or the STOP file is active;
    whether the timer ran in the last hour; and whether dispatch resumes.
    """
    def _is_f(uid: str) -> bool:
        return uid.startswith("F") and uid[1:].isdigit() and int(uid[1:]) >= 31

    # 1. parked units and the exact reason
    parked = sorted((u for u in roadmap.values() if u.get("status") == "parked"),
                    key=lambda u: u["id"])
    parked_final = sorted((u for u in roadmap.values()
                           if u.get("status") == "parked-final"), key=lambda u: u["id"])
    if parked or parked_final:
        parts = [f"{u['id']} parked (attempts {u.get('attempts',0)}, "
                 f"{str(u.get('reason','') or 'no reason recorded')[:80]})"
                 for u in parked]
        parts += [f"{u['id']} parked-final "
                  f"({str(u.get('reason','') or 'no reason recorded')[:70]})"
                  for u in parked_final]
        line1 = "1. Parked: " + "; ".join(parts)
    else:
        line1 = "1. Parked: none"

    # 2. F31+ units not yet merged, and what holds them
    f_open = sorted((u for u in roadmap.values() if _is_f(u.get("id", ""))
                     and u.get("status") != "merged"), key=lambda u: u["id"])
    if not f_open:
        line2 = "2. F31+ open: none"
    else:
        bits = []
        for u in f_open[:6]:
            blockers = [str(d) for d in (u.get("depends_on") or [])
                        if (roadmap.get(str(d)) or {}).get("status") != "merged"]
            why = ("blocked on " + ", ".join(blockers)) if blockers else (
                "waiting for a planner pass" if u.get("status") == "design"
                else str(u.get("reason", "") or "ready")[:40])
            bits.append(f"{u['id']}={u.get('status')} ({why})")
        more = f"; +{len(f_open)-6} more" if len(f_open) > 6 else ""
        line2 = (f"2. F31+ open ({len(f_open)}): " + "; ".join(bits) + more)

    # 3. caps and STOP
    merged = int(state.get("merged_today", 0))
    tokens = int(state.get("tokens_today", 0))
    cap = effective_merge_cap(state)
    caps = []
    if merged >= cap:
        caps.append(f"daily merge cap HIT ({merged}/{cap})")
    if tokens >= DAILY_TOKEN_CAP:
        caps.append(f"daily token cap HIT ({tokens}/{DAILY_TOKEN_CAP})")
    cap_txt = "; ".join(caps) if caps else (
        f"caps not in effect (merged {merged}/{cap}, "
        f"tokens {tokens}/{DAILY_TOKEN_CAP})")
    stop_txt = "STOP file PRESENT" if STOP_FILE.exists() else "no STOP file"
    line3 = f"3. {cap_txt}; {stop_txt}"

    # 4. whether the timer ran in the last hour (newest cycle-start event)
    last = ""
    for e in reversed(state.get("events", [])):
        if str(e.get("msg", "")).startswith("cycle start"):
            last = e.get("ts", "")
            break
    if last:
        try:
            age = (datetime.now(timezone.utc) - datetime.strptime(
                last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds()
            line4 = (f"4. Timer: last cycle {last} "
                     f"({int(age//60)} min ago) - "
                     f"{'ran within the last hour' if age < 3600 else 'NOT in the last hour'}")
        except Exception:
            line4 = f"4. Timer: last cycle {last}"
    else:
        line4 = "4. Timer: no cycle recorded yet"

    # 5. does dispatch resume? (lightweight readiness: no Jev call, no state
    #    mutation - diagnosis must not change the thing it reports on)
    cap = effective_merge_cap(state)
    ready = [u for u in roadmap.values()
             if u.get("status") == "todo" and not u.get("split_requested")
             and deps_merged(u, roadmap)
             and int(u.get("tokens", 0)) < PER_UNIT_TOKEN_CAP
             and int(state.get("merged_today", 0)) < cap
             and int(state.get("tokens_today", 0)) < DAILY_TOKEN_CAP]
    if any(not is_advisory(u) for u in ready):
        ready = [u for u in ready if not is_advisory(u)]  # QA waits for real work
    elif ready and planner_pending(roadmap):
        ready = []                                       # promotion beats QA
    active = [u["id"] for u in roadmap.values()
              if u.get("status") in ("building", "pr_open", "queued")]
    if active:
        line5 = f"5. Dispatch: running/dispatched: {', '.join(sorted(active))}"
    elif ready:
        line5 = ("5. Dispatch: ready to resume this cycle: "
                 + ", ".join(sorted(u["id"] for u in ready)))
    else:
        line5 = ("5. Dispatch: nothing ready this cycle - "
                 + (f"{sum(1 for u in roadmap.values() if u.get('status')=='design')} "
                    "design units await the planner (one promotion per cycle)"
                    if any(u.get("status") == "design" for u in roadmap.values())
                    else "no todo/design work remains"))
    return [line1, line2, line3, line4, line5]


def write_state_md(roadmap: dict, state: dict) -> None:
    counts: dict = {}
    for u in roadmap.values():
        counts[u.get("status", "?")] = counts.get(u.get("status", "?"), 0) + 1
    lines = [
        "# PHP-Retro pipeline state",
        "",
        f"updated: {now()}",
        f"day: {state['day']}  merged_today: {state['merged_today']}/{effective_merge_cap(state)}"
        f"  tokens_today: {state['tokens_today']}/{DAILY_TOKEN_CAP}",
        f"STOP file: {'PRESENT - dispatch halted' if STOP_FILE.exists() else 'absent'}",
        f"merge gate: {MERGE_GATE_DESCRIPTION}",
        "",
        "## Report",
        "",
    ]
    lines += report_lines(roadmap, state)
    lines += ["", "## Diagnosis", ""]
    lines += [f"- {l}" for l in diagnosis_lines(roadmap, state)]
    lines += ["", "## Quality", ""]
    lines += quality_lines(roadmap)
    lines += ["", "## Telemetry", ""]
    lines += telemetry_lines(state)
    lines += ["", "## Jev", ""]
    lines += jev_lines()
    lines += ["", "## Token Terminator (builder context engine)", ""]
    lines += tt_lines()
    lines += ["", "## Nightly checks", ""]
    lines += nightly_lines()
    lines += ["", "## Alerts", ""]
    lines += alerts_lines()
    lines += ["", "## Counts by status", ""]
    for k in sorted(counts):
        lines.append(f"- {k}: {counts[k]}")
    lines += ["", "## Units", "",
              "| id | kind | sev | status | attempts | model | tokens | pr | coverage | fidelity | reason |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    q = read_json(QUALITY_JSON, {})
    for uid in sorted(roadmap):
        u = roadmap[uid]
        reason = str(u.get("reason", "")).replace("|", "/")[:100]
        series = (q.get(uid) or {}).get("coverages") or []
        cov = f"{series[-1]}%" if series else "-"
        fid = (u.get("fidelity") or (q.get(uid) or {}).get("fidelity") or "-")
        lines.append(f"| {uid} | {u.get('kind','') or '-'} | {u.get('severity','') or '-'} | "
                     f"{u.get('status','')} | {u.get('attempts',0)} | "
                     f"{u.get('model','') or '-'} | {u.get('tokens',0)} | "
                     f"{u.get('pr',0) or '-'} | {cov} | {fid} | {reason} |")
    lines += ["", "## Last 20 events", ""]
    for e in state["events"][-20:]:
        lines.append(f"- {e['ts']}  {e['msg']}")
    STATE_MD.write_text("\n".join(lines) + "\n")


def configure_jev_accounting(state: dict, roadmap: dict) -> None:
    mod = _load_jev()
    if mod is None:
        return
    def before(uid):
        try:
            return admit_paid(state, roadmap.get(uid), "jev", limit=36864)
        except BudgetDenied:
            return None
    def after(rid, uid, usage, failed):
        tokens = usage_tokens(usage or {})
        if not usage or tokens <= 0:
            tokens = 36864
        log_model_run("jev", mod.JEV_MODEL, uid, None, 1 if failed else 0,
                      "provider_error" if failed else "other", usage or {},
                      ts_start=state["reservations"][rid]["ts_start"], run_id=rid, charged_tokens=tokens,
                      provider_override="openrouter")
        release_paid(state, rid)
        add_tokens(state, roadmap.get(uid, {}), tokens)
        write_json(STATE_JSON, state)
    mod.CONTROL_BEFORE = before
    mod.CONTROL_AFTER = after


def reconcile_deliveries(roadmap: dict, state: dict) -> list[str]:
    rc, out = sh(["gh", "pr", "list", "--repo", GH_REPO, "--state", "merged", "--limit", "1000",
                  "--json", "number,headRefName,mergeCommit,mergedAt"], cwd=REPO, timeout=120)
    if rc:
        raise DeliveryUnavailable("Git delivery reconciliation unavailable; dispatch deferred")
    try:
        prs = json.loads(out)
        if not isinstance(prs, list) or len(prs) >= 1000:
            raise ValueError("incomplete delivery inventory")
    except ValueError as exc:
        raise control.IntegrityError("invalid delivery inventory") from exc
    accepted = {}
    for pr in sorted(prs, key=lambda r: r.get("mergedAt") or ""):
        branch, commit = pr.get("headRefName", ""), (pr.get("mergeCommit") or {}).get("oid", "")
        uid = branch[5:] if branch.startswith("unit/") else next((uid for uid, u in roadmap.items() if u.get("branch") == branch), "")
        if uid not in roadmap or not commit:
            continue
        if git("merge-base", "--is-ancestor", commit, "origin/main")[0] != 0:
            raise control.IntegrityError("merged PR is not an ancestor of fetched main: " + uid)
        accepted[uid] = pr
    changed = []
    for uid, pr in accepted.items():
        u = roadmap[uid]
        if u.get("status") == "merged":
            continue
        previous = dict(u)
        commit = pr["mergeCommit"]["oid"]
        control.append_record(STATE_DIR / "reconciliation.jsonl", {
            "ts": now(), "unit": uid, "previous": previous, "pr": pr["number"], "commit": commit})
        control.append_record(STATE_DIR / "runs.jsonl", {"record_type": "delivery", "count_merge": False,
            "unit": uid, "pr": pr["number"], "head": commit, "merged_at": pr["mergedAt"]})
        u.update(status="merged", pr=pr["number"], delivery_commit=commit, updated=now(),
                 split_requested=False, reason=f"reconciled from Git PR #{pr['number']}; history preserved")
        changed.append(uid)
        event(state, f"{uid}: reconciled Git-merged PR #{pr['number']}; never redispatch")
    if changed:
        save_roadmap(roadmap)
        write_json(STATE_JSON, state)
    return changed


def cycle(*, no_dispatch: bool = False) -> None:
    ensure_dirs()
    if STOP_FILE.exists() and not no_dispatch:
        log("STOP file present; dispatch halted")
        return
    with (LOCK_DIR / "orchestrator.lock").open("w") as fh:
        if not _try_lock(fh):
            log("another cycle is running; skipping")
            return
        try:
            state = load_state()
            rollover(state)
            roadmap = load_roadmap(state)
            bootstrap_accounting(state, roadmap)
            event(state, f"cycle start (merged_today={state['merged_today']}, tokens_today={state['tokens_today']})")
            apply_merge_cap_guard(state)
            rc, out = git("fetch", "origin", "--prune")
            if rc:
                raise DeliveryUnavailable("git fetch failed; reconciliation deferred")
            reconcile_deliveries(roadmap, state)
            configure_jev_accounting(state, roadmap)
            if not no_dispatch:
                for u in roadmap.values():
                    if u.get("status") == "building":
                        u["status"] = "todo"
                history = load_history()
                if paid_allowed(state, None, "builder"):
                    for u in roadmap.values():
                        if u.get("status") != "todo" or int(u.get("attempts", 0)) == 0:
                            continue
                        entry = history.get(u["id"])
                        if entry and entry.get("outcome") == "no-change":
                            continue
                        recover_branch(u, history, state)
                    resume_open_prs(roadmap, state)
                dispatch(roadmap, state)
                queue_nightly_fixes(roadmap, state)
                maybe_refactor_unit(roadmap, state)
                used_agent = maybe_plan_nightly_fix(roadmap, state)
                if not used_agent:
                    used_agent = maybe_plan(roadmap, state)
                if not used_agent:
                    maybe_audit(roadmap, state)
            else:
                event(state, "dispatch-disabled maintenance cycle: no workers, review or merges")
            save_roadmap(roadmap)
            event(state, "cycle end")
            write_json(STATE_JSON, state)
            write_state_md(roadmap, state)
        except DeliveryUnavailable as exc:
            event(state, str(exc))
            write_json(STATE_JSON, state)
            write_state_md(roadmap, state)
            return
        except (control.IntegrityError, OSError) as exc:
            STOP_FILE.touch()
            control.atomic_json(STATE_DIR / "integrity-failure.json", {"ts": now(), "reason": str(exc)})
            control.atomic_text(STATE_MD, f"Pipeline STOP: {exc}\nAccounting recovery requires a validated append-only ledger.\n")
            raise


def _try_lock(fh) -> bool:
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def run_ops_tests() -> int:
    """Run the ops/ regression suite (ops/tests/run_all.sh).

    Returns the suite's exit code. ``PHPRETRO_SKIP_OPS_TESTS=1`` skips it when a
    caller (the nightly self-check) already ran it as its own check, so the suite
    is never run twice in one job. ``PHPRETRO_OPS_TESTS`` overrides the script
    path, which lets the suite's own tests point it at a deliberately red copy.
    """
    if os.environ.get("PHPRETRO_SKIP_OPS_TESTS") == "1":
        return 0
    script = Path(os.environ.get("PHPRETRO_OPS_TESTS",
                                 Path(__file__).with_name("tests") / "run_all.sh"))
    if not script.exists():
        # Fail closed: a missing suite is a broken wiring, not a pass.
        log(f"ops tests: MISSING {script}")
        return 2
    rc, out = sh(["bash", str(script)], cwd=REPO, timeout=900)
    tail = "\n".join(out.strip().splitlines()[-25:])
    print(tail, flush=True)
    return rc


def selftest() -> int:
    doc = parse_yaml('''
version: 1
units:
  - id: F1
    title: "A, B and C"
    status: merged
    depends_on: []
    paths: [a/b.go, c/*.ts]
    tests: ["go test ./a/..."]
    acceptance: ["one", "two"]
    attempts: 0
  - id: F2
    title: Second
    status: todo
    depends_on: [F1]
    paths: [d/e.go]
    acceptance: []
    attempts: 3
''')
    units = doc["units"]
    assert len(units) == 2, units
    assert units[0]["paths"] == ["a/b.go", "c/*.ts"], units[0]
    assert units[0]["title"] == "A, B and C", units[0]
    assert units[0]["depends_on"] == []
    assert units[1]["depends_on"] == ["F1"]
    assert units[1]["attempts"] == 3
    # block-list values (a model's natural YAML) must not become units
    block = parse_yaml('''
units:
  - id: QA1
    title: "one"
    acceptance:
      - first bullet
      - second bullet
    paths: [a/b.go]
    size: M
  - id: QA2
    title: "two"
    paths: [c/d.go]
''')
    assert len(block["units"]) == 2, block["units"]
    assert block["units"][0]["id"] == "QA1", block["units"][0]
    assert block["units"][0]["acceptance"] == ["first bullet", "second bullet"], \
        block["units"][0]["acceptance"]
    assert block["units"][0]["size"] == "M"
    assert block["units"][1]["id"] == "QA2", block["units"][1]
    assert block["units"][1]["title"] == "two", block["units"][1]
    # a mix of flow and block lists in one entry
    mixed = parse_yaml('''
units:
  - id: X1
    title: t
    paths:
      - internal/a
      - internal/b
    depends_on: [F1]
    acceptance:
      - one
''')
    assert mixed["units"][0]["paths"] == ["internal/a", "internal/b"], mixed["units"][0]
    assert mixed["units"][0]["depends_on"] == ["F1"], mixed["units"][0]
    assert mixed["units"][0]["acceptance"] == ["one"], mixed["units"][0]
    # runtime state survives a save/load round trip (PR number, attempts, reason)
    units[1].update({"pr": 61, "tokens": 1234, "reason": "check.sh failed: x | y",
                     "model": "gpt-6-luna", "review_rounds": 1})
    round_trip = parse_yaml("version: 1\nunits:\n" + dump_unit_yaml(units[1]) + "\n")
    got = round_trip["units"][0]
    assert got["pr"] == 61, got
    assert got["tokens"] == 1234, got
    assert got["reason"] == "check.sh failed: x | y", got
    assert got["review_rounds"] == 1, got
    assert got["depends_on"] == ["F1"], got
    assert paths_overlap(["internal/home/**"], ["internal/home/home.go"])
    assert not paths_overlap(["internal/home/**"], ["internal/account/**"])
    assert reviewer_model_for(MODEL["luna"]) == MODEL["deepseek"]
    assert reviewer_model_for(MODEL["deepseek"]) == MODEL["luna"]
    assert model_for_attempt(1) == MODEL["luna"]
    assert model_for_attempt(3) == MODEL["deepseek"]
    assert model_for_attempt(4) == MODEL["sol"]
    # diff guard: protected paths and out-of-scope paths are rejected, the
    # unit's own listed paths (including its delivery note) are not.
    allowed = ["internal/registration", "docs/units/F25.md"]
    assert guard_violations(["internal/registration/x.go"], allowed) == []
    assert guard_violations(["docs/units/F25.md"], allowed) == []
    assert guard_violations(["ops/orchestrator.py"], allowed) == \
        [("ops/orchestrator.py", "protected path")]
    assert guard_violations(["scripts/check.sh"], allowed) == \
        [("scripts/check.sh", "protected path")]
    assert guard_violations([".github/workflows/go-security.yml"], allowed) == \
        [(".github/workflows/go-security.yml", "protected path")]
    assert guard_violations(["internal/profile/profile.go"], allowed) == \
        [("internal/profile/profile.go", "outside the unit's listed paths")]
    # the unit's own delivery note is always permitted, even when its paths omit
    # it (the brief requires the builder to write docs/units/<id>.md)...
    assert guard_violations(["docs/units/F25.md"], ["internal/registration"], "F25") == []
    # ...but another unit's note is still out of scope
    assert guard_violations(["docs/units/F26.md"], ["internal/registration"], "F25") == \
        [("docs/units/F26.md", "outside the unit's listed paths")]
    # a split keeps the replacements inside the parent's paths and sizes
    roadmap = {"F9": {"id": "F9", "title": "big", "paths": ["internal/big"],
                      "status": "todo", "split_requested": True,
                      "planner_retries": 0}}
    plan = ('units:\n'
            '  - id: F9a\n'
            '    title: "part one"\n'
            '    size: S\n'
            '    paths: [internal/big/a.go]\n'
            '    depends_on: []\n'
            '  - id: F9b\n'
            '    title: "part two"\n'
            '    size: M\n'
            '    paths: [internal/big/b.go]\n'
            '    depends_on: [F9]\n')
    assert apply_planner_output(roadmap, {}, roadmap["F9"], plan,
                                old_id="F9", mode="split")
    assert roadmap["F9a"]["status"] == "todo"
    assert roadmap["F9a"]["attempts"] == 0
    assert roadmap["F9b"]["depends_on"] == ["F9a"], roadmap["F9b"]["depends_on"]
    assert roadmap["F9b"]["branch"] == ""
    # an L is never accepted as a replacement
    l_plan = ('units:\n  - id: F9c\n    title: "too big"\n    size: L\n'
              '    paths: [internal/big/c.go]\n')
    assert not apply_planner_output({}, {}, {}, l_plan, old_id="F9", mode="split")
    # more replacements than the split cap are rejected
    many = "units:\n" + "".join(
        f'  - id: F9{i}\n    title: "p{i}"\n    size: S\n'
        f'    paths: [internal/big/{i}.go]\n' for i in range(SPLIT_MAX_UNITS + 1))
    assert not apply_planner_output({}, {}, {}, many, old_id="F9", mode="split")
    assert _median([100, 0, 300]) == 200   # a recorded 0 is not a data point
    assert _median([100, 200]) == 150
    assert _median([]) == 0

    # Everything else the pipeline depends on lives in ops/tests/ and is run
    # below: the diff base, the diff guard, advisory units, planner
    # non-starvation, the split deadlock, timeout accounting, the pre-push hook
    # through a real push, the alert streaks, the Jev fail-open paths and the
    # quality gates. Add a test there when ops/ code changes - not here.

    # The ops/ regression suite (ops/tests/run_all.sh). A failure here fails the
    # self-check, which is what drives the nightly alert.
    if run_ops_tests() != 0:
        print("ops tests FAILED", flush=True)
        return 1

    print("selftest OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="PHP-Retro autonomous unit pipeline")
    ap.add_argument("--once", action="store_true", help="run one cycle")
    ap.add_argument("--no-dispatch", action="store_true", help="reconcile state only; no paid roles or merges")
    ap.add_argument("--status", action="store_true", help="print live state")
    ap.add_argument("--selftest", action="store_true", help="exercise the parser")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.status:
        if STATE_MD.exists():
            print(STATE_MD.read_text())
        else:
            print("no state yet")
        return 0
    cycle(no_dispatch=args.no_dispatch)
    return 0


if __name__ == "__main__":
    sys.exit(main())

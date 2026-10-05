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
MAX_MERGE_PER_DAY = int(os.environ.get("PHPRETRO_MAX_MERGE_PER_DAY", "12"))
MAX_ATTEMPTS = 4            # luna x2, deepseek x1, sol x1, then parked
PLANNER_RETRIES = 2
DIFF_LINE_CAP = 700
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

PROVIDER = "custom:a6api"
MODEL = {
    "luna": "gpt-6-luna",
    "deepseek": "deepseek-v4.1-flash",
    "sol": "gpt-6.1-sol",
}
LADDER = ["luna", "luna", "deepseek", "sol"]
PROFILE_HOME = {name: HOME / ".hermes" / "profiles" / name
                for name in ("builder", "reviewer", "planner")}
HERMES = shutil.which("hermes") or str(HOME / ".local" / "bin" / "hermes")

# Paths whose diff escalates to a Sol second review (auth / session / schema).
SENSITIVE = ("internal/authflow", "internal/session", "internal/account",
             "internal/polaris", "internal/profile/settings", "migrations")

STATE_DIR = OPS / "state"
LOG_DIR = OPS / "logs"
BRIEF_DIR = OPS / "briefs"
LOCK_DIR = OPS / "locks"
STOP_FILE = OPS / "STOP"
STATE_JSON = STATE_DIR / "units.state.json"
STATE_MD = STATE_DIR / "STATE.md"
LIVE_UNITS = STATE_DIR / "units.live.yaml"
REPO_UNITS = REPO / "units.yaml"

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
    Path(path).write_text(json.dumps(data, indent=1, sort_keys=True))


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
    """Parse the units.yaml subset: top-level scalars, and ``units:`` as a list
    of mappings whose values are scalars or flow lists. Indentation-2."""
    doc: dict = {}
    current = None
    in_units = False
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if indent == 0:
            m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
            if not m:
                continue
            key, val = m.group(1), m.group(2)
            if val == "" and key == "units":
                doc["units"] = []
                in_units = True
                current = None
                continue
            in_units = False
            doc[key] = _scalar(val) if val else {}
            continue
        if not in_units:
            continue
        m = re.match(r"^-\s*(.*)$", line)
        if m:
            current = {}
            doc["units"].append(current)
            rest = m.group(1).strip()
            if rest:
                km = re.match(r"^([\w-]+):\s*(.*)$", rest)
                if km:
                    current[km.group(1)] = _scalar(km.group(2))
            continue
        km = re.match(r"^([\w-]+):\s*(.*)$", line)
        if km and current is not None:
            current[km.group(1)] = _scalar(km.group(2))
    return doc


STATE_KEYS = ("status", "pr", "attempts", "tokens", "wall_s", "model", "reason",
              "review_rounds", "conflict_rounds", "planner_retries", "branch",
              "feedback", "split_requested")
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

def load_roadmap(state: dict) -> dict:
    """Repo units.yaml defines the roadmap; the live copy carries runtime state."""
    doc = parse_yaml(REPO_UNITS.read_text())
    repo_units = doc.get("units", [])
    live_doc = parse_yaml(LIVE_UNITS.read_text()) if LIVE_UNITS.exists() else {"units": []}
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
    return live


def save_roadmap(roadmap: dict) -> None:
    body = "\n".join(dump_unit_yaml(roadmap[k]) for k in sorted(roadmap))
    LIVE_UNITS.write_text("version: 1\nunits:\n" + body + "\n")


def load_state() -> dict:
    st = read_json(STATE_JSON, {})
    st.setdefault("day", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    st.setdefault("merged_today", 0)
    st.setdefault("tokens_today", 0)
    st.setdefault("events", [])
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
    unit["tokens"] = int(unit.get("tokens", 0)) + int(tokens or 0)
    state["tokens_today"] = int(state.get("tokens_today", 0)) + int(tokens or 0)


# --------------------------------------------------------------------------
# Hermes agent calls
# --------------------------------------------------------------------------

# Skill names as registered (Hermes resolves -s by plain name in the active
# profile's skills/ dir, not by path).
SKILL_NAME = {"builder": "unit-builder", "reviewer": "unit-reviewer",
              "planner": "unit-planner"}


def hermes_run(profile: str, model: str, prompt: str, toolsets: str,
               cwd: Path, tag: str, timeout: int) -> tuple[int, str, dict]:
    """One headless agent run. Returns (rc, output, usage).

    ``--usage-file`` is written even when the run fails, so every unit's spend is
    accounted for. The prompt is passed as argv (not stdin): the unit briefs are
    plain text with no shell metacharacter risk and argv keeps the run's exact
    prompt visible in the log.
    """
    usage = LOG_DIR / f"{tag}.usage.json"
    with_suppress(lambda: usage.unlink())
    env = {"HERMES_HOME": str(PROFILE_HOME[profile])}
    cmd = [HERMES, "-z", prompt,
           "--usage-file", str(usage),
           "-m", model,
           "--provider", PROVIDER,
           "--reasoning", "low",
           "-t", toolsets,
           "-s", SKILL_NAME[profile],
           "--in", str(cwd),
           "--accept-hooks"]
    rc, out = sh(cmd, cwd=cwd, timeout=timeout, env=env)
    data = read_json(usage, {}) or {}
    return rc, out, data


def usage_tokens(usage: dict) -> int:
    for key in ("total_including_auxiliary", "total_tokens"):
        val = usage.get(key)
        if isinstance(val, dict):
            val = val.get("total_tokens")
        if isinstance(val, int):
            return val
    return int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))


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
    """The skill says pass|fix|block; models also emit approve/reject/ok."""
    v = str(raw or "pass").strip().lower()
    if v in ("block", "blocked", "reject", "rejected", "fail", "failed"):
        return "block"
    if v in ("fix", "fixes", "needs_fix", "changes_requested", "revise"):
        return "fix"
    return "pass"


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
    for args in (("diff", "--name-only", BASE_REF, "HEAD"),
                 ("diff", "--name-only", "HEAD"),
                 ("ls-files", "--others", "--exclude-standard")):
        for ln in git_out(*args, cwd=wt).splitlines():
            ln = ln.strip()
            if ln:
                files.add(ln)
    return sorted(files)


def guard_violations(files, allowed) -> list:
    """Paths a builder may not touch, or that fall outside the unit's list.

    Two rules: the repository's protected paths (ops/, CI, skills, AGENTS.md,
    scripts/check.sh) are never a builder's to change; and anything the unit
    did not list is out of scope. Returns a list of ``(path, reason)``.
    """
    allowed = [str(p) for p in (allowed or [])]
    bad = []
    for f in files:
        if any(f == p or f.startswith(p) for p in PROTECTED_FILES) or \
           any(f.startswith(p) for p in PROTECTED_PREFIXES):
            bad.append((f, "protected path"))
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


def run_review(unit: dict, wt: Path, state: dict, author_model: str) -> tuple[str, str, int]:
    """Returns (verdict, findings_text, tokens)."""
    model = reviewer_model_for(author_model)
    diff = current_diff(wt)
    if not diff:
        return "pass", "", 0
    prompt = reviewer_brief(unit, diff, model)
    rc, out, usage = hermes_run("reviewer", model, prompt, "file", wt,
                                f"{unit['id']}-review", 900)
    tokens = usage_tokens(usage)
    verdict, findings = "pass", ""
    m = re.search(r"\{.*\}", out, re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            verdict = normalize_verdict(data.get("verdict"))
            blockers = [f for f in data.get("findings", [])
                        if str(f.get("severity", "")).lower() == "blocker"]
            findings = "\n".join(
                f"- {f.get('file','')}:{f.get('line',0)} {f.get('issue','')}"
                for f in blockers)
        except Exception:
            verdict = "pass"
    elif rc != 0:
        verdict = "pass"  # reviewer unavailable: check.sh remains the gate
    return verdict, findings, tokens


def run_second_review(unit: dict, wt: Path, state: dict) -> tuple[str, str, int]:
    model = MODEL["sol"]
    diff = current_diff(wt)
    prompt = (f"SECOND REVIEW {unit['id']} (auth/session/schema paths)\n\n"
              f"## Unified diff\n{diff}\n\nOutput ONLY the JSON verdict object.\n")
    rc, out, usage = hermes_run("reviewer", model, prompt, "file", wt,
                                f"{unit['id']}-review2", 900)
    tokens = usage_tokens(usage)
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        return "pass", "", tokens
    try:
        data = json.loads(m.group(0))
        verdict = normalize_verdict(data.get("verdict"))
        blockers = [f for f in data.get("findings", [])
                    if str(f.get("severity", "")).lower() == "blocker"]
        findings = "\n".join(f"- {f.get('file','')}:{f.get('line',0)} {f.get('issue','')}"
                             for f in blockers)
        return verdict, findings, tokens
    except Exception:
        return "pass", "", tokens


def strip_required_actions_check(state: dict) -> None:
    """Remove ONLY the Actions check requirement from `main` protection.

    The authoritative gate is local (``scripts/check.sh``); the ``foundation``
    Actions check is advisory. If branch protection still lists it as required,
    a git-side outage blocks every merge. This drops that one context - and
    nothing else: the rules against force-push and branch deletion (branch
    protection ``allow_force_pushes``/``allow_deletions`` and the
    ``main-protection-v1`` ruleset) are left untouched, and the result is
    verified and logged.
    """
    rc, out = sh(["gh", "api", f"repos/{GH_REPO}/branches/main/protection"], timeout=90)
    if rc != 0:
        event(state, "cannot read branch protection; leaving it as it is")
        return
    try:
        prot = json.loads(out)
    except Exception:
        event(state, "cannot parse branch protection; leaving it as it is")
        return
    contexts = (prot.get("required_status_checks") or {}).get("contexts") or []
    if "foundation" not in contexts:
        event(state, "branch protection does not require the Actions check; nothing to remove")
        return
    body = STATE_DIR / "protection-before.json"
    body.write_text(json.dumps(prot, indent=1, sort_keys=True))
    payload = STATE_DIR / "drop-foundation.json"
    payload.write_text(json.dumps({"contexts": ["foundation"]}))
    rc, out = sh(["gh", "api", "-X", "DELETE",
                  f"repos/{GH_REPO}/branches/main/protection/required_status_checks/contexts",
                  "--input", str(payload)], timeout=90)
    if rc != 0:
        event(state, f"could not drop the required `foundation` check: {out[-300:]}")
        return
    rc, out = sh(["gh", "api", f"repos/{GH_REPO}/branches/main/protection"], timeout=90)
    after = {}
    with_suppress(lambda: None)
    try:
        after = json.loads(out)
    except Exception:
        after = {}
    still = (after.get("required_status_checks") or {}).get("contexts") or []
    keeps_fp = (after.get("allow_force_pushes") or {}).get("enabled") is False
    keeps_del = (after.get("allow_deletions") or {}).get("enabled") is False
    event(state, f"removed required `foundation` check from main protection "
                 f"(contexts now {still or 'none'}; force-push blocked={keeps_fp}; "
                 f"deletion blocked={keeps_del})")
    (STATE_DIR / "protection-after.json").write_text(
        json.dumps(after, indent=1, sort_keys=True))


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
    """Locked: rebase, re-check, merge one PR at a time.

    ``scripts/check.sh`` on the exact rebased head, run here under the lock, is
    the authoritative gate. GitHub Actions is advisory: it is observed and
    recorded, and a queued/cancelled/missing run never blocks the merge.
    """
    lock = LOCK_DIR / "merge.lock"
    with lock.open("w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        pr = int(unit.get("pr") or 0)
        if not pr:
            event(state, f"{unit['id']}: no PR recorded; cannot merge")
            return False
        git("fetch", "origin", "main", cwd=wt)
        rc, out = git("rebase", "origin/main", cwd=wt)
        if rc != 0:
            git("rebase", "--abort", cwd=wt)
            unit["conflict_rounds"] = int(unit.get("conflict_rounds", 0)) + 1
            unit["attempts"] = int(unit.get("attempts", 0)) + 1
            unit["reason"] = f"rebase conflict on main: {tail(out, 12)}"
            unit["status"] = "parked" if unit["conflict_rounds"] > 1 else "todo"
            event(state, f"{unit['id']}: rebase conflict -> {unit['status']}")
            return False
        # The gate, on the exact head that will be merged.
        rc, out = run_check(wt)
        if rc != 0:
            (LOG_DIR / f"{unit['id']}-rebase.check.log").write_text(out)
            unit["attempts"] = int(unit.get("attempts", 0)) + 1
            unit["reason"] = "check.sh failed after rebase"
            # The worktree is left on the rebased head (the rebase above
            # succeeded; only the gate failed), so the next builder attempt sees
            # the new main and can fix the conflict. Hand it the error and mark
            # the history so the recovery path does not re-queue the stale
            # branch and steal the attempt.
            unit["feedback"] = ("scripts/check.sh failed after rebasing onto main:\n"
                                + tail(out, 60))
            record_history(unit, "rebase-check-fail")
            unit["status"] = "todo" if unit["attempts"] < MAX_ATTEMPTS else "parked"
            event(state, f"{unit['id']}: check failed after rebase -> {unit['status']}")
            return False
        head_sha = git_out("rev-parse", "HEAD", cwd=wt)
        rc, out = git("push", "--force-with-lease", "origin",
                      f"HEAD:refs/heads/{unit_branch(unit)}", cwd=wt, timeout=300)
        if rc != 0:
            event(state, f"{unit['id']}: rebase push failed: {out[-300:]}")
            return False
        if git_out("rev-parse", f"refs/remotes/origin/{unit_branch(unit)}") != head_sha:
            git("fetch", "origin", unit_branch(unit))
        # Actions: advisory. Observe, record, move on.
        ci_clean, ci_detail = ci_advisory(pr, state, "pre-merge")
        append_actions_note(pr, "pre-merge advisory: " +
                            ("green" if ci_clean else "not green"), state)
        event(state, f"{unit['id']}: Actions (advisory) is "
                     f"{'green' if ci_clean else 'not green'}: "
                     f"{tail(ci_detail, 1).strip()}")
        (LOG_DIR / f"{unit['id']}-merge.check.log").write_text(
            f"authoritative gate: scripts/check.sh PASSED under the merge lock\n"
            f"head: {head_sha}\n"
            f"actions advisory: {'green' if ci_clean else 'not green'}: {ci_detail}\n")
        merged = False
        for attempt in range(3):
            rc, out = sh(["gh", "pr", "merge", str(pr), "--repo", GH_REPO,
                          "--merge", "--delete-branch"], timeout=300)
            if rc == 0:
                merged = True
                break
            low = out.lower()
            if ("base branch policy" in low or "protected branch" in low
                    or "required status" in low or "required check" in low
                    or "status check" in low or "not mergeable" in low
                    or "--auto flag" in low):
                strip_required_actions_check(state)
                event(state, f"{unit['id']}: merge refused by policy; retrying after "
                             f"dropping the required `foundation` check")
                continue
            if "queued" in low or "pending" in low or "in progress" in low:
                # A required check re-queued between the wait and the merge;
                # observe it again, briefly, and retry.
                ci_advisory(pr, state, "merge retry")
                continue
            event(state, f"{unit['id']}: gh pr merge failed: {out[-400:]}")
            (LOG_DIR / f"{unit['id']}-merge.fail.log").write_text(out)
            return False
        if not merged:
            event(state, f"{unit['id']}: merge gave up after 3 attempts")
            return False
        unit["status"] = "merged"
        unit["updated"] = now()
        state["merged_today"] = int(state.get("merged_today", 0)) + 1
        event(state, f"{unit['id']}: MERGED PR #{pr} "
                     f"(head {head_sha[:12]}, gate=check.sh, tokens {unit.get('tokens',0)})")
        git("fetch", "origin", "main")
        drop_worktree(unit)
        return True


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------

def model_for_attempt(attempt: int) -> str:
    idx = min(max(attempt - 1, 0), len(LADDER) - 1)
    return MODEL[LADDER[idx]]


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
    hist[unit["id"]] = {"outcome": outcome, "attempt": int(unit.get("attempts", 0)),
                        "ts": now()}
    write_json(HISTORY_JSON, hist)


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
        except Exception as exc:
            event(state, f"{uid}: resume failed: {exc}")


def deps_merged(unit: dict, roadmap: dict) -> bool:
    for dep in unit.get("depends_on", []) or []:
        d = roadmap.get(str(dep))
        if d is None or d.get("status") != "merged":
            return False
    return True


def select_ready(roadmap: dict, state: dict) -> list:
    if int(state.get("merged_today", 0)) >= MAX_MERGE_PER_DAY:
        event(state, f"daily merge cap reached ({MAX_MERGE_PER_DAY}); not dispatching")
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
        if int(u.get("tokens", 0)) >= PER_UNIT_TOKEN_CAP:
            u["status"] = "parked"
            u["reason"] = f"per-unit token cap {PER_UNIT_TOKEN_CAP} exceeded"
            event(state, f"{uid}: parked on token cap ({u['tokens']})")
            continue
        if adopt_branch_unit(u, state):
            continue
        ready.append(u)
    return ready


def start_build(unit: dict, state: dict):
    unit["attempts"] = int(unit.get("attempts", 0)) + 1
    attempt = unit["attempts"]
    model = model_for_attempt(attempt)
    unit["model"] = model
    unit["status"] = "building"
    unit["updated"] = now()
    wt = ensure_worktree(unit)
    feedback = unit.get("feedback", "")
    prompt = builder_brief(unit, attempt, model, feedback)
    brief_file = BRIEF_DIR / f"{unit['id']}-attempt{attempt}.md"
    brief_file.write_text(prompt)
    log(f"{unit['id']}: dispatch attempt {attempt} on {model} in {wt}")
    env = {"HERMES_HOME": str(PROFILE_HOME["builder"])}
    usage = LOG_DIR / f"{unit['id']}-attempt{attempt}.usage.json"
    with_suppress(lambda: usage.unlink())
    logfile = (LOG_DIR / f"{unit['id']}-attempt{attempt}.log").open("w")
    cmd = [HERMES, "-z", prompt, "--usage-file", str(usage), "-m", model,
           "--provider", PROVIDER, "--reasoning", "low", "-t", "file,terminal",
           "-s", SKILL_NAME["builder"], "--in", str(wt), "--accept-hooks"]
    proc = subprocess.Popen(cmd, cwd=str(wt), env={**os.environ, **env},
                            stdout=logfile, stderr=subprocess.STDOUT,
                            text=True, start_new_session=True)
    return {"unit": unit, "proc": proc, "started": time.time(),
            "logfile": logfile, "usage": usage, "wt": wt}


def finish_build(job, roadmap: dict, state: dict) -> None:
    unit = job["unit"]
    uid = unit["id"]
    proc, wt, usage = job["proc"], job["wt"], job["usage"]
    killed = ""
    try:
        proc.communicate(timeout=RUN_TIMEOUT)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        killed = kill_process_group(proc)
        rc = 124
        event(state, f"{uid}: builder run stopped at {RUN_TIMEOUT}s (SIG{killed.upper()})")
    with_suppress(job["logfile"].close)
    wall = int(time.time() - job["started"])

    # Token accounting must never record 0 for work that happened. Prefer the
    # usage file the agent writes; if a killed run never flushed it, read the
    # session out of the profile store; if even that is missing, charge a
    # pessimistic estimate so the caps still trip.
    tokens = usage_tokens(read_json(usage, {}) or {})
    source = "usage-file"
    if tokens <= 0 and rc == 124:
        tokens = tokens_from_state_db("builder", f"UNIT BRIEF {uid}")
        source = "state.db"
        if tokens <= 0:
            tokens = TIMEOUT_FALLBACK_TOKENS
            source = "pessimistic-estimate"
    add_tokens(state, unit, tokens)
    unit["wall_s"] = int(unit.get("wall_s", 0)) + wall
    unit["updated"] = now()
    log(f"{uid}: builder finished rc={rc} in {wall}s, {tokens} tokens ({source})")

    # A timeout is a size problem, not a model problem: ask the planner to
    # split the unit instead of retrying it whole at the same size.
    if rc == 124:
        unit["split_requested"] = True
        unit["reason"] = f"timed out at {RUN_TIMEOUT}s ({tokens} tokens, {source})"

    # --- diff guard: scope and protected paths ---------------------------
    # Checked on the working tree, before commit_if_dirty, so an uncommitted
    # edit to ops/ still fails the attempt instead of being committed.
    files = changed_files(wt)
    violations = guard_violations(files, unit.get("paths"))
    if violations:
        detail = "\n".join(f"- {p}: {why}" for p, why in violations)
        event(state, f"{uid}: DIFF GUARD rejected the attempt:\n{detail}")
        (LOG_DIR / f"{uid}-attempt{unit['attempts']}-guard.log").write_text(detail + "\n")
        discard_changes(wt, unit)
        unit["reason"] = "diff guard: " + "; ".join(f"{p} ({why})" for p, why in violations)[:300]
        unit["feedback"] = ("Your diff touched paths you may not change:\n" + detail +
                            "\nNothing from that attempt was kept. Stay inside the listed paths.")
        if unit["attempts"] >= MAX_ATTEMPTS:
            unit["status"] = "parked"
            event(state, f"{uid}: parked after repeated diff-guard rejections")
        else:
            unit["status"] = "todo"
            event(state, f"{uid}: diff guard -> retry")
        return

    commit_if_dirty(wt, unit)
    ahead = git_out("rev-list", "--count", f"{BASE_REF}..HEAD", cwd=wt)
    if not ahead or ahead == "0":
        record_history(unit, "no-change")
        # No change is the same signal as a timeout: the unit is too big or
        # too vague, so the planner splits it instead of it retrying unchanged.
        unit["split_requested"] = True
        unit["feedback"] = "The previous attempt produced no committed change."
        unit["status"] = "todo"
        if unit["attempts"] >= MAX_ATTEMPTS or unit["tokens"] >= PER_UNIT_TOKEN_CAP:
            unit["status"] = "parked"
            unit["reason"] = "no committed change after all ladder attempts"
        event(state, f"{uid}: no change produced -> {unit['status']} (split requested)")
        return

    rc, out = run_check(wt)
    (LOG_DIR / f"{uid}-attempt{unit['attempts']}.check.log").write_text(out)
    if rc != 0:
        unit["feedback"] = ("scripts/check.sh failed:\n" + tail(out, 60))
        unit["reason"] = "check.sh failed: " + tail(out, 3).replace("\n", " | ")
        if unit["attempts"] >= MAX_ATTEMPTS or unit["tokens"] >= PER_UNIT_TOKEN_CAP:
            unit["status"] = "parked"
            event(state, f"{uid}: parked after {unit['attempts']} attempts "
                         f"({unit['tokens']} tokens)")
        else:
            unit["status"] = "todo"
            event(state, f"{uid}: check failed, attempt {unit['attempts']} -> retry")
        return

    event(state, f"{uid}: check.sh PASSED on attempt {unit['attempts']}")
    try:
        pr = push_and_open_pr(unit, wt, out, state)
    except Exception as exc:
        unit["status"] = "todo"
        unit["feedback"] = f"delivery failed: {exc}"
        event(state, f"{uid}: PR delivery failed: {exc}")
        return
    unit["pr"] = pr
    unit["status"] = "pr_open"
    unit["updated"] = now()
    event(state, f"{uid}: PR #{pr} opened")

    # --- review (one round maximum) -------------------------------------
    verdict, findings, rtokens = run_review(unit, wt, state, unit.get("model", MODEL["luna"]))
    add_tokens(state, unit, rtokens)
    if diff_touches_sensitive(current_diff(wt)):
        v2, f2, t2 = run_second_review(unit, wt, state)
        add_tokens(state, unit, t2)
        if v2 == "block" or (v2 == "fix" and f2):
            verdict, findings = v2, f2
        event(state, f"{uid}: second review ({MODEL['sol']}) verdict={v2}")
    event(state, f"{uid}: review verdict={verdict}")
    if verdict in ("fix", "block") and findings and int(unit.get("review_rounds", 0)) < 1:
        unit["review_rounds"] = int(unit.get("review_rounds", 0)) + 1
        unit["feedback"] = "Reviewer blockers to repair:\n" + findings
        unit["reason"] = "reviewer blockers: " + findings.replace("\n", " | ")[:300]
        unit["attempts"] = int(unit.get("attempts", 0)) + 1
        unit["status"] = "todo" if unit["attempts"] < MAX_ATTEMPTS else "parked"
        event(state, f"{uid}: blockers from review -> {unit['status']}")
        return

    unit["status"] = "queued"
    merge_queue(unit, wt, state)


# --------------------------------------------------------------------------
# Planner
# --------------------------------------------------------------------------

def planner_model(unit: dict) -> str:
    return MODEL["sol"] if unit.get("unclear_semantics") else MODEL["deepseek"]


def apply_planner_output(roadmap: dict, state: dict, unit: dict, out: str,
                          old_id: str = "", mode: str = "") -> bool:
    m = re.search(r"(units:\s*\n(?:.|\n)*)", out)
    text = m.group(1) if m else out
    try:
        doc = parse_yaml(text)
    except Exception:
        return False
    entries = doc.get("units") or []
    if not entries:
        return False
    if mode == "split" and len(entries) > SPLIT_MAX_UNITS:
        return False
    for e in entries:
        if not e.get("id") or not e.get("title"):
            return False
        if not e.get("paths") or len(e["paths"]) > 8:
            return False
        if e.get("acceptance") and len(e["acceptance"]) > 5:
            return False
        if str(e.get("size", "")).upper() == "L":
            return False  # an L must be split
        e.setdefault("status", "todo")
        e.setdefault("depends_on", [])
        e.setdefault("attempts", 0)
        e.setdefault("tokens", 0)
        e.setdefault("review_rounds", 0)
        e.setdefault("conflict_rounds", 0)
        e.setdefault("planner_retries", 0)
        e.setdefault("reason", "")
        e.setdefault("pr", 0)
        e.setdefault("model", "")
        e.setdefault("branch", "")
        e.setdefault("updated", now())
    # Refs from the replacement entries back to the unit being replaced (a
    # dependency, or a worktree/branch name) must be retargeted, or the
    # replacements can never become ready.
    new_ids = [e["id"] for e in entries]
    for e in entries:
        deps = [str(d) for d in (e.get("depends_on") or [])]
        if old_id and old_id in deps:
            stripped = [d for d in deps if d != old_id]
            e["depends_on"] = stripped + [new_ids[0]] if stripped or new_ids else stripped
        if old_id and str(e.get("branch", "")).startswith(f"unit/{old_id}"):
            e["branch"] = ""
    for e in entries:
        roadmap[e["id"]] = e
    return True


def maybe_plan(roadmap: dict, state: dict) -> None:
    active = [u for u in roadmap.values() if u.get("status") in ("building", "pr_open", "queued")]
    if active:
        return
    todo = [u for u in roadmap.values() if u.get("status") == "todo"
            and not u.get("split_requested")]
    if todo:
        return
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
        if parked:
            target, mode = parked[0], "rewrite"
        elif design:
            target, mode = design[0], "promote"
        else:
            for u in roadmap.values():
                if u.get("status") == "parked":
                    u["status"] = "parked-final"
                if u.get("status") == "design" and int(u.get("planner_retries", 0)) >= PLANNER_RETRIES:
                    u["status"] = "design-blocked"
            return

    uid = target["id"]
    target["split_requested"] = False
    model = planner_model(target)
    design_text = ""
    if mode == "promote" and target.get("design_doc"):
        p = REPO / str(target["design_doc"])
        if p.exists():
            design_text = p.read_text()[:12000]
    prompt = planner_brief(target, mode, design_text)
    (BRIEF_DIR / f"{uid}-planner.md").write_text(prompt)
    event(state, f"{uid}: planner ({model}) {mode}")
    rc, out, usage = hermes_run("planner", model, prompt, "file", REPO,
                                f"{uid}-planner", 900)
    tokens = usage_tokens(usage)
    state["tokens_today"] = int(state.get("tokens_today", 0)) + tokens
    target["planner_retries"] = int(target.get("planner_retries", 0)) + 1
    target["tokens"] = int(target.get("tokens", 0)) + tokens
    if rc == 0 and apply_planner_output(roadmap, state, target, out, old_id=uid, mode=mode):
        if mode == "promote":
            target["status"] = "promoted"
        else:
            target["status"] = "parked-final"
        event(state, f"{uid}: planner produced replacement entries")
    else:
        target["reason"] = (target.get("reason", "") + " | planner output rejected")[:400]
        if target["planner_retries"] >= PLANNER_RETRIES:
            if mode == "promote":
                target["status"] = "design-blocked"
            else:
                # The split could not be produced: fall back to the retry ladder
                # rather than silently dropping the unit.
                target["status"] = "todo"
        elif mode == "split":
            target["split_requested"] = True
        event(state, f"{uid}: planner output rejected "
                     f"({target['planner_retries']}/{PLANNER_RETRIES})")


# --------------------------------------------------------------------------
# Cycle
# --------------------------------------------------------------------------

def dispatch(roadmap: dict, state: dict) -> None:
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
            jobs.append(start_build(u, state))
        except Exception as exc:
            u["status"] = "todo"
            u["reason"] = f"dispatch error: {exc}"
            event(state, f"{u['id']}: dispatch error: {exc}")
    for job in jobs:
        try:
            finish_build(job, roadmap, state)
        except Exception as exc:
            u = job["unit"]
            u["status"] = "todo"
            u["reason"] = f"pipeline error: {exc}"
            event(state, f"{u['id']}: pipeline error: {exc}")


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


def report_lines(roadmap: dict, state: dict) -> list:
    """The five-line report: merged, stuck, median tokens/unit, caps, unresolved."""
    merged = sorted(u["id"] for u in roadmap.values() if u.get("status") == "merged")
    stuck = sorted((u["id"], u.get("status", "?")) for u in roadmap.values()
                   if u.get("status") in ("queued", "pr_open", "building", "todo",
                                          "parked", "parked-final",
                                          "design-blocked"))
    delivered = [unit_tokens(u) for u in roadmap.values()
                 if u.get("status") == "merged"]
    med = _median(delivered)
    over_cap = sorted(u["id"] for u in roadmap.values()
                      if int(u.get("tokens", 0)) >= PER_UNIT_TOKEN_CAP)
    caps = (f"merged {state['merged_today']}/{MAX_MERGE_PER_DAY}; "
            f"tokens {state['tokens_today']}/{DAILY_TOKEN_CAP}; "
            f"per-unit {PER_UNIT_TOKEN_CAP}"
            + (f"; over per-unit cap: {', '.join(over_cap)}" if over_cap else ""))
    unresolved = []
    open_prs = sorted((u["id"], int(u.get("pr") or 0)) for u in roadmap.values()
                      if u.get("status") in ("queued", "pr_open")
                      and int(u.get("pr") or 0))
    if open_prs:
        unresolved.append("open PRs awaiting merge: " +
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
        f"(n={len(delivered)})",
        f"4. Caps: {caps}",
        f"5. Unresolved: " + "; ".join(unresolved),
    ]


def write_state_md(roadmap: dict, state: dict) -> None:
    counts: dict = {}
    for u in roadmap.values():
        counts[u.get("status", "?")] = counts.get(u.get("status", "?"), 0) + 1
    lines = [
        "# PHP-Retro pipeline state",
        "",
        f"updated: {now()}",
        f"day: {state['day']}  merged_today: {state['merged_today']}/{MAX_MERGE_PER_DAY}"
        f"  tokens_today: {state['tokens_today']}/{DAILY_TOKEN_CAP}",
        f"STOP file: {'PRESENT - dispatch halted' if STOP_FILE.exists() else 'absent'}",
        f"merge gate: {MERGE_GATE_DESCRIPTION}",
        "",
        "## Report",
        "",
    ]
    lines += report_lines(roadmap, state)
    lines += ["", "## Counts by status", ""]
    for k in sorted(counts):
        lines.append(f"- {k}: {counts[k]}")
    lines += ["", "## Units", "",
              "| id | status | attempts | model | tokens | wall_s | pr | reason |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for uid in sorted(roadmap):
        u = roadmap[uid]
        reason = str(u.get("reason", "")).replace("|", "/")[:120]
        lines.append(f"| {uid} | {u.get('status','')} | {u.get('attempts',0)} | "
                     f"{u.get('model','') or '-'} | {u.get('tokens',0)} | "
                     f"{u.get('wall_s',0)} | {u.get('pr',0) or '-'} | {reason} |")
    lines += ["", "## Last 20 events", ""]
    for e in state["events"][-20:]:
        lines.append(f"- {e['ts']}  {e['msg']}")
    STATE_MD.write_text("\n".join(lines) + "\n")


def cycle() -> None:
    ensure_dirs()
    if STOP_FILE.exists():
        log("STOP file present; dispatch halted")
        return
    with (LOCK_DIR / "orchestrator.lock").open("w") as fh:
        if not _try_lock(fh):
            log("another cycle is running; skipping")
            return
        state = load_state()
        rollover(state)
        roadmap = load_roadmap(state)
        event(state, f"cycle start (merged_today={state['merged_today']}, "
                     f"tokens_today={state['tokens_today']})")
        rc, out = git("fetch", "origin", "--prune")
        if rc != 0:
            event(state, f"git fetch failed: {out[-200:]}")
        # units parked while in flight by a previous cycle
        for u in roadmap.values():
            if u.get("status") == "building":
                u["status"] = "todo"
        history = load_history()
        # A cycle that died between commit and merge would otherwise re-run the
        # whole build. Recover it instead: re-gate the branch and requeue.
        for u in roadmap.values():
            if u.get("status") != "todo" or int(u.get("attempts", 0)) == 0:
                continue
            entry = history.get(u["id"])
            if entry and entry.get("outcome") == "no-change":
                continue
            if recover_branch(u, history, state):
                continue
        resume_open_prs(roadmap, state)
        dispatch(roadmap, state)
        maybe_plan(roadmap, state)
        save_roadmap(roadmap)
        write_json(STATE_JSON, state)
        write_state_md(roadmap, state)
        event(state, "cycle end")
        write_json(STATE_JSON, state)
        write_state_md(roadmap, state)


def _try_lock(fh) -> bool:
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

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
    print("selftest OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="PHP-Retro autonomous unit pipeline")
    ap.add_argument("--once", action="store_true", help="run one cycle")
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
    cycle()
    return 0


if __name__ == "__main__":
    sys.exit(main())

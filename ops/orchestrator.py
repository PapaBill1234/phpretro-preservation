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
CI_TIMEOUT = int(os.environ.get("PHPRETRO_CI_TIMEOUT", "1800"))
PER_UNIT_TOKEN_CAP = int(os.environ.get("PHPRETRO_UNIT_TOKEN_CAP", "6000000"))
DAILY_TOKEN_CAP = int(os.environ.get("PHPRETRO_DAILY_TOKEN_CAP", "60000000"))
MAX_MERGE_PER_DAY = int(os.environ.get("PHPRETRO_MAX_MERGE_PER_DAY", "12"))
MAX_ATTEMPTS = 4            # luna x2, deepseek x1, sol x1, then parked
PLANNER_RETRIES = 2
DIFF_LINE_CAP = 700

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


def dump_unit_yaml(unit: dict) -> str:
    lines = [f"  - id: {unit.get('id','')}"]
    for key in ("title", "status", "depends_on", "paths", "tests", "acceptance",
                "fixtures", "fidelity_notes", "size", "design_doc"):
        if key not in unit:
            continue
        val = unit[key]
        if isinstance(val, list):
            items = ", ".join(json.dumps(v) if isinstance(v, str) and "," in v else str(v)
                              for v in val)
            lines.append(f"    {key}: [{items}]")
        elif isinstance(val, str):
            lines.append(f'    {key}: "{val}"')
        else:
            lines.append(f"    {key}: {val}")
    return "\n".join(lines)


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


def diff_touches_sensitive(diff: str) -> bool:
    return any(f"a/{p}" in diff or f"b/{p}" in diff for p in SENSITIVE)


def commit_if_dirty(wt: Path, unit: dict) -> bool:
    status = git_out("status", "--porcelain", cwd=wt)
    if not status:
        return False
    git("add", "-A", cwd=wt)
    git("-c", "user.name=PapaBill1234",
        "-c", "user.email=PapaBill1234@users.noreply.github.com",
        "commit", "-m", f"unit({unit['id']}): builder output", cwd=wt)
    return True


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
            verdict = str(data.get("verdict", "pass")).lower()
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
        verdict = str(data.get("verdict", "pass")).lower()
        blockers = [f for f in data.get("findings", [])
                    if str(f.get("severity", "")).lower() == "blocker"]
        findings = "\n".join(f"- {f.get('file','')}:{f.get('line',0)} {f.get('issue','')}"
                             for f in blockers)
        return verdict, findings, tokens
    except Exception:
        return "pass", "", tokens


def wait_for_checks(pr: int, timeout: int = CI_TIMEOUT) -> tuple[bool, str]:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        rc, out = sh(["gh", "pr", "view", str(pr), "--repo", GH_REPO, "--json",
                      "statusCheckRollup,mergeable,mergeStateStatus"], timeout=120)
        if rc != 0:
            time.sleep(20)
            continue
        last = out
        try:
            data = json.loads(out)
        except Exception:
            time.sleep(20)
            continue
        checks = data.get("statusCheckRollup") or []
        if not checks:
            time.sleep(20)
            continue
        pending = [c for c in checks
                   if (c.get("status") or "").upper() not in ("COMPLETED",)
                   or (c.get("conclusion") or "").upper() in ("", "PENDING", "QUEUED", "IN_PROGRESS")]
        if pending:
            time.sleep(20)
            continue
        bad = [c for c in checks
               if (c.get("conclusion") or "").upper() not in ("SUCCESS", "NEUTRAL", "SKIPPED")]
        return (not bad), last
    return False, f"timed out waiting for checks\n{last}"


def merge_queue(unit: dict, wt: Path, state: dict) -> bool:
    """Locked: rebase, re-check, merge one PR at a time."""
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
        rc, out = run_check(wt)
        if rc != 0:
            unit["attempts"] = int(unit.get("attempts", 0)) + 1
            unit["reason"] = "check.sh failed after rebase"
            unit["status"] = "todo" if unit["attempts"] < MAX_ATTEMPTS else "parked"
            event(state, f"{unit['id']}: check failed after rebase -> {unit['status']}")
            return False
        rc, out = git("push", "--force-with-lease", "origin",
                      f"HEAD:refs/heads/{unit_branch(unit)}", cwd=wt, timeout=300)
        if rc != 0:
            event(state, f"{unit['id']}: rebase push failed: {out[-300:]}")
            return False
        ok, detail = wait_for_checks(pr)
        if not ok:
            event(state, f"{unit['id']}: foundation check not green: {tail(detail, 6)}")
            return False
        for attempt in range(3):
            rc, out = sh(["gh", "pr", "merge", str(pr), "--repo", GH_REPO,
                          "--merge", "--delete-branch"], timeout=300)
            if rc == 0:
                break
            if "queued" in out or "pending" in out or "in progress" in out.lower():
                # a required check re-queued between the wait and the merge
                ok, detail = wait_for_checks(pr, timeout=600)
                if not ok:
                    event(state, f"{unit['id']}: check not green before merge: "
                                 f"{tail(detail, 4)}")
                    return False
                continue
            event(state, f"{unit['id']}: gh pr merge failed: {out[-400:]}")
            return False
        else:
            event(state, f"{unit['id']}: merge gave up after 3 attempts")
            return False
        unit["status"] = "merged"
        unit["updated"] = now()
        state["merged_today"] = int(state.get("merged_today", 0)) + 1
        event(state, f"{unit['id']}: MERGED PR #{pr} (tokens {unit.get('tokens',0)})")
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
    """
    for uid in sorted(roadmap):
        u = roadmap[uid]
        if u.get("status") not in ("queued", "pr_open") or not u.get("pr"):
            continue
        if int(state.get("merged_today", 0)) >= MAX_MERGE_PER_DAY:
            event(state, f"{uid}: daily merge cap reached; PR left open")
            return
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
    try:
        proc.communicate(timeout=RUN_TIMEOUT)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        with_suppress(lambda: os.killpg(os.getpgid(proc.pid), signal.SIGKILL))
        with_suppress(lambda: proc.communicate(timeout=30))
        rc = 124
        event(state, f"{uid}: builder run killed at {RUN_TIMEOUT}s")
    with_suppress(job["logfile"].close)
    wall = int(time.time() - job["started"])
    tokens = usage_tokens(read_json(usage, {}) or {})
    add_tokens(state, unit, tokens)
    unit["wall_s"] = int(unit.get("wall_s", 0)) + wall
    unit["updated"] = now()
    log(f"{uid}: builder finished rc={rc} in {wall}s, {tokens} tokens")

    commit_if_dirty(wt, unit)
    ahead = git_out("rev-list", "--count", f"{BASE_REF}..HEAD", cwd=wt)
    if not ahead or ahead == "0":
        unit["feedback"] = "The previous attempt produced no committed change."
        unit["status"] = "todo"
        if unit["attempts"] >= MAX_ATTEMPTS or unit["tokens"] >= PER_UNIT_TOKEN_CAP:
            unit["status"] = "parked"
            unit["reason"] = "no committed change after all ladder attempts"
        event(state, f"{uid}: no change produced -> {unit['status']}")
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


def apply_planner_output(roadmap: dict, state: dict, unit: dict, out: str) -> bool:
    m = re.search(r"(units:\s*\n(?:.|\n)*)", out)
    text = m.group(1) if m else out
    try:
        doc = parse_yaml(text)
    except Exception:
        return False
    entries = doc.get("units") or []
    if not entries:
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
        roadmap[e["id"]] = e
    return True


def maybe_plan(roadmap: dict, state: dict) -> None:
    active = [u for u in roadmap.values() if u.get("status") in ("building", "pr_open", "queued")]
    if active:
        return
    todo = [u for u in roadmap.values() if u.get("status") == "todo"]
    if todo:
        return
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
    if rc == 0 and apply_planner_output(roadmap, state, target, out):
        target["status"] = "promoted" if mode == "promote" else "parked-final"
        event(state, f"{uid}: planner produced replacement entries")
    else:
        target["reason"] = (target.get("reason", "") + " | planner output rejected")[:400]
        if target["planner_retries"] >= PLANNER_RETRIES:
            target["status"] = "design-blocked" if mode == "promote" else "parked-final"
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
        "",
        "## Counts by status",
        "",
    ]
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
    assert paths_overlap(["internal/home/**"], ["internal/home/home.go"])
    assert not paths_overlap(["internal/home/**"], ["internal/account/**"])
    assert reviewer_model_for(MODEL["luna"]) == MODEL["deepseek"]
    assert reviewer_model_for(MODEL["deepseek"]) == MODEL["luna"]
    assert model_for_attempt(1) == MODEL["luna"]
    assert model_for_attempt(3) == MODEL["deepseek"]
    assert model_for_attempt(4) == MODEL["sol"]
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

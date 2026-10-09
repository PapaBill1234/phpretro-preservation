#!/usr/bin/env python3
"""Jev decision model: routing-only help for the orchestrator.

Jev (`typesafe/jev-1.13`) answers typed questions about a state object and
returns probabilities, not prose. It runs on OpenRouter's Decisions API, which
is *not* the chat-completions surface, so this module talks to the endpoint with
``urllib`` only - the Hermes chat client does not work for this model.

Design rules (all of them matter):

* **Routing only.** Jev never gates a merge. ``scripts/check.sh`` remains the
  only merge gate. This module only chooses between options the pipeline
  already allows.
* **Never blocking.** Every entry point falls back to the existing behaviour on
  a missing key, a timeout, an error, a malformed response, or a missing
  probability/confidence. Missing confidence is treated as ``0``.
* **Bounded input.** Jev's context is 32K tokens. The state is trimmed to fit;
  if it still does not fit, Jev is skipped and the rule is used.
* **No secrets in logs.** The key is read from the dedicated service environment and never
  printed or written; only the decision is logged.

State lives in ``~/phpretro-ops/state/jev.json`` (enable flags + counters) and
``~/phpretro-ops/state/jev.jsonl`` (one line per call, append-only).
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
OPS = Path(os.environ.get("PHPRETRO_OPS", HOME / "phpretro-ops"))
STATE = OPS / "state"
JEV_LOG = STATE / "jev.jsonl"
JEV_STATE = STATE / "jev.json"

ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
# Pinned on purpose: the ~typesafe/jev-latest alias would drift our thresholds.
JEV_MODEL = "typesafe/jev-1.13"
TIMEOUT = int(os.environ.get("PHPRETRO_JEV_TIMEOUT", "20"))
RETRIES = 1
MAX_INPUT_TOKENS = 32000
CTX_LIMIT = int(os.environ.get("PHPRETRO_JEV_CTX", str(MAX_INPUT_TOKENS)))

# Review cascade thresholds (item 2c).
ACCEPT_PROB = 0.9
ACCEPT_CONF = 0.9
DIFF_LINE_LIMIT = 300

# Auto-disable guard (item 4).
SKIP_WINDOW = 10          # a miss counts while within the last N skipped reviews
MISS_LIMIT = 2            # two misses inside the window disable (c)
MEDIAN_WINDOW = 10        # units per median comparison for (a)+(b)

# Paths whose diff must always get a real review (item 2c: auth, sessions,
# schema, ops/, CI, skills).
SENSITIVE_PREFIXES = (
    "internal/authflow", "internal/session", "internal/account",
    "internal/polaris", "internal/profile/settings", "migrations",
    "ops/", ".github/workflows/", "skills/", ".agents/skills/",
)

PLACES = ("a", "b", "c")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# key + state
# --------------------------------------------------------------------------

def _env_files() -> list:
    """Files searched for the key, in order. The dashboard's secrets file is
    the deployment's source of truth for this key."""
    return [
        Path(os.environ.get("PHPRETRO_JEV_ENV", "")) if os.environ.get("PHPRETRO_JEV_ENV") else None,
        HOME / "phpretro-dashboard" / "secrets" / "openrouter.env",
    ]


def _env_value(name: str) -> str:
    """Read a variable from the environment or a known env file.

    The value is returned to the caller only; it is never logged or printed.
    """
    val = os.environ.get(name, "").strip()
    if val:
        return val
    for path in _env_files():
        if not path:
            continue
        try:
            for line in path.read_text(errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == name:
                    got = v.strip().strip('"').strip("'")
                    if got:
                        return got
        except OSError:
            continue
    return ""


def api_key() -> str:
    """The OpenRouter key, or '' when none is configured. Never printed."""
    return _env_value("OPENROUTER_API_KEY")


def _default_state() -> dict:
    return {
        "enabled": {"a": False, "b": False, "c": False},
        "disabled_reason": {"a": "", "b": "", "c": ""},
        "calls": 0,
        "spend": 0.0,
        "spend_unknown": 0,
        "changed": 0,
        "skips": [],          # unit ids whose review was skipped via Jev
        "skipped_reviews": 0,
        "misses": 0,
        "miss_units": [],
        "last_miss_date": "",
        "recent_merged": [],  # [{unit, tokens}]
        "median_checked_at": 0,
        "updated": "",
    }


def load_state() -> dict:
    try:
        raw = json.loads(JEV_STATE.read_text())
        if not isinstance(raw, dict):
            raise ValueError
    except (OSError, ValueError, json.JSONDecodeError):
        raw = {}
    st = _default_state()
    for k, v in raw.items():
        if k == "enabled" and isinstance(v, dict):
            st["enabled"].update({p: bool(v.get(p, False)) if p != "c" else False for p in PLACES})
        elif k == "disabled_reason" and isinstance(v, dict):
            st["disabled_reason"].update({p: str(v.get(p, "")) for p in PLACES})
        else:
            st[k] = v
    st["disabled_reason"]["c"] = "Review skipping disabled by runtime policy"
    return st


def save_state(st: dict) -> None:
    st["updated"] = now()
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = JEV_STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(st, indent=1, sort_keys=True))
    tmp.replace(JEV_STATE)


def enabled(place: str) -> bool:
    """Is this call site on? Off when auto-disabled or when there is no key.

    The key check makes an unconfigured install fall back silently instead of
    paying for a doomed request on every unit.
    """
    if place not in PLACES:
        return False
    return bool(load_state()["enabled"].get(place)) and bool(api_key())


def disable(place: str, reason: str) -> None:
    st = load_state()
    if st["enabled"].get(place):
        st["enabled"][place] = False
        st["disabled_reason"][place] = reason[:300]
        save_state(st)


# --------------------------------------------------------------------------
# input sizing
# --------------------------------------------------------------------------

def estimate_tokens(obj) -> int:
    """Rough token estimate: ~4 chars per token over the JSON text."""
    try:
        text = obj if isinstance(obj, str) else json.dumps(obj, default=str)
    except (TypeError, ValueError):
        text = str(obj)
    return max(1, len(text) // 4)


def trim_state(state: dict, limit: "int | None" = None) -> tuple[dict, int]:
    """Drop the largest string fields until the state fits.

    Returns ``(state, dropped_count)``. Shrinking is by design shallow: the
    decision points get small states, and a diff only enters usage (c) when it
    is already under 300 lines.
    """
    limit = limit or CTX_LIMIT
    if not isinstance(state, dict):
        return state, 0
    out = dict(state)
    dropped = 0
    # Largest strings first: those are what blow the budget.
    while estimate_tokens(out) > limit:
        fields = [(len(v), k) for k, v in out.items()
                  if isinstance(v, str) and len(v) > 200]
        if not fields:
            break
        fields.sort(reverse=True)
        _, key = fields[0]
        keep = max(200, int(len(out[key]) / 2))
        out[key] = out[key][:keep] + f"\n[... {len(out[key]) - keep} chars trimmed ...]"
        dropped += 1
    return out, dropped


def fits(obj, limit: "int | None" = None) -> bool:
    return estimate_tokens(obj) <= (limit or CTX_LIMIT)


# --------------------------------------------------------------------------
# the API call
# --------------------------------------------------------------------------

def _post(payload: dict, key: str) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "HTTP-Referer": "https://localhost/phpretro-pipeline",
                 "X-Title": "phpretro-pipeline"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read().decode("utf-8", "replace")
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("answers"), dict):
        raise ValueError("malformed Decisions response")
    return data


CONTROL_BEFORE = None
CONTROL_AFTER = None


def call(state, questions: dict, *, place: str = "a", unit: str = "",
         retries: int = RETRIES) -> dict | None:
    """One Decisions request. Returns ``{answers, usage, model}`` or None.

    None means "no usable Jev answer" for any reason: no key, too large, error,
    timeout, malformed body. Callers must then use the existing rule.
    """
    key = api_key()
    if not key:
        return None
    trimmed, _ = trim_state(state if isinstance(state, dict) else {"state": state})
    payload = {"model": JEV_MODEL, "state": trimmed, "questions": questions}
    if not fits(payload):
        log_fallback(place, unit, "state exceeds the 32K-token budget after trimming")
        return None
    attempt = 0
    started = time.time()
    while attempt <= max(0, retries):
        attempt += 1
        rid = CONTROL_BEFORE(unit) if CONTROL_BEFORE else "fixture"
        if rid is None:
            return None
        recorded = False
        try:
            resp = _post(payload, key)
            # Validate at the boundary too, not only inside _post: a transport
            # that returns a 200 with an unusable body must fall back to the
            # rule rather than make a call site raise on a missing key.
            if not isinstance(resp, dict) or not isinstance(resp.get("answers"), dict):
                raise ValueError("malformed Decisions response")
            if CONTROL_AFTER:
                CONTROL_AFTER(rid, unit, resp.get("usage") or {}, False)
            recorded = True
            return resp
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                ValueError, json.JSONDecodeError, OSError) as exc:
            if CONTROL_AFTER and not recorded:
                CONTROL_AFTER(rid, unit, {}, True)
            if attempt > retries:
                log_fallback(place, unit, f"{type(exc).__name__}: {str(exc)[:160]}",
                             latency_ms=int((time.time() - started) * 1000))
                return None
            time.sleep(0.5)
    return None


def log_fallback(place: str, unit: str, reason: str, latency_ms: int = 0) -> None:
    log_call({"place": place, "unit": unit, "question": "", "chosen": "",
              "probability": None, "confidence": None, "cost": None,
              "fell_back": True, "reason": reason, "latency_ms": latency_ms})


def log_call(rec: dict) -> None:
    """Append one call to jev.jsonl (item 3). Never raises, never logs a key."""
    STATE.mkdir(parents=True, exist_ok=True)
    rec = {"ts": now(), **rec}
    try:
        with JEV_LOG.open("a") as fh:
            fh.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
    except OSError:
        pass


def _choice_answer(answers: dict, qid: str) -> tuple[str, float, float]:
    """(option, probability of that option, confidence) from a choice answer.

    A missing probability or confidence is treated as 0, per the contract.
    """
    a = answers.get(qid)
    if not isinstance(a, dict) or a.get("type") != "choice":
        return "", 0.0, 0.0
    option = str(a.get("choice") or "")
    probs = a.get("probabilities") or {}
    prob = probs.get(option) if isinstance(probs, dict) else None
    try:
        prob = float(prob) if prob is not None else 0.0
    except (TypeError, ValueError):
        prob = 0.0
    try:
        conf = float(a.get("confidence") or 0.0)
    except (TypeError, ValueError):
        conf = 0.0
    return option, prob, conf


def _cost(usage: dict):
    try:
        c = usage.get("cost")
        return float(c) if c is not None else None
    except (TypeError, ValueError, AttributeError):
        return None


def _record(place: str, unit: str, question: str, chosen: str, prob, conf,
            usage: dict, latency_ms: int, changed: bool,
            extra: "dict | None" = None) -> None:
    st = load_state()
    st["calls"] = int(st.get("calls", 0)) + 1
    c = _cost(usage or {})
    if c is None:
        st["spend_unknown"] = int(st.get("spend_unknown", 0)) + 1
    else:
        st["spend"] = round(float(st.get("spend", 0.0)) + c, 8)
    if changed:
        st["changed"] = int(st.get("changed", 0)) + 1
    save_state(st)
    log_call({"place": place, "unit": unit, "question": question, "chosen": chosen,
              "probability": prob, "confidence": conf, "cost": c,
              "latency_ms": latency_ms, "changed": changed,
              "fell_back": False, **(extra or {})})


# --------------------------------------------------------------------------
# (a) pre-dispatch size check
# --------------------------------------------------------------------------

SIZE_OPTIONS = ("run_as_is", "split", "shrink")


def size_check(unit: dict) -> dict:
    """Route a unit before it is built: run_as_is | split | shrink.

    A unit that already timed out once is never run as is - that rule holds
    whether or not Jev answers. Returns ``{action, source, ...}``.
    """
    timed_out = int(unit.get("timeouts", 0)) > 0 or unit.get("last_outcome") == "timeout"
    rule_action = "split" if timed_out else "run_as_is"
    result = {"action": rule_action, "source": "rule", "probability": None,
              "confidence": None}
    # A prior timeout is a hard rule; do not spend a call re-deciding it.
    if timed_out or not enabled("a"):
        return result
    state = {
        "unit": unit.get("id", ""),
        "path_count": len(unit.get("paths") or []),
        "acceptance_count": len(unit.get("acceptance") or []),
        "size": unit.get("size", ""),
        "attempts": int(unit.get("attempts", 0)),
        "timeouts": int(unit.get("timeouts", 0)),
        "tokens_so_far": int(unit.get("tokens", 0)),
        "title": str(unit.get("title", ""))[:300],
    }
    questions = {"action": {
        "type": "choice",
        "instructions": ("Choose how to run this build unit. run_as_is: it is "
                         "small and clear enough to build in one attempt. split: "
                         "it covers too many paths or goals and should become "
                         "several smaller units. shrink: it is one goal but too "
                         "wide, so narrow it before building."),
        "criteria": {
            "run_as_is": "The scope is small and well-specified for one attempt.",
            "split": "It bundles several independent goals or many paths.",
            "shrink": "One goal, but the surface is too wide for one attempt.",
        }}}
    started = time.time()
    resp = call(state, questions, place="a", unit=unit.get("id", ""))
    latency = int((time.time() - started) * 1000)
    if not resp:
        return result
    action, prob, conf = _choice_answer(resp["answers"], "action")
    if action not in SIZE_OPTIONS or prob < 0.5:
        action = rule_action
    changed = action != rule_action
    _record("a", unit.get("id", ""), "pre-dispatch size", action, prob, conf,
            resp.get("usage") or {}, latency, changed,
            {"rule": rule_action, "size": unit.get("size", "")})
    return {"action": action, "source": "jev", "probability": prob,
            "confidence": conf}


# --------------------------------------------------------------------------
# (b) failure triage
# --------------------------------------------------------------------------

TRIAGE_OPTIONS = ("retry_same", "shrink_unit", "split_unit", "escalate_model", "park")


def allowed_triage(attempt: int, max_attempts: int, at_last_rung: bool) -> list:
    """Which options the remaining ladder permits (item 2b)."""
    if attempt >= max_attempts:
        return ["park"]
    opts = ["retry_same", "shrink_unit", "split_unit", "park"]
    if not at_last_rung:
        opts.append("escalate_model")
    return opts


def triage(unit: dict, output: str, attempt: int, max_attempts: int,
           at_last_rung: bool) -> dict:
    """Decide what to do after a failed attempt. Never blocks.

    Falls back to ``retry_same`` unless the ladder only allows ``park``.
    """
    allowed = allowed_triage(attempt, max_attempts, at_last_rung)
    rule_action = "park" if allowed == ["park"] else "retry_same"
    result = {"action": rule_action, "source": "rule", "probability": None,
              "confidence": None}
    if not enabled("b") or len(allowed) < 2:
        return result if allowed == ["park"] else _triage_local(unit, output, result)
    state = {
        "unit": unit.get("id", ""),
        "attempt": attempt,
        "max_attempts": max_attempts,
        "at_last_rung": at_last_rung,
        "allowed_options": allowed,
        "output_tail": str(output or "")[-4000:],
        "reason": str(unit.get("reason", ""))[:400],
    }
    questions = {"action": {
        "type": "choice",
        "instructions": ("A build attempt failed. Choose the best next move from "
                         "the allowed options only. retry_same: the failure looks "
                         "transient. shrink_unit: the same unit, narrower. "
                         "split_unit: break it into smaller units. escalate_model: "
                         "try a stronger model. park: stop working on it."),
        "criteria": {o: _triage_criterion(o) for o in allowed}}}
    started = time.time()
    resp = call(state, questions, place="b", unit=unit.get("id", ""))
    latency = int((time.time() - started) * 1000)
    if not resp:
        return _triage_local(unit, output, result)
    raw, prob, conf = _choice_answer(resp["answers"], "action")
    # Every call is logged (item 3), even when the answer is rejected for being
    # outside the ladder or below the probability bar - that is what makes the
    # "changed the decision" count trustworthy.
    action = raw if (raw in allowed and prob >= 0.5) else rule_action
    _record("b", unit.get("id", ""), "failure triage", action, prob, conf,
            resp.get("usage") or {}, latency, action != rule_action,
            {"rule": rule_action, "allowed": allowed, "raw": raw})
    if action == rule_action:
        return _triage_local(unit, output, result)
    return {"action": action, "source": "jev", "probability": prob,
            "confidence": conf}


def _triage_criterion(opt: str) -> str:
    return {
        "retry_same": "The failure looks transient or environmental, not structural.",
        "shrink_unit": "The same goal, but the unit's surface must be narrowed.",
        "split_unit": "The unit covers more than one goal and should be divided.",
        "escalate_model": "The task is clear but beyond the current model's reach.",
        "park": "Repeated real failures; stop rather than burn more budget.",
    }.get(opt, opt)


def _triage_local(unit: dict, output: str, result: dict) -> dict:
    """The existing rule, used when Jev is off or unusable (item 1)."""
    return result


# --------------------------------------------------------------------------
# (c) review cascade
# --------------------------------------------------------------------------

def review_gate(unit: dict, diff: str, tests_pass: bool) -> dict:
    """Decide whether the deepseek review can be skipped (item 2c).

    Independent review is mandatory. This compatibility function reports
    deterministic reasons and never calls Jev or returns a waiver.
    """
    decision = {"skip": False, "source": "rule", "probability": None,
                "confidence": None, "reason": ""}
    lines = _changed_lines(diff)
    if lines == 0:
        decision["reason"] = "empty diff"
        return decision
    if _touches_sensitive(diff):
        decision["reason"] = "sensitive path"
        return decision
    if not tests_pass:
        decision["reason"] = "tests not passing"
        return decision
    if lines >= DIFF_LINE_LIMIT:
        decision["reason"] = f"diff too large ({lines} lines)"
        return decision
    decision["reason"] = "independent review mandatory; site c has no waiver authority"
    return decision


def _changed_lines(diff: str) -> int:
    n = 0
    for line in (diff or "").splitlines():
        if (line.startswith("+") and not line.startswith("+++")) or \
           (line.startswith("-") and not line.startswith("---")):
            n += 1
    return n


def _diff_files(diff: str) -> list:
    return re.findall(r"^diff --git a/(\S+)", diff or "", re.M)[:40]


def _touches_sensitive(diff: str) -> bool:
    for f in _diff_files(diff):
        if any(f == p.rstrip("/") or f.startswith(p) for p in SENSITIVE_PREFIXES):
            return True
    return False


# --------------------------------------------------------------------------
# auto-disable guard (item 4)
# --------------------------------------------------------------------------

def note_skip(unit_id: str, lines: int, tokens: int) -> None:
    st = load_state()
    st["skips"] = (st.get("skips", []) + [{
        "unit": unit_id, "ts": now(), "lines": int(lines),
        "tokens": int(tokens), "miss": False}])[-200:]
    st["skipped_reviews"] = int(st.get("skipped_reviews", 0)) + 1
    save_state(st)


def record_merged(unit_id: str, tokens: int) -> None:
    """Track merged-unit tokens; compare medians every MEDIAN_WINDOW units."""
    st = load_state()
    st["recent_merged"] = (st.get("recent_merged", []) + [{
        "unit": unit_id, "tokens": int(tokens), "ts": now()}])[-100:]
    save_state(st)
    _maybe_disable_ab(st)


def _median(vals: list) -> float:
    vals = sorted(int(v) for v in vals if v)
    if not vals:
        return 0.0
    mid = len(vals) // 2
    return float(vals[mid]) if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2


def _maybe_disable_ab(st: dict) -> None:
    """If the newest 10 merged units are not cheaper than the previous 10,
    turn (a) and (b) off (item 4)."""
    if not (st["enabled"].get("a") or st["enabled"].get("b")):
        return
    merged = st.get("recent_merged", [])
    if len(merged) < 2 * MEDIAN_WINDOW:
        return
    stamp = len(merged)
    if int(st.get("median_checked_at", 0)) == stamp:
        return
    new = [m["tokens"] for m in merged[-MEDIAN_WINDOW:]]
    old = [m["tokens"] for m in merged[-2 * MEDIAN_WINDOW:-MEDIAN_WINDOW]]
    st["median_checked_at"] = stamp
    if _median(new) >= _median(old) > 0:
        st["enabled"]["a"] = False
        st["enabled"]["b"] = False
        st["disabled_reason"]["a"] = (f"median tokens/merged unit not lower after "
                                      f"{MEDIAN_WINDOW} units "
                                      f"({_median(new):.0f} >= {_median(old):.0f})")
        st["disabled_reason"]["b"] = st["disabled_reason"]["a"]
        save_state(st)
        log_call({"place": "a+b", "unit": "", "question": "auto-disable",
                  "chosen": "disabled", "probability": None, "confidence": None,
                  "cost": None, "reason": st["disabled_reason"]["a"]})
    else:
        save_state(st)


def note_miss(unit_id: str, reason: str) -> None:
    """A Jev-skipped unit later failed nightly or needed a fix unit."""
    st = load_state()
    # One triggering incident can produce both a nightly failure and a fix unit;
    # count at most one miss per UTC day so a single bad night cannot on its own
    # trip the two-miss disable. (c) is disabled by *independent* misses.
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if st.get("last_miss_date") == today:
        log_call({"place": "c", "unit": unit_id, "question": "miss-suppressed",
                  "chosen": "suppressed", "probability": None, "confidence": None,
                  "cost": None, "reason": f"already counted a miss today ({reason})"})
        return
    for s in reversed(st.get("skips", [])):
        if s.get("unit") == unit_id and not s.get("miss"):
            s["miss"] = True
            break
    st["misses"] = int(st.get("misses", 0)) + 1
    st["miss_units"] = (st.get("miss_units", []) + [unit_id])[-50:]
    st["last_miss_date"] = today
    save_state(st)
    _maybe_disable_c(st, reason)


def note_miss_recent(reason: str) -> list:
    """Attribute a nightly failure / fix unit to the most recent Jev skip.

    Attribution is deliberately conservative: one triggering event counts one
    miss, against the newest unmarked skip in the last 24h (the most likely
    culprit). Marking every recent skip would disable (c) on a single bad night.
    """
    st = load_state()
    cutoff = time.time() - 86400
    newest = None
    for s in st.get("skips", []):
        if s.get("miss"):
            continue
        try:
            t = datetime.strptime(s["ts"], "%Y-%m-%dT%H:%M:%SZ") \
                .replace(tzinfo=timezone.utc).timestamp()
        except (KeyError, ValueError):
            continue
        if t >= cutoff and (newest is None or t >= newest[0]):
            newest = (t, s["unit"])
    if newest is None:
        return []
    note_miss(newest[1], reason)
    return [newest[1]]


def _maybe_disable_c(st: dict, reason: str) -> None:
    """Two misses within the last SKIP_WINDOW skipped reviews disable (c)."""
    if not st["enabled"].get("c"):
        return
    recent = st.get("skips", [])[-SKIP_WINDOW:]
    misses = sum(1 for s in recent if s.get("miss"))
    if misses >= MISS_LIMIT:
        st["enabled"]["c"] = False
        st["disabled_reason"]["c"] = (f"{misses} misses in the last "
                                      f"{len(recent)} skipped reviews ({reason})")
        save_state(st)
        log_call({"place": "c", "unit": "", "question": "auto-disable",
                  "chosen": "disabled", "probability": None, "confidence": None,
                  "cost": None, "reason": st["disabled_reason"]["c"]})
    else:
        save_state(st)


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

def summary() -> dict:
    st = load_state()
    try:
        calls = sum(1 for _ in JEV_LOG.read_text().splitlines()) if JEV_LOG.exists() else 0
    except OSError:
        calls = 0
    return {
        "enabled": st["enabled"],
        "disabled_reason": st["disabled_reason"],
        "calls": calls,
        "spend": round(float(st.get("spend", 0.0)), 6),
        "spend_unknown": int(st.get("spend_unknown", 0)),
        "changed": int(st.get("changed", 0)),
        "skipped_reviews": int(st.get("skipped_reviews", 0)),
        "misses": int(st.get("misses", 0)),
        "miss_units": st.get("miss_units", []),
        "key_present": None,  # Status must never open credential files.
    }


def report_lines() -> list:
    """STATE.md lines for the Jev section (item 3 + item 4)."""
    s = summary()
    if s["key_present"] is False and all(s["enabled"].values()) and not s["calls"]:
        return ["- not active: no OPENROUTER_API_KEY configured (see below)",
                "- calls: 0; estimated spend: $0.00; decisions changed: 0",
                "- (a) size check, (b) triage, (c) review skip all use the "
                "existing rule until a key is added"]
    lines = [
        f"- (a) size check: {'on' if s['enabled']['a'] else 'OFF'}"
        + (f" ({s['disabled_reason']['a']})" if s['disabled_reason']['a'] else ""),
        f"- (b) failure triage: {'on' if s['enabled']['b'] else 'OFF'}"
        + (f" ({s['disabled_reason']['b']})" if s['disabled_reason']['b'] else ""),
        f"- (c) review skip: {'on' if s['enabled']['c'] else 'OFF'}"
        + (f" ({s['disabled_reason']['c']})" if s['disabled_reason']['c'] else ""),
        f"- calls: {s['calls']}; estimated spend: ${s['spend']:.6f}"
        + (f" (+{s['spend_unknown']} calls with no cost reported)"
           if s['spend_unknown'] else ""),
        f"- decisions changed by Jev: {s['changed']} of {s['calls']}",
        f"- skipped reviews: {s['skipped_reviews']}; misses: {s['misses']}"
        + (f" ({', '.join(s['miss_units'][-5:])})" if s['miss_units'] else ""),
    ]
    if s["key_present"] is False:
        lines.append("- no OPENROUTER_API_KEY: Jev is skipping and the rules are "
                     "in use (setup steps below)")
    if s["key_present"] is None:
        lines.append("- credential availability: not probed by status reporting")
    return lines


SETUP_STEPS = (
    "Jev setup (one key, no TypeSafe account): 1) create a key at "
    "https://openrouter.ai/keys; 2) add `OPENROUTER_API_KEY=<key>` to "
    "~/.hermes/.env (the line exists, commented, at the OpenRouter section); "
    "3) no restart needed - ops/jev.py reads the file per call. Billing is on "
    "input tokens only, output is free; each call logs its cost to jev.jsonl."
)


# --------------------------------------------------------------------------
# selftest
# --------------------------------------------------------------------------

def selftest() -> int:
    """Exercise the pure logic with the network stubbed out."""
    import tempfile
    import shutil
    global JEV_LOG, JEV_STATE
    keep = (JEV_LOG, JEV_STATE)
    tmp = Path(tempfile.mkdtemp(prefix="jev-selftest-"))
    JEV_LOG, JEV_STATE = tmp / "jev.jsonl", tmp / "jev.json"
    try:
        # 1. a missing answer field means 0, not an error
        opt, p, c = _choice_answer({"q": {"type": "choice", "choice": "yes"}}, "q")
        assert (opt, p, c) == ("yes", 0.0, 0.0), (opt, p, c)
        opt, p, c = _choice_answer(
            {"q": {"type": "choice", "choice": "yes",
                   "probabilities": {"yes": 0.95}, "confidence": 0.97}}, "q")
        assert (opt, p, c) == ("yes", 0.95, 0.97), (opt, p, c)
        assert _choice_answer({}, "q") == ("", 0.0, 0.0)
        assert _choice_answer({"q": {"type": "noul", "noul": 0.9}}, "q") == ("", 0.0, 0.0)

        # 2. sizing: a 400K-char state is trimmed until it fits
        big = {"diff": "x" * 400000}
        assert not fits(big), "big state must not fit"
        trimmed, dropped = trim_state(big)
        assert dropped >= 1 and fits(trimmed), (dropped, estimate_tokens(trimmed))

        # 3. triage options respect the ladder (item 2b)
        assert allowed_triage(4, 4, True) == ["park"]
        assert "escalate_model" not in allowed_triage(4, 4, True)
        assert allowed_triage(1, 4, False) == ["retry_same", "shrink_unit",
                                               "split_unit", "park", "escalate_model"]
        # attempt 3 is deepseek; sol is still ahead, so escalation is allowed
        assert "escalate_model" in allowed_triage(3, 4, False)
        # once the last rung is in use, escalation is no longer an option
        assert "escalate_model" not in allowed_triage(3, 4, True)

        # 4. sensitive paths block a skip (item 2c)
        assert _touches_sensitive("diff --git a/ops/x.py b/ops/x.py\n+ x\n")
        assert _touches_sensitive("diff --git a/internal/authflow/y.go b/internal/authflow/y.go\n+ y\n")
        assert not _touches_sensitive("diff --git a/internal/api/x.go b/internal/api/x.go\n+ x\n")
        assert _changed_lines("diff --git a/f b/f\n--- a/f\n+++ b/f\n+a\n+b\n-c\n") == 3

        # 5. no key -> everything falls back and every place reports off
        assert not enabled("a") or api_key() != "", "enabled must imply a key"
        # with the key present, a normally-answered question changes nothing when
        # Jev is unreachable: call() returns None and size_check uses the rule.
        real_call = call
        try:
            globals()["call"] = lambda *a, **k: None
            r = size_check({"id": "U1", "paths": ["a", "b"], "size": "S"})
            assert r["action"] == "run_as_is" and r["source"] == "rule", r
            r = size_check({"id": "U2", "paths": ["a"], "size": "S", "timeouts": 1})
            assert r["action"] == "split" and r["source"] == "rule", r
            r = triage({"id": "U3"}, "boom", 2, 4, False)
            assert r["action"] == "retry_same" and r["source"] == "rule", r
            r = review_gate({"id": "U4"}, "diff --git a/ops/x b/ops/x\n+ x\n", True)
            assert r["skip"] is False, r
            r = review_gate({"id": "U5"}, "diff --git a/a b/a\n+ x\n", False)
            assert r["skip"] is False and r["reason"] == "tests not passing", r
        finally:
            globals()["call"] = real_call

        # 6. the (c) guard: 2 misses in the last 10 skips disables (c)
        st = _default_state()
        save_state(st)
        st = load_state()
        st["skips"] = [{"unit": f"U{i}", "ts": now(), "miss": i < 2} for i in range(4)]
        save_state(st)
        _maybe_disable_c(load_state(), "test")
        got = load_state()
        assert got["enabled"]["c"] is False, got["enabled"]
        assert "misses in the last" in got["disabled_reason"]["c"], got["disabled_reason"]

        # 7. the (a)+(b) median guard: not lower -> disabled
        st = _default_state()
        st["recent_merged"] = (
            [{"unit": f"o{i}", "tokens": 100, "ts": now()} for i in range(10)] +
            [{"unit": f"n{i}", "tokens": 200, "ts": now()} for i in range(10)])
        save_state(st)
        _maybe_disable_ab(load_state())
        got = load_state()
        assert got["enabled"]["a"] is False and got["enabled"]["b"] is False, got["enabled"]
        # lower -> stays on
        st = _default_state()
        st["recent_merged"] = (
            [{"unit": f"o{i}", "tokens": 300, "ts": now()} for i in range(10)] +
            [{"unit": f"n{i}", "tokens": 100, "ts": now()} for i in range(10)])
        save_state(st)
        _maybe_disable_ab(load_state())
        assert load_state()["enabled"]["a"] is True

        # 8. the log never carries a key
        log_call({"place": "a", "unit": "U", "chosen": "run_as_is", "cost": 0.0001})
        assert "OPENROUTER" not in JEV_LOG.read_text()
        assert "Bearer" not in JEV_LOG.read_text()
    finally:
        JEV_LOG, JEV_STATE = keep
        shutil.rmtree(tmp, ignore_errors=True)
    print("jev selftest OK")
    return 0


def probe() -> int:
    """One real Decisions call for setup verification. Prints no key."""
    key = api_key()
    if not key:
        print("no OpenRouter key found; add OPENROUTER_API_KEY to "
              "~/.hermes/.env or ~/phpretro-dashboard/secrets/openrouter.env")
        return 2
    print(f"key present: yes ({len(key)} chars, not printed)")
    q = {"action": {"type": "choice",
                    "instructions": "Choose how to run this build unit.",
                    "criteria": {"run_as_is": "small and clear for one attempt",
                                 "split": "it bundles several goals",
                                 "shrink": "one goal but too wide"}}}
    state = {"unit": "PROBE", "path_count": 2, "acceptance_count": 3,
             "size": "M", "attempts": 0, "timeouts": 0}
    resp = call(state, q, place="probe", unit="PROBE")
    if not resp:
        print("probe FAILED: no usable answer (see jev.jsonl for the reason)")
        return 1
    opt, prob, conf = _choice_answer(resp["answers"], "action")
    usage = resp.get("usage") or {}
    print(f"answer: {opt} (p={prob}, confidence={conf})")
    print(f"usage: {json.dumps(usage)}")
    print(f"model: {resp.get('model')} | provider: {resp.get('provider')}")
    print("probe OK")
    return 0


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Jev decision model helper")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--setup-steps", action="store_true")
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.probe:
        return probe()
    if args.setup_steps:
        print(SETUP_STEPS)
        return 0
    if args.summary:
        print(json.dumps(summary(), indent=1, sort_keys=True))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

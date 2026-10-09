#!/usr/bin/env python3
"""Pipeline telemetry: append-only run and event logs, prices, nightly results.

Everything lives outside the repository, under ``~/phpretro-ops/state``:

* ``runs.jsonl``     one JSON line per model call or agent run
* ``events.jsonl``   one JSON line per pipeline state change
* ``prices.yaml``    per-model prices as shown by the A6API gateway

``nightly.json`` and ``nightly-history.jsonl`` also live in that directory but
are written by ``ops/nightly.py``; STATE.md and the alerts read them directly.

Rules this module enforces:

* append-only; a log is never rewritten, only rotated monthly
  (``runs-YYYY-MM.jsonl``) so a month of history is preserved;
* an unknown value is recorded as ``null``, never 0, together with the
  pessimistic estimate the pipeline already uses;
* no API key, token, password or prompt text is ever written. The scrubber
  drops credential-looking fields and the callers never pass a prompt.

Stdlib only. ``ops/telemetry.py --selftest`` exercises the parsers and the
rotation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
OPS = Path(os.environ.get("PHPRETRO_OPS", HOME / "phpretro-ops"))
STATE = OPS / "state"

RUNS = STATE / "runs.jsonl"
EVENTS = STATE / "events.jsonl"
PRICES = STATE / "prices.yaml"

PROVIDER = os.environ.get("PHPRETRO_PROVIDER", "custom:a6api")
# The pipeline's pessimistic fallback for a run whose real spend is unknown.
PESSIMISTIC_TOKENS = int(os.environ.get("PHPRETRO_TIMEOUT_FALLBACK_TOKENS", "1000000"))

ROLES = ("builder", "reviewer", "planner", "audit", "jev", "other")
OUTCOMES = ("merged", "gate_failed", "timeout", "no_change", "review_fix",
            "provider_error", "interrupted", "other")
EVENT_KINDS = ("dispatched", "built", "gate_pass", "gate_fail", "pr_opened",
               "review_verdict", "merged", "parked", "split", "escalated",
               "timeout", "provider_error", "guard_disabled")

# Prices as shown by the A6API gateway. The unit is not yet calibrated, so the
# note in prices.yaml says so; cost_estimate is therefore an estimate only.
DEFAULT_PRICES = {
    "gpt-6-luna": {"input": 0.0180, "output": 0.0900},
    "deepseek-v4.1-flash": {"input": 0.0516, "output": 0.2064},
    # Not confirmed on the gateway yet; a null price yields a null estimate.
    "gpt-6.1-sol": {"input": None, "output": None},
}
PRICE_NOTE = ("price unit uncalibrated: the A6API dashboard's balance box is the "
              "authority; these numbers are per-million estimates until the unit "
              "is confirmed. A null price yields a null cost_estimate, never 0. "
              "Checked 2026-10-06: the gateway's /api/pricing lists "
              "gpt-6-luna, gpt-6.1-sol and deepseek-v4.1-flash all at "
              "model_ratio 0.5 / completion_ratio 1, i.e. a ratio system rather "
              "than per-model prices, so no sol-specific number could be "
              "confirmed and it stays null.")

_CRED = re.compile(r"(api[_-]?key|secret|password|passwd|authorization|cookie|"
                   r"bearer|credential|session[_-]?token|access[_-]?token)", re.I)
# Token counts are the point of this log and must survive the scrubber.
_TOKENISH = re.compile(r"(tokens?|calls?|cost|usd|price|count)", re.I)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _month_of(ts: str) -> str:
    """``YYYY-MM`` for an ISO ts, or '' when it cannot be read."""
    return (ts or "")[:7]


# --------------------------------------------------------------------------
# scrubbing
# --------------------------------------------------------------------------

def scrub(obj):
    """Recursively drop credential-looking fields; keep token/cost counters.

    A field is removed when its name looks like a credential and it does not
    look like a token/cost counter. Prompt text is never passed to this module,
    and any key named ``prompt``/``messages`` is removed as a belt and braces.
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            kl = str(k)
            if kl.lower() in ("prompt", "prompts", "messages", "content", "brief"):
                continue
            if _CRED.search(kl) and not _TOKENISH.search(kl):
                continue
            out[kl] = scrub(v)
        return out
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    return obj


# --------------------------------------------------------------------------
# append-only writes with monthly rotation
# --------------------------------------------------------------------------

def _rotate(path: Path) -> None:
    """Rotate ``path`` into ``<stem>-YYYY-MM<suffix>`` when it is a month old.

    Append-only in spirit: the existing lines are never edited or dropped, only
    moved aside whole. Uses the file's mtime month, which is when its last line
    was written.
    """
    if not path.exists():
        return
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        return
    this_month = datetime.now(timezone.utc).strftime("%Y-%m")
    if mtime.strftime("%Y-%m") == this_month:
        return
    rotated = path.with_name(f"{path.stem}-{mtime.strftime('%Y-%m')}{path.suffix}")
    n = 1
    while rotated.exists():
        rotated = path.with_name(
            f"{path.stem}-{mtime.strftime('%Y-%m')}-{n}{path.suffix}")
        n += 1
    try:
        shutil.move(str(path), str(rotated))
    except OSError:
        pass


def append(path: Path, record: dict) -> None:
    """Append one scrubbed JSON line, rotating first if the month changed."""
    STATE.mkdir(parents=True, exist_ok=True)
    _rotate(path)
    line = json.dumps(scrub(record), sort_keys=True, default=str)
    with path.open("a") as fh:
        fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def log_run(record: dict) -> None:
    append(RUNS, record)


def log_event(kind: str, unit: str, reason: str = "", **extra) -> None:
    rec = {"ts": now(), "unit": unit or "", "kind": kind, "reason": (reason or "")[:300]}
    rec.update(extra)
    append(EVENTS, rec)


# --------------------------------------------------------------------------
# run records
# --------------------------------------------------------------------------

def _int_or_none(v):
    if isinstance(v, bool):
        return None
    try:
        n = int(v)
        if isinstance(v, float) and v != n:
            return None
        if n < 0:
            return None
        return n
    except (TypeError, ValueError, OverflowError):
        return None


def _finite_nonnegative(v):
    if isinstance(v, bool):
        return None
    try:
        n = float(v)
        if n < 0 or not __import__("math").isfinite(n):
            return None
        return n
    except (TypeError, ValueError, OverflowError):
        return None


def parse_usage(usage: dict) -> dict:
    """Normalize a ``--usage-file`` report into token fields.

    Unknown values become ``None``; the caller adds the pessimistic estimate.
    ``cached_tokens`` is the cache-read count (what the provider bills at the
    cached rate).
    """
    u = usage or {}
    aux = u.get("total_including_auxiliary") or {}
    aux = aux if isinstance(aux, dict) else {}
    cost = aux.get("estimated_cost_usd")
    if cost is None:
        cost = u.get("estimated_cost_usd")
    cost = _finite_nonnegative(cost) if cost is not None else None
    # The provider reports 0.0 with cost_status "unknown"; that is not a real
    # zero, so keep it null and let the caller fall back to the price table.
    status = str(u.get("cost_status") or "").lower()
    if cost == 0.0 and status in ("unknown", "none", ""):
        cost = None
    return {
        "input_tokens": _int_or_none(u.get("input_tokens", u.get("prompt_tokens"))),
        "output_tokens": _int_or_none(u.get("output_tokens", u.get("completion_tokens"))),
        "cached_tokens": _int_or_none(u.get("cache_read_tokens")),
        "cache_write_tokens": _int_or_none(u.get("cache_write_tokens")),
        "reasoning_tokens": _int_or_none(u.get("reasoning_tokens")),
        "total_tokens": _int_or_none(u.get("total_tokens")),
        "total_including_auxiliary": _int_or_none(aux.get("total_tokens")),
        "api_calls": _int_or_none(u.get("api_calls")),
        "provider_cost_estimate": cost,
        "cost_status": u.get("cost_status"),
        "model": u.get("model"),
        "provider": u.get("provider"),
        "session_id": u.get("session_id"),
        "accounting_source": u.get("accounting_source"),
        "accounting_metadata": u.get("accounting_metadata"),
        "usage_complete": u.get("usage_complete"),
        "failed": bool(u.get("failed")) if u else None,
    }


def load_prices() -> dict:
    """Read prices.yaml. Returns ``{model: {"input":.., "output":..}}``.

    Written by hand, so the parser handles the file's three fixed levels
    (``models:`` -> model -> input/output) by tracking indentation, and ignores
    everything before ``models:``.
    """
    out: dict = {}
    try:
        text = PRICES.read_text()
    except OSError:
        return out
    in_models = False
    cur_model = None
    model_indent = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if not in_models:
            if re.match(r"^models:\s*$", line):
                in_models = True
            continue
        m = re.match(r"^([\w.\-]+):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if model_indent is None:
            model_indent = indent
        if indent == model_indent:
            # a model name (possibly with an inline - unused - value)
            cur_model = key
            out[cur_model] = {}
            continue
        if indent > model_indent and cur_model and val != "":
            if key == "input_includes_cache":
                out[cur_model][key] = (val.lower() == "true" if val.lower() in ("true", "false") else None)
            else:
                out[cur_model][key] = _float_or_none(val)
        elif indent > model_indent and cur_model and val == "":
            out[cur_model][key] = None
    return out


def _float_or_none(v):
    if v in ("null", "~", ""):
        return None
    return _finite_nonnegative(v)


def _yaml_value(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def write_prices(overrides: dict | None = None) -> Path:
    """Write prices.yaml from the gateway table. Idempotent, keeps a note."""
    prices = {m: dict(v) for m, v in DEFAULT_PRICES.items()}
    if overrides:
        for m, v in overrides.items():
            prices.setdefault(m, {}).update(v)
    lines = [
        "# A6API gateway prices - ESTIMATE ONLY.",
        "# " + PRICE_NOTE.replace(". ", ".\n# "),
        "note: >-",
        f"  {PRICE_NOTE}",
        f"updated: \"{now()}\"",
        "models:",
    ]
    for model in sorted(prices):
        p = prices[model]
        lines.append(f"  {model}:")
        fields = dict(p)
        fields.setdefault("input", None)
        fields.setdefault("output", None)
        for key in sorted(fields):
            lines.append(f"    {key}: {_yaml_value(fields[key])}")
    STATE.mkdir(parents=True, exist_ok=True)
    PRICES.write_text("\n".join(lines) + "\n")
    return PRICES


def _yaml_num(v):
    return "null" if v is None else f"{v}"


def estimate_cost(usage: dict, prices: dict | None = None) -> float | None:
    """Price-based cost estimate, or None when a needed price is null.

    Returns None rather than 0 whenever the numbers are not known, so an
    uncalibrated price can never look like a free run.

    ``input_includes_cache`` must be an explicit boolean when cache-read
    tokens are present.  When true, cached tokens are replaced inside the
    input total; when false, they are billed in addition to input tokens.
    """
    prices = prices if prices is not None else load_prices()
    model = (usage or {}).get("model")
    p = (prices or {}).get(model)
    if not isinstance(p, dict):
        return None
    inp, outp = _finite_nonnegative(p.get("input")), _finite_nonnegative(p.get("output"))
    if inp is None or outp is None:
        return None
    raw = usage or {}
    if raw.get("usage_complete") is False:
        return None
    in_tok = _int_or_none(raw.get("input_tokens", raw.get("prompt_tokens")))
    out_tok = _int_or_none(raw.get("output_tokens", raw.get("completion_tokens")))
    if in_tok is None or out_tok is None:
        return None
    read_tok = _int_or_none(raw.get("cache_read_tokens"))
    write_tok = _int_or_none(raw.get("cache_write_tokens"))
    if ("cache_read_tokens" in raw and read_tok is None) or ("cache_write_tokens" in raw and write_tok is None):
        return None
    if read_tok is None:
        read_tok = 0
    if write_tok is None:
        write_tok = 0
    includes = raw.get("input_includes_cache", p.get("input_includes_cache"))
    if read_tok or write_tok:
        if not isinstance(includes, bool):
            return None
        if includes and read_tok + write_tok > in_tok:
            return None
    if read_tok:
        read_rate = _finite_nonnegative(p.get("cache_read"))
        if read_rate is None or not isinstance(includes, bool):
            return None
        if includes:
            if read_tok > in_tok:
                return None
            input_cost = (in_tok - read_tok) * inp + read_tok * read_rate
        else:
            input_cost = in_tok * inp + read_tok * read_rate
    else:
        input_cost = in_tok * inp
    if write_tok:
        write_rate = _finite_nonnegative(p.get("cache_write"))
        if write_rate is None:
            return None
        if includes:
            input_cost -= write_tok * inp
        input_cost += write_tok * write_rate
    return round(input_cost / 1_000_000 + out_tok / 1_000_000 * outp, 8)


def default_flags(profile: str = "", toolsets: str = "",
                  session: str = "") -> dict:
    """Run flags. ``context_engine`` is the configured engine, defaulting to the
    built-in compressor when config.yaml does not name one."""
    engine = os.environ.get("PHPRETRO_CONTEXT_ENGINE", "").strip()
    if not engine:
        engine = _context_engine_from_config(profile) or "compressor"
    flags: dict = {"context_engine": engine}
    if toolsets:
        flags["toolsets"] = toolsets
    if profile:
        flags["profile"] = profile
    flags["plugins"] = _plugin_marker(profile, session)
    return flags


def _plugin_marker(profile: str, session: str = "") -> dict:
    """Prove the token-terminator ContextEngine was actually active this run.

    Requirement: savings must never be credited on an inactive path, so the
    marker is EVIDENCE, not an assertion. It reads the engine's own store in
    this profile (``<profile>/token-terminator/artifacts.sqlite3``) and reports
    ``active`` only when the engine staged context for THIS run's session. The
    SQLite access is opened read-only and never created, so a marker lookup can
    never touch the engine's data.
    """
    home = (HOME / ".hermes" / "profiles" / profile) if profile else (HOME / ".hermes")
    engine = _context_engine_from_config(profile)
    out = {"tt": False, "plugin": "token-terminator", "engine": engine or "compressor",
           "active": False}
    if engine != "token-terminator":
        return out
    out["tt"] = True
    plugin_yaml = home / "plugins" / "token-terminator" / "plugin.yaml"
    try:
        m = re.search(r"^version:\s*'?([\w.\-]+)'?", plugin_yaml.read_text(errors="replace"), re.M)
        if m:
            out["version"] = m.group(1)
    except OSError:
        pass
    db = home / "token-terminator" / "artifacts.sqlite3"
    if not db.is_file():
        out["error"] = "no store"
        return out
    out["staged_sources"] = _tt_staged_sources(db, session=session or None)
    out["active"] = bool(session) and out["staged_sources"] > 0
    return out


def _tt_staged_sources(db: Path, session: str | None = None) -> int:
    """Count the engine's staged context rows; scoped to a session when known."""
    import sqlite3
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2.0)
    except sqlite3.Error:
        return 0
    try:
        if session:
            row = con.execute(
                "SELECT COUNT(*) FROM tt_context_sources WHERE session_id = ?",
                (session,)).fetchone()
        else:
            row = con.execute("SELECT COUNT(*) FROM tt_context_sources").fetchone()
        return int(row[0]) if row else 0
    except sqlite3.Error:
        return 0
    finally:
        con.close()


def _context_engine_from_config(profile: str) -> str:
    home = (HOME / ".hermes" / "profiles" / profile) if profile else (HOME / ".hermes")
    for path in (home / "config.yaml", HOME / ".hermes" / "config.yaml"):
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        m = re.search(r"^\s{0,4}engine:\s*([\w.\-]+)\s*$", text, re.M)
        if m:
            return m.group(1)
    return ""


def build_run(*, ts_start: str, ts_end: str, role: str, model: str,
              unit: str = "", attempt=None, rc=None, outcome: str = "other",
              usage: dict | None = None, flags: dict | None = None,
              provider: str = PROVIDER, extra: dict | None = None) -> dict:
    """Build one runs.jsonl record.

    Token fields are the raw usage-file values. A value that is missing is
    ``null`` and ``tokens_pessimistic`` carries the pipeline's estimate, so a
    consumer never mistakes "unknown" for "free".
    """
    usage = usage or {}
    norm = parse_usage(usage)
    prices = load_prices()
    if usage.get("runtime") == "openhands":
        import runtime_policy
        prices = runtime_policy.load()["models"]
    est = norm.get("provider_cost_estimate") if norm.get("usage_complete") is not False else None
    cost_source = "usage-file" if est is not None else "none"
    if est is None:
        estimate_usage = dict(usage)
        if model and not estimate_usage.get("model"):
            estimate_usage["model"] = model
        est = estimate_cost(estimate_usage, prices)
        if est is not None:
            cost_source = "runtime-policy" if usage.get("runtime") == "openhands" else "prices.yaml"
    rec = {
        "ts_start": ts_start,
        "ts_end": ts_end,
        "unit": unit or "",
        "attempt": _int_or_none(attempt),
        "role": role if role in ROLES else "other",
        "model": model or (usage.get("model") or ""),
        "provider": provider,
        "runtime": usage.get("runtime", "hermes"),
        "input_tokens": norm["input_tokens"],
        "output_tokens": norm["output_tokens"],
        "cached_tokens": norm["cached_tokens"],
        "cache_write_tokens": norm["cache_write_tokens"],
        "reasoning_tokens": norm["reasoning_tokens"],
        "accounting_source": norm["accounting_source"],
        "accounting_metadata": norm["accounting_metadata"],
        "usage_complete": norm["usage_complete"],
        "api_calls": norm["api_calls"],
        "cost_estimate": est,
        "cost_source": cost_source,
        "cost_unit": "USD (provider estimate)" if cost_source == "usage-file" else "A6API price-table units (uncalibrated)" if cost_source in ("prices.yaml", "runtime-policy") else "unknown",
        "rc": _int_or_none(rc),
        "outcome": outcome if outcome in OUTCOMES else "other",
        "flags": flags or {},
        "usage": usage,
    }
    unknown = [k for k in ("input_tokens", "output_tokens", "api_calls")
               if rec[k] is None]
    if unknown:
        rec["unknown_fields"] = unknown
        rec["tokens_pessimistic"] = PESSIMISTIC_TOKENS
    return rec


# --------------------------------------------------------------------------
# readers (STATE.md numbers come from here)
# --------------------------------------------------------------------------

def read_runs(path: Path | None = None):
    """Every run record in the current log plus its rotated predecessors."""
    path = path or RUNS
    files = sorted(path.parent.glob(f"{path.stem}-*{path.suffix}")) + [path]
    records, outcomes, seen = [], {}, set()
    for f in files:
        try:
            for line in f.read_text(errors="replace").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    kind = rec.get("record_type", "run")
                    if kind == "outcome":
                        outcomes[rec.get("run_id")] = rec.get("outcome", "other")
                    elif kind == "run":
                        rid = rec.get("run_id")
                        if rid and rid in seen:
                            continue
                        if rid:
                            seen.add(rid)
                        records.append(rec)
        except OSError:
            if f.exists():
                raise
            continue
    for rec in records:
        if rec.get("run_id") in outcomes:
            rec["outcome"] = outcomes[rec["run_id"]]
        yield rec


def run_total(rec: dict) -> int:
    """A run's token total, using the pessimistic estimate when unknown.

    Preference order: the total including auxiliary calls (the billed figure),
    then the usage file's own total, then the sum of the recorded parts, then
    the pessimistic estimate. Never returns 0 for an unknown value unless the
    record genuinely has none.
    """
    if "charged_tokens" in rec:
        return int(rec["charged_tokens"])
    u = rec.get("usage") or {}
    aux = u.get("total_including_auxiliary") or {}
    val = aux.get("total_tokens") if isinstance(aux, dict) else None
    if val is None:
        val = u.get("total_tokens")
    if val is None:
        val = rec.get("total_including_auxiliary")
    if val is None:
        parts = [rec.get(k) for k in ("input_tokens", "output_tokens", "cached_tokens", "cache_write_tokens")]
        if any(p is not None for p in parts):
            val = sum(p or 0 for p in parts)
    if val is None:
        return int(rec.get("tokens_pessimistic", PESSIMISTIC_TOKENS))
    return int(val)


def totals_for_day(day: str) -> dict:
    """Tokens and run count for one UTC day, from runs.jsonl."""
    tok = 0
    runs = 0
    merged = 0
    for rec in read_runs():
        if _month_of(rec.get("ts_start", "")) and rec.get("ts_start", "")[:10] != day:
            continue
        runs += 1
        tok += run_total(rec)
        if rec.get("outcome") == "merged":
            merged += 1
    return {"tokens": tok, "runs": runs, "merged": merged}


def unit_token_totals() -> dict:
    """Total tokens per unit, from runs.jsonl."""
    per: dict = {}
    for rec in read_runs():
        u = rec.get("unit") or ""
        if not u:
            continue
        per[u] = per.get(u, 0) + run_total(rec)
    return per


def unit_run_summary(unit: str) -> dict:
    """Aggregate one unit's runs: tokens, runs, outcomes, cost by role."""
    tok, runs, by_role, outcomes, cost = 0, 0, {}, {}, 0.0
    for rec in read_runs():
        if (rec.get("unit") or "") != unit:
            continue
        runs += 1
        tok += run_total(rec)
        r = rec.get("role", "other")
        by_role[r] = by_role.get(r, 0) + run_total(rec)
        o = rec.get("outcome", "other")
        outcomes[o] = outcomes.get(o, 0) + 1
        if rec.get("cost_estimate") is not None:
            cost += float(rec["cost_estimate"])
    return {"tokens": tok, "runs": runs, "by_role": by_role,
            "outcomes": outcomes, "cost_estimate": round(cost, 8)}


# --------------------------------------------------------------------------
# selftest
# --------------------------------------------------------------------------

def selftest() -> int:
    import tempfile
    global STATE, RUNS, EVENTS, PRICES
    keep = (STATE, RUNS, EVENTS, PRICES)
    tmp = Path(tempfile.mkdtemp(prefix="tel-selftest-"))
    STATE = tmp
    RUNS = tmp / "runs.jsonl"
    EVENTS = tmp / "events.jsonl"
    PRICES = tmp / "prices.yaml"
    try:
        # unknown values are null, never 0, and carry the estimate
        r = build_run(ts_start="2026-10-06T00:00:00Z", ts_end="2026-10-06T00:00:05Z",
                      role="builder", model="gpt-6-luna", unit="F1", attempt=1,
                      rc=0, outcome="merged", usage={})
        assert r["input_tokens"] is None, r
        assert r["cost_estimate"] is None, r
        assert r["tokens_pessimistic"] == PESSIMISTIC_TOKENS, r
        assert r["role"] == "builder" and r["outcome"] == "merged", r

        # a real usage file round-trips
        usage = {"input_tokens": 100, "output_tokens": 20, "cache_read_tokens": 5,
                 "api_calls": 3, "model": "gpt-6-luna",
                 "estimated_cost_usd": 0.0, "cost_status": "unknown"}
        r2 = build_run(ts_start="2026-10-06T00:00:00Z", ts_end="2026-10-06T00:00:09Z",
                       role="reviewer", model="gpt-6-luna", unit="F1", rc=0,
                       outcome="other", usage=usage)
        assert r2["input_tokens"] == 100 and r2["output_tokens"] == 20, r2
        assert r2["cached_tokens"] == 5 and r2["api_calls"] == 3, r2
        assert r2["cost_estimate"] is None, "0.0+unknown must not become a real cost"

        # price table estimate when prices are known
        write_prices()
        p = load_prices()
        assert p["gpt-6-luna"]["input"] == 0.018, p
        assert p["gpt-6.1-sol"]["input"] is None, p
        est = estimate_cost({"model": "gpt-6-luna", "input_tokens": 1_000_000,
                             "output_tokens": 1_000_000}, p)
        assert abs(est - (0.018 + 0.09)) < 1e-9, est
        assert estimate_cost({"model": "gpt-6.1-sol", "input_tokens": 1,
                              "output_tokens": 1}, p) is None

        # scrubber keeps token counts, drops credentials and prompts
        s = scrub({"api_key": "SECRET", "input_tokens": 5, "authorization": "Bearer x",
                   "prompt": "do the thing", "session_id": "abc", "nested": {"cookie": "y"}})
        assert "api_key" not in s and "authorization" not in s, s
        assert "prompt" not in s and "cookie" not in s["nested"], s
        assert s["input_tokens"] == 5 and s["session_id"] == "abc", s

        # append-only + readers
        log_run({"ts_start": "2026-10-06T01:00:00Z", "unit": "F1", "role": "builder",
                 "outcome": "merged", "usage": {"total_tokens": 500}})
        log_run({"ts_start": "2026-10-06T02:00:00Z", "unit": "F2", "role": "reviewer",
                 "outcome": "review_fix", "input_tokens": 10, "output_tokens": 4})
        assert RUNS.read_text().count("\n") == 2, RUNS.read_text()
        assert totals_for_day("2026-10-06")["tokens"] == 514, totals_for_day("2026-10-06")
        assert unit_token_totals() == {"F1": 500, "F2": 14}, unit_token_totals()
        assert unit_run_summary("F1")["outcomes"] == {"merged": 1}, unit_run_summary("F1")

        # monthly rotation keeps the old month's file
        old = int(datetime(2026, 9, 15, tzinfo=timezone.utc).timestamp())
        os.utime(RUNS, (old, old))
        append(RUNS, {"ts_start": "2026-10-06T03:00:00Z", "unit": "F3"})
        rotated = list(tmp.glob("runs-2026-09.jsonl"))
        assert rotated, [p.name for p in tmp.iterdir()]
        assert "F1" in rotated[0].read_text() and "F3" in RUNS.read_text()

        # events
        log_event("merged", "F1", "PR #65 merged")
        ev = [json.loads(l) for l in EVENTS.read_text().splitlines() if l.strip()]
        assert ev[0]["kind"] == "merged" and ev[0]["unit"] == "F1", ev

    finally:
        STATE, RUNS, EVENTS, PRICES = keep
        shutil.rmtree(tmp, ignore_errors=True)
    print("telemetry selftest OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="pipeline telemetry")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--write-prices", action="store_true")
    ap.add_argument("--show-prices", action="store_true")
    ap.add_argument("--unit", help="print one unit's run summary")
    ap.add_argument("--day", help="print one UTC day's totals")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.write_prices:
        print("wrote", write_prices())
        return 0
    if args.show_prices:
        print(json.dumps(load_prices(), indent=1, sort_keys=True))
        return 0
    if args.unit:
        print(json.dumps(unit_run_summary(args.unit), indent=1, sort_keys=True))
        return 0
    if args.day:
        print(json.dumps(totals_for_day(args.day), indent=1, sort_keys=True))
        return 0
    ap.error("choose --selftest, --write-prices, --show-prices, --unit or --day")
    return 2


if __name__ == "__main__":
    sys.exit(main())

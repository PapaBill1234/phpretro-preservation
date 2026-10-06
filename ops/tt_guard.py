"""Guard for the Token Terminator context engine (builder profile only).

The engine is only kept if it pays for itself. This module measures, from the
append-only ``runs.jsonl`` telemetry, everything needed to decide that, and the
rules are deliberately hostile to flattering numbers:

* Cost is **billed cost per MERGED unit over ALL attempts** - every builder
  attempt including failed, timed-out and retried ones, plus that unit's review
  runs. A unit whose spend is not fully known is reported as ``unknown`` and
  excluded from the median; it is never silently treated as free.
* A unit that failed early is never counted as a saving: only units that
  actually merged are in the comparison, and their failures are still charged.
* Tokens per builder attempt and the first-attempt success rate are recorded.
* The next N merged units are compared with the previous N. If the median cost
  per merged unit is not at least ``MIN_SAVING`` lower, or first-attempt success
  is lower, the engine is deselected and uninstalled.
* Two units showing missing-context symptoms (re-reading the same file over and
  over) also force removal: a cheap run that lost the plot is not a saving.

Nothing here talks to the network or needs the plugin installed; it only reads
telemetry and writes its own state file, so it keeps working after a revert.
"""

from __future__ import annotations

import json
import os
import re
import statistics
from pathlib import Path

HOME = Path.home()
OPS = Path(os.environ.get("PHPRETRO_OPS", HOME / "phpretro-ops"))
STATE = OPS / "state"
RUNS = STATE / "runs.jsonl"
TT_STATE = STATE / "tt.json"

WINDOW = 6              # units per side of the comparison
MIN_SAVING = 0.15       # median cost per merged unit must drop by >= 15%
REREAD_LIMIT = 3        # same path read this many times in one attempt = symptom
SENSITIVE_PATHS_ARE_SAFETY = True

# Roles whose spend belongs to the unit they name. Planner runs are global (the
# planner is not dispatched per unit in the log), so they are excluded rather
# than mis-attributed.
UNIT_ROLES = ("builder", "reviewer")


def read_runs(path: Path | None = None) -> list[dict]:
    out: list[dict] = []
    for line in (path or RUNS).read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _ts(rec: dict) -> str:
    return str(rec.get("ts_end") or rec.get("ts_start") or "")


def merged_units(runs: list[dict]) -> list[dict]:
    """Merged units in merge order. A unit merged when a builder attempt did."""
    first_merge: dict[str, str] = {}
    for rec in runs:
        if rec.get("role") != "builder" or rec.get("outcome") != "merged":
            continue
        unit = str(rec.get("unit") or "")
        if not unit:
            continue
        ts = _ts(rec)
        if unit not in first_merge or ts < first_merge[unit]:
            first_merge[unit] = ts
    return [{"unit": u, "ts": t} for u, t in sorted(first_merge.items(), key=lambda kv: kv[1])]


def unit_records(runs: list[dict], unit: str) -> list[dict]:
    return [r for r in runs if r.get("unit") == unit and r.get("role") in UNIT_ROLES]


def unit_cost(recs: list[dict]) -> float | None:
    """Billed cost over ALL of the unit's attempts, or None if any is unknown.

    None means "not fully known": the unit is excluded from the median rather
    than counted as a saving. A failed or timed-out attempt is included in the
    sum whenever its cost is known.
    """
    costs = [r.get("cost_estimate") for r in recs]
    if not costs or any(c is None for c in costs):
        return None
    return round(sum(float(c) for c in costs if c is not None), 10)


def unit_tokens(recs: list[dict]) -> int | None:
    """Total tokens across every builder attempt for the unit (None if unknown)."""
    tok = [r.get("input_tokens") for r in recs if r.get("role") == "builder"]
    if not tok or any(t is None for t in tok):
        return None
    totals = [r.get("input_tokens", 0) + r.get("output_tokens", 0)
              for r in recs if r.get("role") == "builder"]
    return sum(int(t) for t in totals)


def builder_attempts(recs: list[dict]) -> list[dict]:
    return sorted((r for r in recs if r.get("role") == "builder"),
                  key=lambda r: (r.get("attempt") or 0, _ts(r)))


def first_attempt_merged(recs: list[dict]) -> bool:
    for r in builder_attempts(recs):
        if r.get("attempt") == 1:
            return r.get("outcome") == "merged"
    return False


def context_engine_of(recs: list[dict]) -> str:
    for r in recs:
        eng = (r.get("flags") or {}).get("context_engine")
        if eng:
            return str(eng)
    return ""


def marker_active(recs: list[dict]) -> bool:
    """True only when the plugin marker says the engine was active for the run."""
    for r in recs:
        plug = (r.get("flags") or {}).get("plugins") or {}
        if plug.get("tt") and plug.get("active"):
            return True
    return False


# --------------------------------------------------------------------------
# missing-context symptoms
# --------------------------------------------------------------------------

_READ_RE = re.compile(r"read_file|Read|cat |sed -n|view_file", re.I)


def _read_paths(dump: str) -> list[str]:
    paths = []
    for m in re.finditer(r"[\w./\-]+\.(?:go|py|md|yaml|yml|json|sh|sql|ts|js|html|css)",
                         dump or ""):
        paths.append(m.group(0))
    return paths


def context_loss_symptom(recs: list[dict], dump: str = "") -> bool:
    """Heuristic: the same file was read to exhaustion in one attempt.

    The cheap, checkable form of "re-reading the same files repeatedly" is a
    single attempt reading the same path at least ``REREAD_LIMIT`` times. This is
    deliberately strict; it only fires on clear thrash and never on a one-off.
    """
    if not dump:
        return False
    counts: dict[str, int] = {}
    lines = [ln for ln in dump.splitlines() if _READ_RE.search(ln)]
    for ln in lines:
        for p in _read_paths(ln):
            counts[p] = counts.get(p, 0) + 1
    return any(n >= REREAD_LIMIT for n in counts.values())


# --------------------------------------------------------------------------
# comparison
# --------------------------------------------------------------------------

def measure(runs: list[dict], window: int = WINDOW) -> dict:
    """Per-unit rows plus the windowed comparison and the verdict."""
    units = merged_units(runs)
    rows = []
    for u in units:
        recs = unit_records(runs, u["unit"])
        rows.append({
            "unit": u["unit"], "ts": u["ts"],
            "cost": unit_cost(recs),
            "tokens": unit_tokens(recs),
            "builder_attempts": len(builder_attempts(recs)),
            "first_attempt_merged": first_attempt_merged(recs),
            "context_engine": context_engine_of(recs),
            "marker_active": marker_active(recs),
        })

    known = [r for r in rows if r["cost"] is not None]
    prev = known[-2 * window:-window] if len(known) >= 2 * window else known[:-window] if len(known) > window else []
    nxt = known[-window:]
    if len(known) < 2 * window:
        # Not enough on both sides yet: report readiness, do not rule.
        return {"rows": rows, "window": window, "status": "insufficient",
                "need": 2 * window, "have": len(known),
                "prev": None, "next": None, "verdict": "", "revert": False}

    prev_costs = [r["cost"] for r in prev]
    next_costs = [r["cost"] for r in nxt]
    prev_median = statistics.median(prev_costs)
    next_median = statistics.median(next_costs)
    prev_first = sum(1 for r in prev if r["first_attempt_merged"]) / len(prev)
    next_first = sum(1 for r in nxt if r["first_attempt_merged"]) / len(nxt)

    drop = 0.0 if prev_median <= 0 else (prev_median - next_median) / prev_median
    saving_ok = drop >= MIN_SAVING
    first_ok = next_first >= prev_first
    revert = not (saving_ok and first_ok)

    reasons = []
    if not saving_ok:
        reasons.append(
            f"median cost per merged unit fell {drop * 100:.1f}% "
            f"(need >= {MIN_SAVING * 100:.0f}%)")
    if not first_ok:
        reasons.append(
            f"first-attempt success fell from {prev_first * 100:.0f}% "
            f"to {next_first * 100:.0f}%")
    return {
        "rows": rows, "window": window, "status": "measured",
        "prev": {"units": [r["unit"] for r in prev], "median_cost": prev_median,
                 "first_attempt_rate": round(prev_first, 4),
                 "median_tokens": _median_tokens(prev)},
        "next": {"units": [r["unit"] for r in nxt], "median_cost": next_median,
                 "first_attempt_rate": round(next_first, 4),
                 "median_tokens": _median_tokens(nxt)},
        "saving_pct": round(drop * 100, 2),
        "revert": revert,
        "verdict": ("KEEP" if not revert else "REVERT") + (
            "" if not reasons else ": " + "; ".join(reasons)),
    }


def _median_tokens(rows: list[dict]) -> float | None:
    vals = [r["tokens"] for r in rows if r["tokens"] is not None]
    return statistics.median(vals) if vals else None


def rules_state(path: Path | None = None) -> dict:
    return read_json(path or TT_STATE, {}) or {}


def read_json(p: Path, default):
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return default


def note_symptom(unit: str, path: Path | None = None) -> dict:
    """Record a missing-context symptom; report whether two units now show it."""
    p = path or TT_STATE
    st = read_json(p, {}) or {}
    seen = set(st.get("symptom_units") or [])
    seen.add(unit)
    st["symptom_units"] = sorted(seen)
    st["symptom_revert"] = len(seen) >= 2
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, indent=1, sort_keys=True))
    return {"units": st["symptom_units"], "revert": st["symptom_revert"]}


def record(path: Path | None = None, runs: list[dict] | None = None) -> dict:
    """Recompute and persist the guard state; return it."""
    p = path or TT_STATE
    result = measure(runs if runs is not None else read_runs())
    st = read_json(p, {}) or {}
    st.update({
        "window": result["window"],
        "status": result["status"],
        "saving_pct": result.get("saving_pct"),
        "revert": bool(result.get("revert")) or bool(st.get("symptom_revert")),
        "verdict": result.get("verdict", ""),
        "prev": result.get("prev"),
        "next": result.get("next"),
        "units": result["rows"],
    })
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, indent=1, sort_keys=True))
    return st


def summary_lines(path: Path | None = None) -> list[str]:
    """Five-ish lines for STATE.md."""
    st = read_json(path or TT_STATE, {}) or {}
    verdict = st.get("verdict") or ("collecting" if st.get("status") == "insufficient" else "?")
    lines = [f"token-terminator: {verdict}"]
    if st.get("status") == "insufficient":
        have = len([r for r in (st.get("units") or []) if r.get("cost") is not None])
        lines.append(f"  need {st.get('window', WINDOW) * 2} priced merged units, have {have}")
    elif st.get("prev") and st.get("next"):
        pv, nx = st["prev"], st["next"]
        lines.append(f"  median cost/merged unit: {pv['median_cost']:.6f} -> {nx['median_cost']:.6f} "
                     f"({st.get('saving_pct')}%)")
        lines.append(f"  first-attempt success: {pv['first_attempt_rate'] * 100:.0f}% -> "
                     f"{nx['first_attempt_rate'] * 100:.0f}%")
    if st.get("symptom_units"):
        lines.append(f"  missing-context symptom units: {', '.join(st['symptom_units'])}")
    if st.get("revert"):
        lines.append("  ACTION: engine did not pay off - deselect and uninstall")
    return lines


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Token Terminator cost/quality guard")
    ap.add_argument("--check", action="store_true", help="recompute and print the verdict")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.check:
        st = record()
        if args.json:
            print(json.dumps(st, indent=1, sort_keys=True))
        else:
            print("\n".join(summary_lines()))
        return 1 if st.get("revert") else 0
    return 0


def selftest() -> int:
    """Deterministic checks on synthetic telemetry (no network, no real logs)."""
    def run(unit, role, attempt, outcome, cost, tokens=(100, 10), eng="token-terminator"):
        return {"unit": unit, "role": role, "attempt": attempt, "outcome": outcome,
                "cost_estimate": cost, "input_tokens": tokens[0], "output_tokens": tokens[1],
                "ts_end": f"2026-10-06T00:00:{attempt:02d}Z",
                "flags": {"context_engine": eng,
                          "plugins": {"tt": eng == "token-terminator", "active": True}}}

    # A cheap, clean unit.
    ok = [run("U1", "builder", 1, "merged", 0.10), run("U1", "reviewer", 1, "other", 0.01)]

    # A failed-first unit: the failure is still charged.
    fail_then = [run("U2", "builder", 1, "gate_failed", 0.50),
                 run("U2", "builder", 2, "merged", 0.10)]

    # An unknown-cost unit must be excluded from the median, not counted.
    unknown = [run("U3", "builder", 1, "merged", None)]

    assert unit_cost(ok) == 0.11, unit_cost(ok)
    assert unit_cost(fail_then) == 0.60, "a failed attempt must stay in the total"
    assert unit_cost(unknown) is None, "unknown spend must not become a number"
    assert first_attempt_merged(ok) is True
    assert first_attempt_merged(fail_then) is False, "attempt 1 failed, so not first-try"

    # Too few priced units -> no ruling.
    r = measure([*ok, *fail_then, *unknown])
    assert r["status"] == "insufficient", r["status"]
    assert r["revert"] is False, "must not rule without both windows"

    # Build two full windows: previous expensive, next cheap -> KEEP.
    def window(name, base, merged_first=True):
        rows = []
        for i in range(6):
            u = f"{name}{i}"
            rows.append(run(u, "builder", 1, "merged" if merged_first else "gate_failed", base))
            if not merged_first:
                rows.append(run(u, "builder", 2, "merged", base))
        return rows

    prev = window("A", 0.20)
    nxt = window("B", 0.10)
    v = measure([*prev, *nxt])
    assert v["status"] == "measured", v
    assert v["saving_pct"] == 50.0, v["saving_pct"]
    assert v["revert"] is False, v["verdict"]

    # Same price -> must revert (no saving).
    flat = measure([*window("A", 0.20), *window("B", 0.20)])
    assert flat["revert"] is True, flat["verdict"]
    assert "need >= 15%" in flat["verdict"], flat["verdict"]

    # Cheaper but sloppier (first-attempt success fell) -> must revert.
    sloppy = measure([*window("A", 0.20, merged_first=True),
                      *window("B", 0.10, merged_first=False)])
    assert sloppy["revert"] is True, sloppy["verdict"]
    assert "first-attempt" in sloppy["verdict"], sloppy["verdict"]

    # Missing-context symptoms: two units disable.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "tt.json"
        assert note_symptom("X1", p)["revert"] is False
        assert note_symptom("X2", p)["revert"] is True
        dump = "\n".join(['read_file path="internal/a.go"'] * 3)
        assert context_loss_symptom([], dump) is True
        assert context_loss_symptom([], 'read_file path="internal/a.go"') is False

    # marker_active is False when the marker says inactive.
    inactive = [run("U9", "builder", 1, "merged", 0.1, eng="compressor")]
    assert marker_active(ok) is True and marker_active(inactive) is False

    print("tt_guard selftest OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

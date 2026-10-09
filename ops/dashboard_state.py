"""Typed dashboard projections shared with controller accounting; no prompts."""
from __future__ import annotations
import json
from pathlib import Path
import integrity
import telemetry
import worker


def live_workers(ops, units, now):
    result = []
    for path in sorted((Path(ops) / "state" / "receipts").glob("*.json")):
        if path.name.count(".") != 1 or path.stat().st_size > 65536:
            continue
        try:
            rec = json.loads(path.read_text())
            if rec.get("runtime") != "openhands" or rec.get("status") != "running":
                continue
            if not worker.alive(rec.get("worker_pid"), rec.get("worker_identity")):
                continue
            uid = rec.get("unit", "")
            unit = units.get(uid, {})
            usage = rec.get("usage") or {}
            result.append({"id": uid, "title": unit.get("title"), "model": rec.get("model"),
                           "role": rec.get("role"), "age": max(0, now - rec.get("prepared_at", now)),
                           "attempts": rec.get("attempt"), "tokens": usage.get("total_tokens"),
                           "pid": rec["worker_pid"], "run_id": rec["run_id"],
                           "hint": "OpenHands " + str(rec.get("role")) + "; durable worker receipt active"})
        except (OSError, ValueError, TypeError, KeyError):
            continue
    return result


def run_cost(record, prices=None):
    if record.get("usage_complete") is False:
        return None
    if "cost_estimate" in record:
        return telemetry._finite_nonnegative(record["cost_estimate"])
    usage = dict(record.get("usage") or record)
    usage.setdefault("model", record.get("model"))
    usage.setdefault("cache_read_tokens", record.get("cached_tokens", 0))
    return telemetry.estimate_cost(usage, prices)


def planning_queue(ops):
    result = []
    for path in sorted((Path(ops) / "state" / "planning-needed").glob("*.json"))[:100]:
        try:
            if path.stat().st_size > 65536:
                continue
            record = json.loads(path.read_text())
            if record.get("status") != "awaiting-subscription-brief":
                continue
            result.append({k: record.get(k) for k in ("unit", "reason", "status", "attempts", "tokens", "paths", "depends_on")})
        except (OSError, ValueError):
            continue
    return result

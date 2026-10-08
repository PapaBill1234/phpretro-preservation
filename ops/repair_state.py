#!/usr/bin/env python3
"""Idempotent, STOP-only reconciliation for the 2026-10-08 controller repair.

No agents, provider calls, environment files or budget resets. The operator
supplies the independently verified maintenance PR/merge commit. Back up state
before applying; the full prior roadmap is also kept in reconciliation.jsonl.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import re

import orchestrator as o
import integrity as c


def repaired(roadmap, state, pr, commit):
    road, st = copy.deepcopy(roadmap), copy.deepcopy(state)
    for u in road.values():
        if u.get("status") in ("design", "design-blocked"):
            u["planning_ready"] = False
            u["blocked_reason"] = "No approved bounded implementation contract; reserved design only"
    if "F38" in road:
        u = road["F38"]
        u["blocked_reason"] = "Durable adapter and independent sensitive-path review remain incomplete; architecture chosen in restart-contracts.md"
        u["feedback"] = "Implement the F38 development replay contract in docs/roadmap/restart-contracts.md; preserve existing PR history. Do not recover the conflicting PR unchanged."
        u["reason"] = u["blocked_reason"]
        u["repair_required"] = True
        u["implementation_ready"] = False
    for uid in ("F39a", "QA3"):
        if uid in road:
            road[uid].update(status="merged", pr=pr, branch="codex/hermes-pipeline-repair",
                delivery_commit=commit, repair_required=False, split_requested=False,
                reason=f"Delivered by independently reviewed controller repair PR #{pr}; original history retained",
                updated=o.now())
    if "F39a" in road:
        road["F39a"]["paths"] = ["internal/audit/audit.go", "internal/audit/audit_test.go",
            "internal/audit/redact.go", "internal/audit/redact_test.go",
            "internal/audit/redact_integration_test.go", "docs/evidence/F39-a-audit-redaction.md", "docs/units/F39a.md"]
    if "F49" in road:
        road["F49"].update(planning_ready=True, blocked_reason="",
            planning_context="docs/roadmap/restart-contracts.md",
            planning_paths=["frontend/src/localization/catalogPackage.ts", "frontend/tests/localization-package.test.ts", "docs/evidence/F49-locale-catalog.md"],
            planning_acceptance=["Only the F49 synthetic catalog validation contract in restart-contracts.md"],
            planning_tests=["cd frontend && npm test && npm run typecheck && npm run build", "bash scripts/check.sh"])
    approved = o.validated_units(o.REPO / "docs/roadmap/restart-units.yaml")["units"]
    for u in approved:
        if u["id"] not in road:
            road[u["id"]] = dict(u, attempts=0, tokens=0, pr=0, updated=o.now())
    if int(st.get("provider_errors", 0)) == 0:
        st.pop("provider_pause_reason", None)
    # Known Jev-only size advisories previously prevented these bounded units
    # from launching. Clear the advisory cache, retaining attempts and spend.
    for u in road.values():
        if u.get("size_source") == "jev":
            for key in ("size_action", "size_check_at", "size_source"):
                u.pop(key, None)
    return road, st


def apply(pr, commit):
    if not o.STOP_FILE.exists():
        raise c.IntegrityError("repair reconciliation requires STOP")
    o.ensure_dirs()
    with (o.LOCK_DIR / "orchestrator.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        done = o.STATE_DIR / "controller-repair-20261008.json"
        if done.exists():
            previous = o.read_json(done, {})
            if previous.get("pr") != pr or previous.get("commit") != commit:
                raise c.IntegrityError("repair identity differs from applied migration")
            return False
        st = o.load_state()
        old = o.load_roadmap(st)
        road, revised = repaired(old, st, pr, commit)
        for uid, u in old.items():
            for key in ("tokens", "attempts"):
                if road[uid].get(key, 0) != u.get(key, 0):
                    raise c.IntegrityError("repair changed historical counters")
        previous_path = o.STATE_DIR / "controller-repair-previous.json"
        if not previous_path.exists():
            c.atomic_json(previous_path, {"roadmap": old, "state": st})
        # One maintenance PR delivered both support fixes; do not count it
        # twice or rewrite any existing reservation/run/baseline.
        rows = c.ledger_records(o.STATE_DIR)
        for uid in ("F39a", "QA3"):
            if uid in road and not any(r.get("record_type") == "delivery" and r.get("pr") == pr and r.get("unit") == uid for r in rows):
                c.append_record(o.STATE_DIR / "runs.jsonl", {"record_type": "delivery",
                    "unit": uid, "pr": pr, "head": commit, "merged_at": o.now(), "count_merge": False})
        o.save_roadmap(road)
        o.write_json(o.STATE_JSON, revised)
        jev = o.read_json(o.STATE_DIR / "jev.json", {})
        jev.setdefault("enabled", {}).update(a=False, b=False, c=False)
        jev.setdefault("disabled_reason", {}).update(a="Post-repair baseline: rules only",
            b="Post-repair baseline: rules only", c="Review skip disabled; exact-head independent review required")
        o.write_json(o.STATE_DIR / "jev.json", jev)
        c.atomic_json(done, {"pr": pr, "commit": commit, "applied_at": o.now(),
            "added_units": [uid for uid in road if uid not in old], "historical_counters_preserved": True})
        return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pr", type=int, required=True)
    ap.add_argument("--commit", required=True)
    args = ap.parse_args()
    if args.pr <= 0 or not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        ap.error("require a real positive PR number and full merge SHA")
    print("State reconciled; STOP retained" if apply(args.pr, args.commit) else "Repair already reconciled; STOP retained")


if __name__ == "__main__":
    main()

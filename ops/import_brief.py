#!/usr/bin/env python3
"""Import one subscription-authored brief under STOP and the controller lock."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
from pathlib import Path

import integrity as control
import orchestrator as o
import runtime_policy


def validate(document, roadmap, head):
    if document.get("schema") != "phpretro.brief.v1" or document.get("base_commit") != head:
        raise control.IntegrityError("brief schema/base does not match the current source")
    if document.get("planning_source") != "subscription-codex":
        raise control.IntegrityError("brief must be prepared in subscription Codex")
    units = document.get("units")
    if not isinstance(units, list) or not 1 <= len(units) <= 3:
        raise control.IntegrityError("brief requires one to three bounded units")
    result = []
    ids = set(roadmap)
    for proposed in units:
        uid = proposed.get("id")
        if not isinstance(uid, str) or not __import__("re").fullmatch(r"[A-Z][A-Za-z0-9]{1,31}", uid):
            raise control.IntegrityError("invalid unit ID")
        existing = roadmap.get(uid)
        if existing and existing.get("status") in ("merged", "building", "pr_open", "queued"):
            raise control.IntegrityError("cannot replace active/delivered work")
        if any(x.get("id") == uid for x in result):
            raise control.IntegrityError("duplicate unit ID")
        if proposed.get("size") not in ("S", "M"):
            raise control.IntegrityError("unit must be size S or M")
        for field in ("title", "paths", "acceptance", "tests", "fixtures"):
            if not proposed.get(field):
                raise control.IntegrityError("brief missing " + field)
        paths = proposed["paths"]
        if not isinstance(paths, list) or len(paths) > 12 or not all(
            control.safe_path(p, o.PROTECTED_PREFIXES + o.PROTECTED_FILES) for p in paths
        ):
            raise control.IntegrityError("unsafe/unbounded brief paths")
        models = proposed.get("allowed_models", [])
        if not models or any(not runtime_policy.load()["models"].get(m, {}).get("automatic") for m in models):
            raise control.IntegrityError("brief models outside coding policy")
        if proposed.get("token_cap") != o.PER_UNIT_TOKEN_CAP:
            raise control.IntegrityError("brief cannot change the preserved unit cap")
        unit = dict(proposed)
        if existing:
            for field in ("attempts", "tokens", "pr", "branch", "review_rounds", "conflict_rounds", "planner_retries"):
                if field in existing:
                    unit[field] = existing[field]
        unit.update(status="todo", planning_ready=False, implementation_ready=True,
                    planning_source="subscription-codex", brief_base=head)
        result.append(unit)
        ids.add(uid)
    if any(dep not in ids for u in result for dep in u.get("depends_on", [])):
        raise control.IntegrityError("brief references unknown dependencies")
    graph = {uid: row.get("depends_on", []) for uid, row in roadmap.items()}
    graph.update({row["id"]: row.get("depends_on", []) for row in result})
    visiting, visited = set(), set()
    def visit(uid):
        if uid in visiting:
            raise control.IntegrityError("brief introduces a dependency cycle")
        if uid in visited:
            return
        visiting.add(uid)
        for dep in graph.get(uid, []):
            visit(dep)
        visiting.remove(uid)
        visited.add(uid)
    for row in result:
        visit(row["id"])
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("brief", type=Path)
    args = ap.parse_args()
    if not o.STOP_FILE.exists():
        raise control.IntegrityError("STOP is required for brief import")
    raw = args.brief.read_bytes()
    if len(raw) > 65536:
        raise control.IntegrityError("oversized brief")
    digest = hashlib.sha256(raw).hexdigest()
    o.ensure_dirs()
    with (o.LOCK_DIR / "orchestrator.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        journal = o.STATE_DIR / "brief-imports" / (digest + ".json")
        if journal.exists() and json.loads(journal.read_text()).get("status") == "complete":
            print("Brief already imported")
            return 0
        state = o.load_state()
        roadmap = o.load_roadmap(state)
        head = o.git_out("rev-parse", "origin/main")
        units = validate(json.loads(raw), roadmap, head)
        # A prepared journal plus preserved counters makes a crash replay additive.
        control.atomic_json(journal, {"sha256": digest, "status": "prepared", "units": [u["id"] for u in units]})
        for unit in units:
            roadmap[unit["id"]] = unit
        o.save_roadmap(roadmap)
        for unit in units:
            pending = runtime_policy.OPS / "state" / "planning-needed" / (unit["id"] + ".json")
            if pending.exists():
                handoff = json.loads(pending.read_text())
                handoff.update(status="imported", brief_sha256=digest)
                control.atomic_json(pending, handoff)
        control.atomic_json(journal, {"sha256": digest, "status": "complete", "units": [u["id"] for u in units]})
        print("Imported " + ", ".join(u["id"] for u in units))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

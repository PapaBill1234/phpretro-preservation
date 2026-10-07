#!/usr/bin/env python3
"""Read-only roadmap assessment. Delivery is never an implementation verdict.

No provider, worker, scheduler, ledger or network access. The reviewed catalog
records explicit assessments against exact source bytes. New/changed deliveries
require a fresh assessment; the publisher cannot automatically promote them.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

CLASSES = ("not started", "designed", "scaffold", "implemented", "verified")
AREAS = ("legacy preserved behavior", "Redis", "Go backend", "React frontend",
         "themes: Habbo", "themes: Atom CMS", "themes: theme system",
         "Polaris integration", "staff", "infrastructure")


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def safe_artifact(repo: Path, path: str) -> Path:
    p = repo / path
    if not path or p.is_symlink() or not p.resolve().is_relative_to(repo.resolve()):
        raise ValueError("assessment path escapes repository")
    if any((part.startswith(".") and part != ".github") or re.search(r"(?i)secret|credential|\.env", part) for part in Path(path).parts):
        raise ValueError("assessment may not read secret files")
    return p


def build(repo: Path, canonical: dict, runtime: dict, deliveries: dict,
          catalog=None, timestamp=None) -> dict:
    catalog = catalog or json.loads((repo / "ops/roadmap-assessment.json").read_text())
    assessed = {row["id"]: row for row in catalog["units"]}
    if len(assessed) != len(catalog["units"]):
        raise ValueError("duplicate assessment identity")
    items = []
    divergences = []
    for uid in sorted(set(canonical) | set(runtime), key=lambda x: (not x.startswith("F"), int(re.search(r"\d+", x)[0]) if re.search(r"\d+", x) else 0, x)):
        c, r, a = canonical.get(uid, {}), runtime.get(uid, {}), assessed.get(uid)
        delivery = deliveries.get(uid, [])
        merged = bool(delivery)
        classification = "designed" if c.get("design_doc") or r.get("design_doc") else "not started"
        reason = "Unassessed; delivery never proves implementation."
        stale = []
        evidence, criteria, gaps = [], [], []
        area = "infrastructure"
        if a:
            area = a["area"]
            if a["classification"] not in CLASSES or area not in AREAS:
                raise ValueError("invalid assessment classification or area")
            evidence, criteria, gaps = a["evidence"], a["criteria"], a.get("gaps", [])
            for e in evidence:
                p = safe_artifact(repo, e["path"])
                if not p.is_file() or fingerprint(p) != e["fingerprint"]:
                    stale.append(e["path"])
            for source in criteria:
                p = safe_artifact(repo, source["path"])
                if not p.is_file() or source["quote"] not in p.read_text():
                    stale.append(source["path"])
            if {d["pr"] for d in delivery} != set(a.get("assessed_prs", [])):
                stale.append("Git delivery inventory changed")
            if not stale:
                classification, reason = a["classification"], a["reason"]
                wiring = str(a.get("production_wiring") or "n/a")
                verification = str(a.get("verification") or "n/a")
                if classification in ("implemented", "verified") and (not merged or wiring.lower().startswith(("n/a", "unknown")) or not a.get("tests")):
                    raise ValueError("implementation claim lacks Git, wiring or test evidence: " + uid)
                if classification == "verified" and verification.lower().startswith(("n/a", "unknown")):
                    raise ValueError("verification claim lacks acceptance comparison: " + uid)
            else:
                reason = "Assessment stale; fresh review required: " + ", ".join(sorted(set(stale)))
        item = {"id": uid, "title": c.get("title", r.get("title", uid)), "area": area,
                "roadmap_item": uid in canonical, "classification": classification,
                "assessment_current": bool(a) and not stale, "reason": reason,
                "canonical_status": c.get("status", "n/a"), "runtime_status": r.get("status", "n/a"),
                "git_status": "merged" if merged else "not found", "deliveries": delivery,
                "criteria": criteria, "gaps": gaps, "evidence": evidence,
                "runtime_acceptance": r.get("acceptance", []),
                "runtime_acceptance_source": "state/units.live.yaml (runtime snapshot; not canonical approval)",
                "production_wiring": a.get("production_wiring", "n/a") if a else "n/a",
                "tests": a.get("tests", []) if a else [],
                "verification": a.get("verification", "n/a") if a else "n/a"}
        items.append(item)
        if merged != (r.get("status") == "merged"):
            divergences.append({"id": uid, "git": item["git_status"], "runtime": item["runtime_status"]})
    # Platform obligations summarize approved scope; they are not extra units
    # and do not inflate the 56-card roadmap denominator.
    platform = []
    for p in catalog.get("platform", []):
        row = dict(p)
        stale = any(not safe_artifact(repo, e["path"]).is_file() or fingerprint(safe_artifact(repo, e["path"])) != e["fingerprint"] for e in p["evidence"])
        row["assessment_current"] = not stale
        if stale:
            row["classification"] = "designed"
            row["reason"] = "Source changed; platform assessment requires review."
        platform.append(row)
    counts = {area: {name: sum(i["area"] == area and i["classification"] == name and i["roadmap_item"] for i in items) for name in CLASSES} for area in AREAS}
    return {"schema_version": 1, "available": True,
            "generated_at": timestamp or datetime.now(timezone.utc).isoformat(),
            "assessment_date": catalog["assessment_date"],
            "scope_authority": "docs/decisions/2026-10-07-maintenance-B.md",
            "classes": list(CLASSES), "areas": list(AREAS), "counts_by_area": counts,
            "canonical_total": len(canonical), "runtime_total": len(runtime),
            "git_merged_units": sum(i["git_status"] == "merged" for i in items),
            "merged_scaffold_units": [i["id"] for i in items if i["git_status"] == "merged" and i["classification"] == "scaffold"],
            "units": items, "platform_obligations": platform,
            "divergences": divergences, "gaps": catalog["gaps"],
            "stand_ins": catalog["stand_ins"], "test_doubles": catalog["test_doubles"],
            "unscheduled_stand_ins": sum(not s["scheduled_replacement"] for s in catalog["stand_ins"]),
            "legacy_capture": catalog["legacy_capture"],
            "limitations": ["Classification is a reviewed snapshot, not inferred from merge count or coverage.",
                             "Implemented requires real backend wiring plus tests; verified also needs an acceptance-source comparison.",
                             "Platform summaries overlap units and are excluded from unit totals.",
                             "A citation proves provenance only; independent review checks expected behavior."]}


def delivery_map(repo, inventory, runtime, is_ancestor, catalog=None):
    """Use reviewed historical PR mappings plus exact current unit branches.
    Verify Git ancestry; never infer a product implementation from a PR title.
    """
    catalog = catalog or json.loads((repo / "ops/roadmap-assessment.json").read_text())
    historical = {u["id"]: set(u.get("assessed_prs", [])) for u in catalog["units"]}
    result = {uid: [] for uid in runtime}
    for pr in inventory:
        number = pr.get("number")
        branch = pr.get("headRefName", "")
        commit = (pr.get("mergeCommit") or {}).get("oid", "")
        ids = {uid for uid in result if number in historical.get(uid, set())}
        ids.update(uid for uid, u in runtime.items() if branch == "unit/" + uid or u.get("branch") == branch and bool(branch))
        if not ids:
            continue
        if not isinstance(number, int) or not commit or not is_ancestor(commit):
            raise ValueError("measurement delivery has no verified Git ancestry")
        for uid in ids:
            result[uid].append({"pr": number, "head": commit[:12], "merged_at": pr.get("mergedAt", "n/a"), "branch": branch})
    return result


def markdown(report: dict) -> str:
    lines = ["# Progress against the approved roadmap", "", f"Snapshot: {report['generated_at']}.", "",
             "Git delivery and runtime status are reported separately from implementation. Product scaffolds remain scaffolds even when their synthetic acceptance tests pass. Infrastructure utility completion does not count as a completed product feature.", "",
             "Counts include canonical roadmap cards only. Split, quality and refactor units appear below but do not inflate the roadmap denominator. Platform obligations are overlapping summaries, not additional cards.", "",
             "| Area | Not started | Designed | Scaffold | Implemented | Verified |", "|---|---:|---:|---:|---:|---:|"]
    for area, counts in report["counts_by_area"].items():
        lines.append("| " + area + " | " + " | ".join(str(counts[name]) for name in CLASSES) + " |")
    lines += ["", "## Approved platform obligations", "", "| Area | Classification | Written authority | Observed boundary |", "|---|---|---|---|"]
    for p in report["platform_obligations"]:
        lines.append(f"| {p['area']} | {p['classification']} | {p['source']} | {p['reason']} |")
    lines += ["", "## Unit delivery and assessment", "", "| Unit | Area | Canonical / runtime / Git | Classification | Evidence / limitation |", "|---|---|---|---|---|"]
    for i in report["units"]:
        refs = ", ".join(f"`{e['path']}:{e['line']}`" for e in i["evidence"])
        lines.append(f"| {i['id']} | {i['area']} | {i['canonical_status']} / {i['runtime_status']} / {i['git_status']} | {i['classification']} | {i['reason']} {refs} |")
    lines += ["", "## Acceptance criteria as written", ""]
    for i in report["units"]:
        lines += [f"### {i['id']}", ""]
        for source in i["criteria"]:
            lines += [f"Source: `{source['path']}:{source['line']}` ({source['kind']}).", "", "> " + source["quote"].replace("\n", "\n> "), ""]
        for gap in i["gaps"]:
            lines += ["Gap: " + gap, ""]
        if i["runtime_acceptance"] and not any(c["kind"] == "canonical acceptance" for c in i["criteria"]):
            lines += ["Runtime-promoted criteria, preserved separately from canonical authority:", ""]
            lines.extend("> " + text for text in i["runtime_acceptance"])
            lines.append("")
    lines += ["## Product stand-ins", "", "| Stand-in | Location | Real replacement written? | Existing roadmap authority |", "|---|---|---|---|"]
    for s in report["stand_ins"]:
        lines.append(f"| {s['symbol']} | `{s['path']}:{s['line']}` | {'yes' if s['scheduled_replacement'] else 'no'} | {s['authority']} |")
    lines += ["", "Legitimate test-local doubles are listed separately in progress.json. They are not unscheduled product replacements.", "",
              "## Gaps and capture status", ""]
    lines.extend("- " + g for g in report["gaps"])
    lines += ["", report["legacy_capture"]["reason"], "",
              f"Git/runtime divergences: {', '.join(d['id'] for d in report['divergences']) or 'none'}. Git-merged scaffold units: {len(report['merged_scaffold_units'])}. Stand-ins without a scheduled replacement: {report['unscheduled_stand_ins']}.", ""]
    return "\n".join(lines)


def publish(repo, canonical, runtime, deliveries, target, atomic_json):
    """A measurement failure emits unavailable data; never changes scheduling."""
    try:
        report = build(repo, canonical, runtime, deliveries)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report = {"schema_version": 1, "available": False,
                  "generated_at": datetime.now(timezone.utc).isoformat(),
                  "reason": "roadmap measurement unavailable: " + type(exc).__name__}
    atomic_json(target, report)
    return report

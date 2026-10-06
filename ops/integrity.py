"""Control-boundary validation; no workers, network, or live paths at import."""
from __future__ import annotations

import copy
import json
import os
import re
import tempfile
import uuid
from pathlib import Path, PurePosixPath


class IntegrityError(RuntimeError):
    pass


def identity() -> str:
    return str(uuid.uuid4())


def nonnegative(value, name="counter") -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise IntegrityError(f"invalid {name}")
    return value


def atomic_text(path: Path, text: str, validate=None) -> None:
    """Validate before replacing; fsync both the new file and its directory."""
    if validate:
        validate(text)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as fh:
            os.fchmod(fh.fileno(), 0o600)
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, data) -> None:
    atomic_text(path, json.dumps(data, indent=1, sort_keys=True) + "\n", json.loads)


def append_record(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(record, sort_keys=True) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        # One writer owns the orchestration lock; detect short writes.
        if os.write(fd, line) != len(line):
            raise IntegrityError("short ledger write")
        os.fsync(fd)
    finally:
        os.close(fd)


def ledger_records(state_dir: Path) -> list[dict]:
    rows = []
    paths = sorted(state_dir.glob("runs-*.jsonl"))
    if (state_dir / "runs.jsonl").exists():
        paths.append(state_dir / "runs.jsonl")
    for path in paths:
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError as exc:
                raise IntegrityError(f"invalid ledger {path.name}:{number}") from exc
            if not isinstance(row, dict):
                raise IntegrityError(f"invalid ledger {path.name}:{number}")
            rows.append(row)
    return rows


def charged_tokens(row: dict, fallback: int) -> int:
    if "charged_tokens" in row:
        return nonnegative(row["charged_tokens"], "ledger charge")
    usage = row.get("usage") or {}
    aux = usage.get("total_including_auxiliary")
    total = aux.get("total_tokens") if isinstance(aux, dict) else aux
    if total is None:
        total = usage.get("total_tokens")
    if total is not None:
        return nonnegative(total, "usage total")
    parts = [row.get(k) for k in ("input_tokens", "output_tokens")]
    if all(v is not None for v in parts):
        return sum(nonnegative(v, "usage part") for v in parts)
    return nonnegative(row.get("tokens_pessimistic", fallback), "unknown usage")


def accounting(rows: list[dict], day: str, fallback: int) -> dict:
    """Recovery uses only the append-only ledger, never guessed free runs."""
    tokens, merged, per_unit, audit = 0, set(), {}, 0
    attempts = {}
    reservations, finished, records, latest = {}, set(), set(), {}
    for i, row in enumerate(rows):
        kind = row.get("record_type", "run")
        rid = row.get("run_id")
        if kind == "reservation":
            if not rid or rid in reservations:
                raise IntegrityError("duplicate/absent reservation identity")
            reservations[rid] = row
            continue
        if kind == "outcome":
            continue
        if kind == "baseline":
            if row.get("day") == day:
                tokens += nonnegative(row["tokens_today"], "baseline tokens")
                for n in range(nonnegative(row["merged_today"], "baseline merges")):
                    merged.add(("baseline", i, n))
            for uid, value in row.get("unit_tokens", {}).items():
                per_unit[uid] = per_unit.get(uid, 0) + nonnegative(value)
            attempts.update({uid: nonnegative(value) for uid, value in row.get("unit_attempts", {}).items()})
            continue
        if kind == "delivery":
            if row.get("count_merge", True) and row.get("merged_at", "")[:10] == day:
                merged.add(("delivery", row["pr"]))
            continue
        if kind != "run":
            raise IntegrityError("unknown ledger record type")
        if rid:
            if rid in records:
                raise IntegrityError("duplicate run identity")
            records.add(rid)
            finished.add(rid)
        ts = row.get("ts_end") or row.get("ts_start")
        if not isinstance(ts, str) or not re.match(r"^\d{4}-\d{2}-\d{2}T", ts):
            raise IntegrityError("undated accounting record")
        charge = charged_tokens(row, fallback)
        uid = row.get("unit") or ""
        if uid:
            per_unit[uid] = per_unit.get(uid, 0) + charge
        if rid and row.get("role") == "builder" and row.get("outcome") != "provider_error" and row.get("rc") != 127:
            attempts[uid] = attempts.get(uid, 0) + 1
        if ts[:10] == day:
            tokens += charge
        if row.get("role") == "audit":
            audit = charge
        # New merges have a durable delivery receipt. Legacy run outcomes have
        # no PR; use their run identity rather than pretending repeated PRs equal.
        if row.get("outcome") == "merged" and not rid and ts[:10] == day:
            merged.add(("legacy", row.get("unit"), row.get("attempt"), ts))
        latest[rid or str(i)] = row
    pending = {rid: r for rid, r in reservations.items() if rid not in finished}
    for r in pending.values():
        charge = nonnegative(r["reserved_tokens"], "unsettled reservation")
        uid = r.get("unit") or ""
        if uid:
            per_unit[uid] = per_unit.get(uid, 0) + charge
        if (r.get("ts_start") or "")[:10] == day:
            tokens += charge
    return {"tokens_today": tokens, "merged_today": len(merged),
            "unit_tokens": per_unit, "unit_attempts": attempts,
            "unsettled": pending, "audit_tokens": audit}


def validate_state(st) -> dict:
    if not isinstance(st, dict) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(st.get("day", ""))):
        raise IntegrityError("invalid accounting state")
    for key in ("tokens_today", "merged_today"):
        nonnegative(st.get(key), key)
    if not isinstance(st.get("events", []), list) or not isinstance(st.get("reservations", {}), dict):
        raise IntegrityError("invalid state collections")
    for rec in st.get("reservations", {}).values():
        nonnegative(rec.get("reserved_tokens"), "reservation")
    return st


def provider_error(rc: int, output: str) -> bool:
    """Infrastructure status, not an ordinary compilation/tool error."""
    if rc in (402, 403, 429) or 500 <= rc <= 599:
        return True
    text = output.lower()
    return bool(re.search(r"(?:http(?:error)?|status(?:[_ ]code)?|error(?:[_ ]code)?|response|provider|api)[^\n]{0,55}\b(?:402|403|429|5\d\d)\b", text)
                or re.search(r"\b(?:402|403|429|5\d\d)\b[^\n]{0,40}(?:payment required|forbidden|rate.limit|gateway|server error|overload)", text)
                or any(s in text for s in ("gateway timeout", "bad gateway", "payment required", "insufficient balance", "rate limit exceeded", "provider unavailable")))


def model_family(model: str) -> str:
    if "deepseek" in model.lower():
        return "deepseek"
    if "claude" in model.lower():
        return "claude"
    if "gpt" in model.lower():
        return "gpt"
    return model.lower()


def review_result(rc: int, output: str) -> tuple[str, str]:
    if rc != 0:
        return "unavailable", f"reviewer exited rc={rc}"
    decoder, objects = json.JSONDecoder(), []
    position = 0
    while position < len(output):
        start = output.find("{", position)
        if start < 0:
            break
        try:
            data, length = decoder.raw_decode(output[start:])
        except ValueError:
            position = start + 1
            continue
        position = start + length
        if isinstance(data, dict) and "verdict" in data:
            objects.append(data)
    if len(objects) != 1:
        return "unavailable", "missing/ambiguous JSON review"
    data = objects[0]
    if data.get("verdict") not in ("pass", "fix", "block") or not isinstance(data.get("findings"), list):
        return "unavailable", "malformed review schema"
    blockers = []
    for f in data["findings"]:
        if (not isinstance(f, dict) or f.get("severity") not in ("blocker", "minor")
                or not isinstance(f.get("file"), str) or not isinstance(f.get("issue"), str)
                or not isinstance(f.get("line"), int) or isinstance(f.get("line"), bool)
                or f["line"] < 0):
            return "unavailable", "malformed review finding"
        if f["severity"] == "blocker":
            blockers.append(f"- {f['file']}:{f['line']} {f['issue']}")
    verdict = data["verdict"]
    if blockers and verdict == "pass":
        verdict = "fix"
    reason = "\n".join(blockers)
    if verdict != "pass" and not reason:
        reason = f"reviewer verdict {verdict} (no findings supplied)"
    return verdict, reason


def safe_path(path, protected: tuple[str, ...]) -> bool:
    if not isinstance(path, str) or not path or "\\" in path or ":" in path:
        return False
    parts = path.split("/")
    if path.startswith("/") or any(p in ("", ".", "..") for p in parts):
        return False
    stem = path.split("*", 1)[0].split("?", 1)[0].split("[", 1)[0].rstrip("/")
    if not stem:
        return False
    return not any(stem == p.rstrip("/") or stem.startswith(p.rstrip("/") + "/")
                   or p.rstrip("/").startswith(stem + "/") for p in protected)


def validate_plan(entries, roadmap, parent, old_id, mode, protected, split_cap):
    if not isinstance(entries, list) or not entries:
        raise IntegrityError("empty plan")
    if mode == "split" and len(entries) > split_cap:
        raise IntegrityError("split cap")
    staged = copy.deepcopy(entries)
    ids = []
    runtime = ("attempts", "tokens", "pr", "review_rounds", "conflict_rounds", "planner_retries")
    for e in staged:
        uid = e.get("id") if isinstance(e, dict) else None
        if not isinstance(uid, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", uid):
            raise IntegrityError("invalid unit id")
        if uid in roadmap or uid in ids:
            raise IntegrityError("unit id collision: " + uid)
        ids.append(uid)
        if not isinstance(e.get("title"), str) or not e["title"].strip():
            raise IntegrityError("missing title")
        if e.get("status", "todo") != "todo" or e.get("size") not in ("S", "M"):
            raise IntegrityError("invalid status/size")
        forbidden = ("review_head", "review_id", "review_verdict", "review_model", "review2_head", "review2_id", "review2_verdict", "review2_model",
                     "run_id", "revision_id", "delivery_commit", "split_requested", "model_override", "provider_retry_at")
        if any(k in e for k in forbidden) or any(e.get(k, 0) != 0 for k in runtime) or e.get("branch") or e.get("model"):
            raise IntegrityError("planner supplied runtime identity")
        if not isinstance(e.get("paths"), list) or not 1 <= len(e["paths"]) <= 8:
            raise IntegrityError("invalid paths")
        if any(not safe_path(p, protected) for p in e["paths"]):
            raise IntegrityError("protected/escaping path")
        for key in ("depends_on", "acceptance", "tests", "fixtures"):
            values = e.get(key, [])
            if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values):
                raise IntegrityError("invalid list: " + key)
        if len(e.get("acceptance", [])) > 5:
            raise IntegrityError("acceptance cap")
        if mode in ("split", "rewrite") and parent.get("paths"):
            allowed = [p.rstrip("*").rstrip("/") for p in parent["paths"]]
            for p in e["paths"]:
                if p == f"docs/units/{uid}.md":
                    continue
                if not any(p == a or p.startswith(a + "/") for a in allowed):
                    raise IntegrityError("replacement escapes parent scope")
        e.setdefault("depends_on", [])
    for index, e in enumerate(staged):
        if old_id and old_id in e["depends_on"]:
            replacement = parent.get("depends_on", []) if index == 0 else [ids[0]]
            e["depends_on"] = list(dict.fromkeys([d for d in e["depends_on"] if d != old_id] + replacement))
        e["revision_id"] = identity()
        e["paths"] = list(dict.fromkeys(e["paths"] + [f"docs/units/{e['id']}.md"]))
    candidate = copy.deepcopy(roadmap)
    candidate.update({e["id"]: e for e in staged})
    # Existing undelivered consumers must wait for every replacement, not a
    # parked parent or just the first slice. Delivered history is unchanged.
    if old_id:
        for uid, e in candidate.items():
            if uid not in ids and uid != old_id and e.get("status") != "merged" and old_id in e.get("depends_on", []):
                e["depends_on"] = list(dict.fromkeys([d for d in e["depends_on"] if d != old_id] + ids))
    visiting, visited = set(), set()
    def visit(uid):
        if uid in visiting:
            raise IntegrityError("dependency cycle: " + uid)
        if uid in visited:
            return
        visiting.add(uid)
        deps = candidate[uid].get("depends_on", [])
        if not isinstance(deps, list):
            raise IntegrityError("invalid dependencies")
        for dep in deps:
            if dep == uid or dep not in candidate:
                raise IntegrityError("self/unknown dependency: " + str(dep))
            visit(dep)
        visiting.remove(uid)
        visited.add(uid)
    for uid in candidate:
        visit(uid)
    return candidate, ids

"""Deterministic migration policy. No credentials, inference or approval gates."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import integrity as control

ROOT = Path(__file__).resolve().parent
OPS = Path(os.environ.get("PHPRETRO_OPS", Path.home() / "phpretro-ops"))
DEFAULT = ROOT / "openhands" / "policy.json"
POLICY = Path(os.environ.get("PHPRETRO_RUNTIME_POLICY", DEFAULT))


def load():
    data = json.loads(POLICY.read_text())
    if data.get("schema") != "phpretro.runtime.v1":
        raise control.IntegrityError("unsupported runtime policy")
    if data.get("automatic_planning") is not False or data.get("automatic_sol") is not False:
        raise control.IntegrityError("paid planning/automatic Sol are forbidden")
    if data.get("max_builders") != 2:
        raise control.IntegrityError("migration requires the reviewed two-builder ceiling")
    return data


def fingerprint():
    paths = sorted(path for path in ROOT.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    paths.append(ROOT.parent / "scripts" / "check.sh")
    paths.append(ROOT.parent / ".go-version")
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(ROOT.parent)).encode())
        digest.update(path.read_bytes())
    if POLICY != DEFAULT:
        digest.update(POLICY.read_bytes())
    return digest.hexdigest()


def capability_fingerprint():
    digest = hashlib.sha256()
    for name in ("runner.py", "probe_models.py", "requirements.lock"):
        digest.update((ROOT / "openhands" / name).read_bytes())
    digest.update(POLICY.read_bytes())
    return digest.hexdigest()


def ready(model=None):
    data = load()
    stamp = OPS / "state" / "openhands-validation.json"
    try:
        checked = json.loads(stamp.read_text())
    except (OSError, ValueError):
        return False
    if checked.get("implementation_sha256") != fingerprint() or checked.get("passed") is not True:
        return False
    required = ("foundation", "ops", "frontend", "isolation", "lifecycle", "resources", "provider")
    if not all(checked.get("checks", {}).get(k) is True for k in required):
        return False
    # A mutable Docker tag or stale vulnerability snapshot invalidates admission.
    if time.time() - checked.get("validated_at", 0) > 48 * 3600:
        return False
    if time.time() - checked.get("vulnerability_snapshot_at", 0) > 48 * 3600:
        return False
    try:
        image = subprocess.check_output(["docker", "image", "inspect", "--format={{.Id}}", data["image"]],
                                        text=True, stderr=subprocess.DEVNULL, timeout=10).strip()
    except (OSError, subprocess.SubprocessError):
        return False
    if not image or image != checked.get("image_id"):
        return False
    if model is not None:
        capability = checked.get("models", {}).get(model, {})
        if capability.get("tool_calls") is not True or capability.get("usage") is not True:
            return False
    return True


def model_settings(model):
    settings = load()["models"].get(model)
    if not settings or settings.get("automatic") is not True:
        raise control.IntegrityError("model is outside the automatic coding/review policy")
    return settings


def planning_needed(unit, reason):
    uid = unit.get("id", "nightly")
    if not isinstance(uid, str) or not __import__("re").fullmatch(r"[A-Za-z0-9_-]{1,80}", uid):
        raise control.IntegrityError("invalid planning handoff identity")
    destination = OPS / "state" / "planning-needed" / (uid + ".json")
    record = {"schema": "phpretro.planning-needed.v1", "unit": uid,
              "reason": str(reason)[:2000], "status": "awaiting-subscription-brief",
              "attempts": unit.get("attempts", 0), "tokens": unit.get("tokens", 0),
              "paths": unit.get("paths", []), "depends_on": unit.get("depends_on", [])}
    if destination.exists() and json.loads(destination.read_text()) == record:
        return False
    control.atomic_json(destination, record)
    return True

"""Deterministic migration policy. No credentials, inference or approval gates."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import integrity as control
import canary

ROOT = Path(__file__).resolve().parent
OPS = Path(os.environ.get("PHPRETRO_OPS", Path.home() / "phpretro-ops"))
DEFAULT = ROOT / ("claude_code" if os.environ.get("PHPRETRO_RUNTIME") == "claude-code" else "openhands") / "policy.json"
POLICY = Path(os.environ.get("PHPRETRO_RUNTIME_POLICY", DEFAULT))


def load():
    data = json.loads(POLICY.read_text())
    if data.get("schema") == "phpretro.claude-code-policy.v1":
        from claude_code import policy
        return policy.load(POLICY)
    if data.get("schema") != "phpretro.runtime.v1":
        raise control.IntegrityError("unsupported runtime policy")
    if data.get("automatic_planning") is not False:
        raise control.IntegrityError("paid planning is forbidden")
    sol_enabled = data.get("models", {}).get("gpt-6.1-sol", {}).get("automatic") is True
    if data.get("automatic_sol") is not sol_enabled:
        raise control.IntegrityError("Sol automation flag and model policy disagree")
    if data.get("max_builders") != 2:
        raise control.IntegrityError("migration requires the reviewed two-builder ceiling")
    families = data.get("required_review_families")
    if type(families) is not int or families not in (2, 3):
        raise control.IntegrityError("review requires two or three independent families")
    if families == 2 and data.get("review_policy") != "temporary-two-family-user-override":
        raise control.IntegrityError("two-family review requires the explicit temporary policy")
    if data.get("providers") != {"a6api": {"base_url": "https://api.a6api.com/v1"},
                                 "portdan": {"base_url": "https://portdan.com/v1"}}:
        raise control.IntegrityError("unexpected provider endpoint")
    for settings in data["models"].values():
        if settings.get("automatic") and settings.get("provider_order") != ["a6api", "portdan"]:
            raise control.IntegrityError("provider order must be A6API then Portdan")
    return data


def review_families_available():
    policy = load()
    families = {control.model_family(m) for m, v in policy["models"].items()
                if v.get("automatic") is True}
    return len(families) >= policy["required_review_families"]


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
    digest.update((ROOT / 'canary.py').read_bytes())
    digest.update((ROOT / 'request_accounting.py').read_bytes())
    for name in ("runner.py", "probe_models.py", "routing.py", "requirements.lock"):
        digest.update((ROOT / "openhands" / name).read_bytes())
    digest.update(Path(__file__).read_bytes())
    digest.update(POLICY.read_bytes())
    return digest.hexdigest()


def ready(model=None):
    data = load()
    if data.get("runtime") == "claude-code":
        from claude_code import policy
        return policy.ready(data, OPS, fingerprint(), model)
    if model is not None and data["models"].get(model, {}).get("automatic") is not True:
        return False
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
        if not verified_providers(model, checked):
            return False
    return True


def route_passed(row):
    return (row.get("tool_calls") is True and row.get("usage") is True
            and 0 <= time.time() - row.get("checked_at", 0) <= 86400)


def verified_providers(model, checked=None):
    if checked is None:
        try:
            checked = json.loads((OPS / "state" / ("claude-code-validation.json" if load().get("runtime")=="claude-code" else "openhands-validation.json")).read_text())
        except (OSError, ValueError):
            return []
    evidence = checked.get("provider_models", {})
    if load().get('runtime')=='claude-code' and not evidence:
        # Retained route observations admit upstream endpoints, not the new
        # CLI bridge. New native validation is still independently mandatory.
        try:evidence=json.loads((OPS/'state/openhands-validation.json').read_text()).get('provider_models',{})
        except (OSError,ValueError):evidence={}
    return [p for p in model_settings(model)["provider_order"]
            if route_passed(evidence.get(p, {}).get(model, {})) or canary.operator_route(p, model)]


def model_settings(model):
    settings = load()["models"].get(model)
    if not settings or settings.get("automatic") is not True:
        raise control.IntegrityError("model is outside the automatic coding/review policy")
    return settings


def sdk_model(model):
    model_settings(model)
    # Native DeepSeek preserves reasoning_content across tool turns.
    return ("deepseek/" if model.startswith("deepseek-") else "openai/") + model


def model_label_matches(model, reported):
    label = str(reported).removeprefix("openai/").removeprefix("deepseek/")
    return label in [model, *model_settings(model).get("reported_model_aliases", [])]


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

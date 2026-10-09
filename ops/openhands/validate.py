#!/usr/bin/env python3
"""Run migration acceptance checks under STOP; stamp only exact passing source."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import integrity as control
import runtime_policy
import sandbox

ROOT = Path(__file__).resolve().parents[2]
OPS = runtime_policy.OPS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider-evidence", type=Path, required=True)
    args = ap.parse_args()
    if not (OPS / "STOP").is_file():
        raise control.IntegrityError("validation requires STOP")
    fingerprint = runtime_policy.fingerprint()
    evidence = json.loads(args.provider_evidence.read_text())
    provider_current = (evidence.get("capability_sha256") == runtime_policy.capability_fingerprint()
                        and 0 <= time.time() - evidence.get("completed_at", 0) <= 86400)
    policy = runtime_policy.load()
    models = evidence.get("models", {})
    provider_models = evidence.get("provider_models", {})
    models = {m: {"tool_calls": bool(runtime_policy.verified_providers(m, evidence)),
                  "usage": bool(runtime_policy.verified_providers(m, evidence))}
              for m, v in policy["models"].items() if v.get("automatic")}
    checks = {"provider": runtime_policy.review_families_available() and provider_current
              and all(row["tool_calls"] and row["usage"] for row in models.values())}
    logdir = OPS / "logs" / "openhands-validation"
    logdir.mkdir(parents=True, exist_ok=True)
    run = subprocess.run(["bash", "ops/tests/run_all.sh"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (logdir / "ops.log").write_bytes(run.stdout)
    checks["ops"] = run.returncode == 0
    rc, output = sandbox.check(ROOT)
    (logdir / "foundation.log").write_text(output)
    checks["foundation"] = rc == 0
    box = sandbox.Sandbox(control.identity(), ROOT, writable=True)
    try:
        box.prepare()
        observed = sandbox.inspect(box.rid)
        config, host = observed["Config"], observed["HostConfig"]
        checks["isolation"] = (config["User"] == "65532:65532" and host["NetworkMode"] == "none"
                               and host["ReadonlyRootfs"] is True and host["CapDrop"] == ["ALL"]
                               and "no-new-privileges" in host["SecurityOpt"]
                               and len([m for m in observed["Mounts"] if m["Type"] == "bind"]) == 1
                               and any(m["Type"] == "bind" and m["Source"] == str(box.stage) and m["Destination"] == "/repo" for m in observed["Mounts"])
                               and all(m["Destination"] in ("/repo", "/tmp", "/home/worker") for m in observed["Mounts"]))
        checks["resources"] = (host["Memory"] > 0 and host["PidsLimit"] == policy["container_pids"]
                               and host["CgroupParent"] == policy["cgroup_parent"])
        oldpid = observed["State"]["Pid"]
        rc, output = box.execute("sleep 60 >/tmp/background.log 2>&1 & printf '%s\\n' started", 10)
        checks["lifecycle"] = rc == 0 and sandbox.inspect(box.rid)["State"]["Pid"] != oldpid
        rc, output = box.execute("python3 -c 'import sys; sys.stdout.write(\"x\" * (5 * 1024 * 1024))'", 10)
        checks["lifecycle"] = checks["lifecycle"] and rc == 124 and len(output.encode()) <= 65536
        rc, output = box.execute("test ! -e /home/ubuntu/phpretro-openhands/secrets/providers.json && test ! -S /var/run/docker.sock && test ! -e /home/ubuntu/.hermes", 10)
        checks["isolation"] = checks["isolation"] and rc == 0
        rc, output = box.execute("cat /opt/vulndb/fetched-at", 10)
        snapshot_at = int(output.strip()) if rc == 0 else 0
        checks["resources"] = checks["resources"] and 0 <= time.time() - snapshot_at < 172800
        rc, output = box.execute("cd frontend && npm run typecheck && npm test && npm run build", 1800)
        (logdir / "frontend.log").write_text(output)
        checks["frontend"] = rc == 0
    finally:
        box.close()
    sandbox.assert_absent(box.rid)
    if fingerprint != runtime_policy.fingerprint():
        raise control.IntegrityError("source changed during validation")
    image = sandbox.docker("image", "inspect", "--format={{.Id}}", policy["image"]).decode().strip()
    result = {"schema": "phpretro.validation.v1", "implementation_sha256": fingerprint,
              "validated_at": time.time(), "image_id": image, "models": models, "provider_models": provider_models,
              "provider_evidence_current": provider_current,
              "vulnerability_snapshot_at": snapshot_at,
              "checks": checks, "passed": all(checks.values())}
    control.atomic_json(OPS / "state" / "openhands-validation.json", result)
    print(json.dumps(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Install reviewed source/config while retaining STOP and disabled timers."""
from __future__ import annotations
import json
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import integrity as control
import runtime_policy
import worker

ROOT = Path(__file__).resolve().parents[2]
OPS = runtime_policy.OPS
TIMERS = ("phpretro-orchestrator.timer", "phpretro-nightly.timer", "phpretro-alerts.timer")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resources-only", action="store_true")
    args = ap.parse_args()
    if not (OPS / "STOP").is_file():
        raise control.IntegrityError("STOP required; installer never activates dispatch")
    if args.resources_only:
        subprocess.run(["sudo", "-n", "install", "-m", "644", str(ROOT / "ops/systemd/phpretro-build.slice"), "/etc/systemd/system/phpretro-build.slice"], check=True)
        user_units = Path.home() / ".config/systemd/user"
        user_units.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "ops/systemd/phpretro-inference.slice", user_units / "phpretro-inference.slice")
        subprocess.run(["sudo", "-n", "systemctl", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "daemon-reload"], env=worker.bus_env(), check=True)
        subprocess.run(["sudo", "-n", "systemctl", "start", "phpretro-build.slice"], check=True)
        print("Resource slices installed; pipeline and dashboard remain stopped/unchanged")
        return
    head = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    main_head = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "origin/main"], text=True).strip()
    if head != main_head:
        raise control.IntegrityError("full installation requires reviewed source on origin/main")
    state = json.loads((OPS / "state" / "units.state.json").read_text())
    if state.get("reservations"):
        raise control.IntegrityError("settle existing reservations first")
    for path in (OPS / "state" / "receipts").glob("*.json"):
        if path.name.count(".") != 1:
            continue
        rec = json.loads(path.read_text())
        if rec.get("status") == "running" or worker.alive(rec.get("worker_pid"), rec.get("worker_identity")):
            raise control.IntegrityError("existing workers must be drained before installation")
    # Source backup only. Provider files and interactive profiles are never copied.
    backup = OPS / "backups" / ("openhands-source-" + str(int(time.time())))
    backup.mkdir(parents=True, mode=0o700)
    dashboard = Path.home() / "phpretro-dashboard"
    for name in ("server.py", "gateway.py", "index.html"):
        if (dashboard / name).exists():
            shutil.copy2(dashboard / name, backup / name)
    for timer in TIMERS:
        subprocess.run(["sudo", "-n", "systemctl", "disable", "--now", timer], check=True)
    for name in ("phpretro-orchestrator.service", "phpretro-nightly.service", "phpretro-alerts.service"):
        observed = subprocess.check_output(["systemctl", "show", name, "--property=ActiveState", "--value"], text=True).strip()
        if observed not in ("inactive", "failed"):
            raise control.IntegrityError("pipeline services must already be stopped")
        text = (ROOT / "ops" / "systemd" / name).read_text().replace("/home/ubuntu/phpretro-preservation", str(ROOT))
        saved = backup / name
        existing = Path("/etc/systemd/system") / name
        if existing.is_file():
            shutil.copy2(existing, backup / (name + ".previous"))
        saved.write_text(text)
        subprocess.run(["sudo", "-n", "install", "-m", "644", str(saved), str(existing)], check=True)
    subprocess.run(["sudo", "-n", "install", "-m", "644", str(ROOT / "ops/systemd/phpretro-build.slice"), "/etc/systemd/system/phpretro-build.slice"], check=True)
    user_units = Path.home() / ".config/systemd/user"
    user_units.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "ops/systemd/phpretro-inference.slice", user_units / "phpretro-inference.slice")
    for name in ("server.py", "gateway.py", "index.html"):
        shutil.copy2(ROOT / "ops/dashboard" / name, dashboard / name)
    subprocess.run(["sudo", "-n", "systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], env=worker.bus_env(), check=True)
    subprocess.run(["sudo", "-n", "systemctl", "start", "phpretro-build.slice"], check=True)
    control.atomic_json(OPS / "state" / "openhands-install.json", {"source": str(ROOT), "backup": str(backup), "paused": True})
    print("Installed paused; no timers or workers started. Backup: " + str(backup))


if __name__ == "__main__":
    main()

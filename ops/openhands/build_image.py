#!/usr/bin/env python3
"""Build the credential-free worker image inside the actual bounded slice."""
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrity as control
import runtime_policy
import sandbox

def main():
    if not (runtime_policy.OPS / "STOP").is_file():
        raise control.IntegrityError("image preparation requires STOP")
    policy = runtime_policy.load()
    group = subprocess.check_output(["systemctl","show",policy["cgroup_parent"],"--property=ControlGroup","--value"],text=True).strip()
    if not group.startswith("/") or group == "/":
        raise control.IntegrityError("install resource slices first")
    with sandbox.heavy_lane():
        subprocess.run(["docker","buildx","build","--cgroup-parent="+group,
                        "--resource","memory=1400m","--resource","cpu-quota=150000","--resource","cpu-period=100000",
                        "-f","ops/openhands/Dockerfile","-t",policy["image"],"--load","."],
                       cwd=Path(__file__).resolve().parents[2],check=True)
if __name__ == "__main__": main()

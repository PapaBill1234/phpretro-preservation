#!/usr/bin/env python3
"""Install the isolated interactive UI; never activate the coding controller."""
import argparse
import json
from pathlib import Path
import subprocess
import time

NAME = 'phpretro-openhands-ui'
IMAGE = 'ghcr.io/openhands/agent-canvas@sha256:ce4526401c08b47d74fd0be5ebf97e8219d6a02955cb6710e8cc3335f01291a6'
VOLUMES = {
    '/home/openhands/.openhands': 'phpretro-openhands-ui-state',
    '/projects': 'phpretro-openhands-ui-projects',
}


def check_existing(container):
    host = container['HostConfig']
    mounts = {m['Destination']: m['Name'] for m in container['Mounts'] if m['Type'] == 'volume'}
    expected_ports = {'8000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '38082'}]}
    expected_env = {'AGENT_CANVAS_ALLOW_LAN_SESSION_KEY=true', 'AGENT_CANVAS_DISABLE_TELEMETRY=1', 'OH_TELEMETRY_EXPORTER=none'}
    return (container['Image'] == IMAGE.split('@')[1]
            and host['PortBindings'] == expected_ports
            and mounts == VOLUMES and len(container['Mounts']) == len(VOLUMES)
            and host['Memory'] == 1600 * 1024 * 1024
            and host['NanoCpus'] == 1000000000 and host['PidsLimit'] == 256
            and host['CapDrop'] == ['ALL'] and not host['Privileged']
            and 'no-new-privileges' in host['SecurityOpt']
            and host['RestartPolicy']['Name'] == 'unless-stopped'
            and expected_env <= set(container['Config']['Env']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    root = Path.home() / 'phpretro-openhands'
    if not (Path.home() / 'phpretro-ops/STOP').is_file():
        raise SystemExit('STOP required; installer never changes dispatch state')
    found = subprocess.run(['docker', 'container', 'inspect', NAME], capture_output=True, text=True)
    if found.returncode == 0:
        container = json.loads(found.stdout)[0]
        if not check_existing(container):
            raise SystemExit('Existing UI differs from pinned isolation settings; preserve it and review manually')
        if not container['State']['Running']:
            subprocess.run(['docker', 'start', NAME], check=True, stdout=subprocess.DEVNULL)
        action = 'adopted'
    else:
        subprocess.run(['docker', 'info'], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(['docker', 'pull', IMAGE], check=True)
        command = ['docker', 'run', '-d', '--name', NAME, '--restart', 'unless-stopped',
                   '--cpus', '1', '--memory', '1600m', '--pids-limit', '256',
                   '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                   '-p', '127.0.0.1:38082:8000']
        for setting in ('AGENT_CANVAS_ALLOW_LAN_SESSION_KEY=true', 'AGENT_CANVAS_DISABLE_TELEMETRY=1', 'OH_TELEMETRY_EXPORTER=none'):
            command += ['-e', setting]
        for destination, volume in VOLUMES.items():
            command += ['-v', volume + ':' + destination]
        subprocess.run(command + [IMAGE], check=True, stdout=subprocess.DEVNULL)
        action = 'created'
    root.mkdir(parents=True, exist_ok=True)
    report = {'installed_at': time.time(), 'container': NAME, 'image': IMAGE,
              'action': action, 'loopback_port': 38082, 'volumes': VOLUMES,
              'controller': 'paused', 'provider_probes': 0}
    (root / 'webui-installation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Install the native supervisor without enabling its timer or repairing work."""
import json, os, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import codex_account as account
import codex_supervisor as supervisor
import worker

def main():
    os.umask(0o077)
    repo=ROOT.parent
    assert (supervisor.OPS/'STOP').is_file(), 'paused installation requires STOP'
    assert not supervisor.ENABLED.exists(), 'disable supervisor before reinstalling'
    assert not supervisor.load(supervisor.OPS/'state/units.state.json').get('reservations'), 'workers must be settled'
    head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    main_head=subprocess.check_output(['git','-C',str(repo),'rev-parse','origin/main'],text=True).strip()
    assert head==main_head, 'reviewed source on main required'
    assert subprocess.check_output([str(account.CLI),'--version'],text=True).strip()==supervisor.VERSION
    account.AUTH.mkdir(parents=True,mode=0o700,exist_ok=True)
    (account.BASE/'work').mkdir(mode=0o700,exist_ok=True)
    units=Path.home()/'.config/systemd/user'; units.mkdir(parents=True,exist_ok=True)
    for name in ('phpretro-codex-supervisor.service','phpretro-codex-supervisor.timer'):
        shutil.copy2(ROOT/'systemd'/name,units/name)
    binary=Path.home()/'.local/bin/codex'; binary.parent.mkdir(parents=True,exist_ok=True)
    if binary.exists() and binary.read_bytes()!=(ROOT/'codex/launch.sh').read_bytes():
        raise RuntimeError('existing codex launcher is not supervisor-owned')
    shutil.copy2(ROOT/'codex/launch.sh',binary); binary.chmod(0o700)
    subprocess.run(['systemctl','--user','daemon-reload'],env=worker.bus_env(),check=True)
    subprocess.run(['systemctl','--user','disable','--now','phpretro-codex-supervisor.timer'],env=worker.bus_env(),check=True)
    subprocess.run(['systemctl','--user','stop','phpretro-codex-supervisor.service'],env=worker.bus_env(),check=True)
    supervisor.cycle(inspect=True)
    print(json.dumps(supervisor.public_summary()))

if __name__=='__main__': main()

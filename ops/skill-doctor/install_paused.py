#!/usr/bin/env python3
"""Install only the read-only audit timer while coding remains paused."""
import json, os, shutil, subprocess
from pathlib import Path
HOME=Path.home()
ROOT=Path(__file__).resolve().parents[2]
OPS=HOME/'phpretro-ops'
BASE=HOME/'phpretro-skill-doctor'
assert (OPS/'STOP').exists(), 'STOP required'
assert not json.loads((OPS/'state/units.state.json').read_text()).get('reservations'), 'Workers must be settled'
def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args],text=True).strip()
assert not git('status','--porcelain'), 'Clean checkout required'
assert git('rev-parse','HEAD')==git('rev-parse','origin/main'), 'Reviewed main required'
cli=BASE/'runtime/node_modules/.bin/skill-doctor'
assert subprocess.check_output([str(cli),'--version'],text=True).strip()=='0.7.0'
BASE.chmod(0o700)
for name in ('reports','snapshots','audit-home'):
    path=BASE/name; path.mkdir(mode=0o700,exist_ok=True); path.chmod(0o700)
units=HOME/'.config/systemd/user'; units.mkdir(parents=True,exist_ok=True)
for name in ('phpretro-skill-doctor.service','phpretro-skill-doctor.timer'):
    shutil.copyfile(ROOT/'ops/systemd'/name,units/name)
env=dict(os.environ,XDG_RUNTIME_DIR=f'/run/user/{os.getuid()}')
def systemctl(*args):subprocess.run(['systemctl','--user',*args],env=env,check=True)
systemctl('daemon-reload')
systemctl('start','phpretro-skill-doctor.service')
systemctl('enable','--now','phpretro-skill-doctor.timer')
assert (OPS/'STOP').exists()
print('Read-only Skill Doctor audit installed; coding remains paused.')

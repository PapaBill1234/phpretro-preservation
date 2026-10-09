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
import hashlib
extension=json.loads((BASE/'extension-manifest.json').read_text())
assert extension['pin']=='fe1f942cf715a47faa67def0fa5f07882f3a84dc'
for name,digest in extension['inputs'].items():
    assert hashlib.sha256((ROOT/'ops/skill-doctor'/name).read_bytes()).hexdigest()==digest,'Build source mismatch'
package=Path(extension['package']).resolve()
assert package.is_relative_to(BASE.resolve()) and hashlib.sha256(package.read_bytes()).hexdigest()==extension['sha256']
subprocess.run(['npm','install','--prefix',str(BASE/'runtime'),str(package),'--ignore-scripts','--no-audit','--no-fund'],check=True)
cli=BASE/'runtime/node_modules/.bin/skill-doctor'
assert subprocess.check_output([str(cli),'--version'],text=True).strip()=='0.7.0'
BASE.chmod(0o700)
for name in ('reports','snapshots','audit-home'):
    path=BASE/name; path.mkdir(mode=0o700,exist_ok=True); path.chmod(0o700)
for name in ('sessions','archived_sessions'):
    (BASE/'audit-home/.codex'/name).mkdir(mode=0o700,parents=True,exist_ok=True)
binary=HOME/'.local/bin/skill-doctor';binary.parent.mkdir(parents=True,exist_ok=True)
launcher='#!/bin/sh\nexport HOME=/home/ubuntu/phpretro-skill-doctor/audit-home\nexec /home/ubuntu/phpretro-skill-doctor/runtime/node_modules/.bin/skill-doctor "$@"\n'
previous_launcher=launcher
launcher=launcher.replace('exec /home','export NODE_OPTIONS="--require /home/ubuntu/phpretro-preservation/ops/skill-doctor/deep-mode.cjs"\nexec /home')
assert not binary.exists() or binary.read_text() in (previous_launcher,launcher), 'Existing launcher is not owned by this installer'
binary.write_text(launcher);binary.chmod(0o700)
units=HOME/'.config/systemd/user'; units.mkdir(parents=True,exist_ok=True)
for name in ('phpretro-skill-doctor.service','phpretro-skill-doctor.timer','phpretro-skill-doctor-ui.service'):
    shutil.copyfile(ROOT/'ops/systemd'/name,units/name)
env=dict(os.environ,XDG_RUNTIME_DIR=f'/run/user/{os.getuid()}')
def systemctl(*args):subprocess.run(['systemctl','--user',*args],env=env,check=True)
systemctl('daemon-reload')
systemctl('start','phpretro-skill-doctor.service')
systemctl('enable','--now','phpretro-skill-doctor.timer')
systemctl('enable','--now','phpretro-skill-doctor-ui.service')
systemctl('restart','phpretro-skill-doctor-ui.service')
assert (OPS/'STOP').exists()
print('Read-only Skill Doctor audit installed; coding remains paused.')

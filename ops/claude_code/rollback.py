#!/usr/bin/env python3
"""Restore a known cutover backup while retaining STOP and disabled coding."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrity as control,runtime_policy,worker

def restore(backup):
    backup=Path(backup).resolve();ops=runtime_policy.OPS
    if not backup.is_relative_to((ops/'backups').resolve()) or not backup.name.startswith('claude-cutover-') or not (backup/'rollback.json').is_file():
        raise control.IntegrityError('Owned cutover backup required')
    if not (ops/'STOP').is_file():raise control.IntegrityError('STOP required before rollback')
    state=json.loads((ops/'state/units.state.json').read_text())
    if state.get('reservations'):raise control.IntegrityError('Workers must drain before rollback')
    old=json.loads((backup/'rollback.json').read_text());base=Path.home()/'phpretro-skill-doctor';units=Path.home()/'.config/systemd/user'
    subprocess.run(['sudo','-n','systemctl','disable','--now','phpretro-orchestrator.timer','phpretro-nightly.timer','phpretro-alerts.timer'],check=True)
    for service in ('phpretro-claude-supervisor.timer','phpretro-claude-supervisor.service','phpretro-skill-doctor-ui.service','phpretro-skill-doctor.timer','phpretro-skill-doctor.service'):
        subprocess.run(['systemctl','--user','stop',service],env=worker.bus_env(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    (Path.home()/'phpretro-claude-code/ENABLED').unlink(missing_ok=True)
    for name in ('phpretro-orchestrator.service','phpretro-nightly.service','phpretro-alerts.service'):
        previous=backup/(name+'.previous')
        if previous.is_file():subprocess.run(['sudo','-n','install','-m','644',str(previous),'/etc/systemd/system/'+name],check=True)
    if (backup/'doctor-runtime').is_dir():
        if (base/'runtime').exists():shutil.move(str(base/'runtime'),str(backup/'failed-doctor-runtime'))
        shutil.move(str(backup/'doctor-runtime'),str(base/'runtime'))
    if (backup/'doctor-manifest.json').is_file():shutil.copy2(backup/'doctor-manifest.json',base/'extension-manifest.json')
    for name in ('server.py','gateway.py','index.html'):
        if (backup/name).is_file():shutil.copy2(backup/name,Path.home()/'phpretro-dashboard'/name)
    for name in ('phpretro-dashboard.service','phpretro-access.service','phpretro-skill-doctor-ui.service','phpretro-skill-doctor.service'):
        target=units/(name+'.d/claude-runtime.conf');previous=backup/(name+'.dropin.previous')
        if previous.is_file():shutil.copy2(previous,target)
        elif name in old.get('changed_dropins',[]):target.unlink(missing_ok=True)
    if old.get('activation') is None:(ops/'state/claude-code-activation.json').unlink(missing_ok=True)
    else:control.atomic_json(ops/'state/claude-code-activation.json',old['activation'])
    if old.get('canvas_exists'):
        subprocess.run(['docker','update','--restart='+old['canvas_restart'],'phpretro-openhands-ui'],check=True,stdout=subprocess.DEVNULL)
        if old.get('canvas_running'):subprocess.run(['docker','start','phpretro-openhands-ui'],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['sudo','-n','systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','--user','daemon-reload'],env=worker.bus_env(),check=True)
    subprocess.run(['systemctl','--user','restart','phpretro-dashboard.service','phpretro-access.service','phpretro-skill-doctor-ui.service'],env=worker.bus_env(),check=True)
    subprocess.run(['systemctl','--user','start','phpretro-skill-doctor.timer'],env=worker.bus_env(),check=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('backup',type=Path);args=parser.parse_args();restore(args.backup)

#!/usr/bin/env python3
"""Reviewed native-Claude cutover, STOP retained; old runtimes remain rollback data."""
import argparse,hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrity as control,runtime_policy,worker
ROOT=Path(__file__).resolve().parents[2];OPS=runtime_policy.OPS
ACTIVE_BACKUP=None

def checked(*args):return subprocess.check_output(args,text=True).strip()
def main():
    global ACTIVE_BACKUP
    parser=argparse.ArgumentParser();parser.add_argument('--doctor-manifest',type=Path,required=True);args=parser.parse_args()
    os.umask(0o077)
    if not (OPS/'STOP').is_file():raise control.IntegrityError('STOP required')
    head=checked('git','-C',str(ROOT),'rev-parse','HEAD')
    if head!=checked('git','-C',str(ROOT),'rev-parse','origin/main') or checked('git','-C',str(ROOT),'status','--porcelain'):
        raise control.IntegrityError('Installation requires clean reviewed origin/main')
    validation=json.loads((OPS/'state/claude-code-validation.json').read_text())
    # Provider/auth may remain pending in a paused installation. Source,
    # lifecycle, browser and isolation must already have actual passing evidence.
    if validation.get('implementation_sha256')!=runtime_policy.fingerprint() or not all(
        validation.get('checks',{}).get(k) is True for k in ('foundation','ops','frontend','isolation','lifecycle','resources')):
        raise control.IntegrityError('Exact-source non-provider validation required')
    review=json.loads((OPS/'state/claude-code-source-review.json').read_text())
    if review.get('head')!=head or review.get('verdict')!='pass' or review.get('independent') is not True:
        raise control.IntegrityError('Exact-head independent source review required')
    extension=json.loads(args.doctor_manifest.read_text());package=Path(extension['package']).resolve()
    for name,digest in extension['inputs'].items():
        path=ROOT/'ops/skill-doctor'/name
        if path.parent!=ROOT/'ops/skill-doctor' or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise control.IntegrityError('Doctor package source mismatch')
    if (extension.get('pin')!='fe1f942cf715a47faa67def0fa5f07882f3a84dc' or
        not package.is_relative_to(Path.home()/'phpretro-claude-code') or
        hashlib.sha256(package.read_bytes()).hexdigest()!=extension['sha256']):
        raise control.IntegrityError('Unverified Doctor package')
    state=json.loads((OPS/'state/units.state.json').read_text())
    if state.get('reservations'):raise control.IntegrityError('Reservations must be settled')
    for path in (OPS/'state/receipts').glob('*.json'):
        if path.name.count('.')!=1:continue
        row=json.loads(path.read_text())
        if row.get('status')=='running' or worker.alive(row.get('worker_pid'),row.get('worker_identity')):
            raise control.IntegrityError('Existing worker must drain')
    backup=OPS/'backups'/('claude-cutover-'+str(int(time.time())));backup.mkdir(mode=0o700,parents=True)
    previous=OPS/'state/claude-code-activation.json'
    canvas=subprocess.run(['docker','container','inspect','--format={{.State.Running}} {{.HostConfig.RestartPolicy.Name}}','phpretro-openhands-ui'],capture_output=True,text=True)
    metadata={'activation':json.loads(previous.read_text()) if previous.is_file() else None,'changed_dropins':[],
      'canvas_exists':canvas.returncode==0,'canvas_running':canvas.stdout.startswith('true '),'canvas_restart':canvas.stdout.split()[-1] if canvas.returncode==0 else 'no'}
    if metadata['canvas_restart'] not in ('no','always','unless-stopped'):raise control.IntegrityError('Unrecognized Canvas restart policy')
    control.atomic_json(backup/'rollback.json',metadata)
    ACTIVE_BACKUP=backup
    base=Path.home()/'phpretro-skill-doctor'
    subprocess.run(['systemctl','--user','stop','phpretro-skill-doctor-ui.service','phpretro-skill-doctor.timer','phpretro-skill-doctor.service'],env=worker.bus_env(),check=True)
    # Build a separate installation before swapping; keep the complete previous UI.
    staged=base/'claude-runtime-staged'
    if staged.exists():raise control.IntegrityError('Previous staged Doctor installation needs inspection')
    subprocess.run(['npm','install','--prefix',str(staged),str(package),'--ignore-scripts','--no-audit','--no-fund'],check=True)
    if checked(str(staged/'node_modules/.bin/skill-doctor'),'--version')!='0.7.0':raise control.IntegrityError('Doctor version mismatch')
    shutil.move(str(base/'runtime'),str(backup/'doctor-runtime'))
    shutil.move(str(staged),str(base/'runtime'))
    shutil.copy2(base/'extension-manifest.json',backup/'doctor-manifest.json')
    control.atomic_json(base/'extension-manifest.json',{**extension,'reviewed':True,'acceptance_complete':True,'source_head':head})
    for timer in ('phpretro-orchestrator.timer','phpretro-nightly.timer','phpretro-alerts.timer'):
        subprocess.run(['sudo','-n','systemctl','disable','--now',timer],check=True)
    for name in ('phpretro-orchestrator.service','phpretro-nightly.service','phpretro-alerts.service'):
        if checked('systemctl','show',name,'--property=ActiveState','--value') not in ('inactive','failed'):
            raise control.IntegrityError('Root service must drain before cutover')
        previous=Path('/etc/systemd/system')/name
        if previous.is_file():shutil.copy2(previous,backup/(name+'.previous'))
        text=(ROOT/'ops/systemd'/name).read_text().replace('/home/ubuntu/phpretro-preservation',str(ROOT)).replace('Environment=PHPRETRO_RUNTIME=openhands','Environment=PHPRETRO_RUNTIME=claude-code\nEnvironment=PHPRETRO_REPO='+str(ROOT))
        staged=backup/name;staged.write_text(text)
        subprocess.run(['sudo','-n','install','-m','644',str(staged),str(previous)],check=True)
    units=Path.home()/'.config/systemd/user';units.mkdir(parents=True,exist_ok=True)
    for name in ('phpretro-claude-supervisor.service','phpretro-claude-supervisor.timer'):
        (units/name).write_text((ROOT/'ops/systemd'/name).read_text().replace('/home/ubuntu/phpretro-preservation',str(ROOT)))
    for old in ('phpretro-codex-supervisor.timer','phpretro-codex-supervisor.service','phpretro-openhands-webui.service'):
        if checked('systemctl','--user','show',old,'--property=LoadState','--value')!='not-found':
            subprocess.run(['systemctl','--user','disable','--now',old],env=worker.bus_env(),check=True)
    # Canvas is a Docker-managed service, not a systemd unit. Stop without deleting
    # its image, volumes, credentials or historical conversations.
    found=subprocess.run(['docker','container','inspect','--format={{.Name}}','phpretro-openhands-ui'],capture_output=True,text=True)
    if found.returncode==0:
        if found.stdout.strip()!='/phpretro-openhands-ui':raise control.IntegrityError('Unexpected Canvas identity')
        subprocess.run(['docker','update','--restart=no','phpretro-openhands-ui'],check=True,stdout=subprocess.DEVNULL)
        subprocess.run(['docker','stop','--time','10','phpretro-openhands-ui'],check=True,stdout=subprocess.DEVNULL)
    (Path.home()/'phpretro-claude-code/ENABLED').unlink(missing_ok=True)
    dashboard=Path.home()/'phpretro-dashboard'
    (Path.home()/'phpretro-skill-doctor/claude-agents/.claude/skills').mkdir(mode=0o700,parents=True,exist_ok=True)
    for name in ('server.py','gateway.py','index.html'):
        shutil.copy2(dashboard/name,backup/name);shutil.copy2(ROOT/'ops/dashboard'/name,dashboard/name)
    for name in ('phpretro-dashboard.service','phpretro-access.service','phpretro-skill-doctor-ui.service','phpretro-skill-doctor.service'):
        dropin=units/(name+'.d');dropin.mkdir(exist_ok=True)
        target=dropin/'claude-runtime.conf'
        if target.exists():shutil.copy2(target,backup/(name+'.dropin.previous'))
        metadata['changed_dropins'].append(name);control.atomic_json(backup/'rollback.json',metadata)
        extra=''
        if name in ('phpretro-skill-doctor-ui.service','phpretro-skill-doctor.service'):
            script='skill-doctor/ui.py' if name.endswith('-ui.service') else 'skill_doctor.py'
            extra='ExecStart=\nExecStart=/usr/bin/python3 '+str(ROOT/'ops'/script)+'\n'
        target.write_text('[Service]\nEnvironment=PHPRETRO_RUNTIME=claude-code\nEnvironment=PHPRETRO_REPO='+str(ROOT)+'\n'+extra)
    subprocess.run(['sudo','-n','systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','--user','daemon-reload'],env=worker.bus_env(),check=True)
    control.atomic_json(OPS/'state/claude-code-activation.json',{'installed':True,'enabled':False,'source_head':head,'backup':str(backup),'installed_at':time.time()})
    subprocess.run(['systemctl','--user','start','phpretro-skill-doctor.service','phpretro-skill-doctor.timer','phpretro-skill-doctor-ui.service'],env=worker.bus_env(),check=True)
    subprocess.run(['systemctl','--user','restart','phpretro-dashboard.service','phpretro-access.service'],env=worker.bus_env(),check=True)
    print('Claude pipeline installed paused. STOP, charges, original caps and historical sessions retained.')

if __name__=='__main__':
    try:main()
    except BaseException:
        if ACTIVE_BACKUP is not None:
            from claude_code import rollback
            rollback.restore(ACTIVE_BACKUP)
        raise

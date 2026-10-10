#!/usr/bin/env python3
"""Actual exact-source checks under STOP. Unknown provider/browser stays pending."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrity as control,runtime_policy,sandbox
from claude_code import policy
ROOT=Path(__file__).resolve().parents[2];OPS=runtime_policy.OPS

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--provider-evidence',type=Path);parser.add_argument('--doctor-evidence',type=Path)
    args=parser.parse_args()
    if not (OPS/'STOP').is_file():raise control.IntegrityError('STOP required')
    data=runtime_policy.load()
    if data.get('runtime')!='claude-code':raise control.IntegrityError('Select Claude runtime explicitly')
    fingerprint=runtime_policy.fingerprint();logs=OPS/'logs/claude-validation';logs.mkdir(mode=0o700,parents=True,exist_ok=True)
    checks={k:False for k in ('foundation','ops','frontend','isolation','lifecycle','resources','provider')}
    env={**os.environ,'PHPRETRO_RUNTIME':'openhands'}
    with (logs/'ops.log').open('w') as output:
        result=subprocess.run(['bash','ops/tests/run_all.sh'],cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,timeout=600)
    with (logs/'transport.log').open('w') as output:
        transport=subprocess.run([sys.executable,str(Path(__file__).with_name('gateway_smoke.py'))],cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,timeout=180)
    with (logs/'bridge.log').open('w') as output:
        bridge=subprocess.run([sys.executable,str(Path(__file__).with_name('bridge_smoke.py'))],cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,timeout=180)
    checks['ops']=result.returncode==0 and transport.returncode==0 and bridge.returncode==0
    rc,text=sandbox.check(ROOT);(logs/'foundation.log').write_text(text);checks['foundation']=rc==0
    box=sandbox.Sandbox(control.identity(),ROOT,writable=True);snapshot_at=0
    try:
        box.prepare();observed=sandbox.inspect(box.rid);config,host=observed['Config'],observed['HostConfig']
        mounts=observed['Mounts']
        checks['isolation']=(config['User']=='65532:65532' and host['NetworkMode']=='none' and host['ReadonlyRootfs'] is True
          and host['CapDrop']==['ALL'] and 'no-new-privileges' in host['SecurityOpt']
          and len([m for m in mounts if m['Type']=='bind'])==1
          and all(m['Destination'] in ('/repo','/tmp','/home/worker') for m in mounts))
        checks['resources']=host['Memory']>0 and host['PidsLimit']==data['container_pids'] and host['CgroupParent']==data['cgroup_parent']
        oldpid=observed['State']['Pid'];rc,text=box.execute('sleep 60 >/tmp/background.log 2>&1 & echo started',10)
        checks['lifecycle']=rc==0 and sandbox.inspect(box.rid)['State']['Pid']!=oldpid
        rc,text=box.execute('test ! -e /home/ubuntu/.claude && test ! -e /home/ubuntu/phpretro-openhands/secrets && test ! -S /var/run/docker.sock',10)
        checks['isolation']=checks['isolation'] and rc==0
        rc,text=box.execute('cat /opt/vulndb/fetched-at',10);snapshot_at=int(text.strip()) if rc==0 else 0
        checks['resources']=checks['resources'] and 0<=time.time()-snapshot_at<172800
        rc,text=box.execute('cd frontend && npm run typecheck && npm test && npm run build',1800)
        (logs/'frontend.log').write_text(text);checks['frontend']=rc==0
    finally:box.close()
    sandbox.assert_absent(box.rid)
    if args.doctor_evidence:
        doctor=json.loads(args.doctor_evidence.read_text())
        checks['frontend']=checks['frontend'] and doctor.get('implementation_sha256')==fingerprint and doctor.get('passed') is True
    else:checks['frontend']=False
    models={};provider_models={}
    if args.provider_evidence:
        provider=json.loads(args.provider_evidence.read_text())
        models=provider.get('models',{});provider_models=provider.get('provider_models',{})
        checks['provider']=(provider.get('implementation_sha256')==fingerprint and 0<=time.time()-provider.get('completed_at',0)<=86400
          and policy.authenticated(data) and all(models.get(m,{}).get('tool_calls') is True and models.get(m,{}).get('usage') is True
            for m,v in data['models'].items() if v.get('automatic')))
    if fingerprint!=runtime_policy.fingerprint():raise control.IntegrityError('Source changed during validation')
    evidence={'schema':'phpretro.claude-validation.v1','implementation_sha256':fingerprint,'checks':checks,'passed':all(checks.values()),
      'validated_at':time.time(),'vulnerability_snapshot_at':snapshot_at,'models':models,'provider_models':provider_models,
      'image_id':sandbox.docker('image','inspect','--format={{.Id}}',data['image']).decode().strip()}
    control.atomic_json(OPS/'state/claude-code-validation.json',evidence)
    print(json.dumps(evidence));return 0 if evidence['passed'] else 1
if __name__=='__main__':raise SystemExit(main())

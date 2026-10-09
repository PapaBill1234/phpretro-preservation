#!/usr/bin/env python3
"""Subscription-backed, bounded operational repairs; disabled until activation."""
import argparse
import fcntl
import http.client
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid

import billing
import codex_account as account
import integrity as control
import runtime_policy
import worker

OPS = Path(os.environ.get('PHPRETRO_OPS',Path.home()/'phpretro-ops'))
REPO = Path(os.environ.get('PHPRETRO_REPO',Path(__file__).resolve().parent.parent))
BASE = account.BASE
STATE = OPS/'state/codex-supervisor.json'
ENABLED = BASE/'ENABLED'
MODEL = 'gpt-6.1-sol'
VERSION = 'codex-cli 0.162.0'
ISSUES = {'billing_stale','dashboard_unavailable','controller_stale','receipt_orphan','state_invalid','disk_pressure'}
REPAIRS = {'billing_stale':'restart_billing','dashboard_unavailable':'restart_dashboard',
           'controller_stale':'start_controller','receipt_orphan':'reconcile_receipts'}
ACTIONS = set(REPAIRS.values())|{'defer'}
MODES = {'disabled','paused','healthy','running','repaired','unresolved','deferred','failed','busy'}
REASONS = ISSUES|{'disabled','pipeline_paused','pipeline_inactive','healthy','quota_unavailable',
    'quota_margin','not_authenticated','model_unavailable','cooldown','daily_limit','repair_complete',
    'repair_failed','repair_in_progress','no_safe_repair','cli_changed','validation_required','job_interrupted','unavailable'}


def load(path, default=None, limit=5*1024*1024):
    if path.stat().st_size>limit: raise ValueError('oversized state')
    value=json.loads(path.read_text())
    if not isinstance(value,dict): raise ValueError('invalid state')
    return value


def run(command, *, user=False, timeout=5):
    args=['systemctl']+(['--user'] if user else [])+command
    return subprocess.run(args,env=worker.bus_env(),capture_output=True,text=True,timeout=timeout)


def active(name, user=False):
    try: return run(['is-active',name],user=user).stdout.strip()=='active'
    except (OSError,subprocess.TimeoutExpired): return False


def snapshot():
    issues=[]
    stopped=(OPS/'STOP').exists()
    timer=active('phpretro-orchestrator.timer')
    controller=active('phpretro-orchestrator.service')
    state_ok=True
    try: state=load(OPS/'state/units.state.json')
    except (OSError,ValueError): state={}; state_ok=False; issues.append('state_invalid')
    reservations=state.get('reservations',{})
    if not isinstance(reservations,dict): state_ok=False; reservations={}; issues.append('state_invalid')
    if len(reservations)>100: state_ok=False; issues.append('state_invalid')
    live=0
    for rid in list(reservations)[:100]:
        try:
            if not isinstance(rid,str) or str(uuid.UUID(rid))!=rid: raise ValueError()
            receipt=load(OPS/'state/receipts'/(rid+'.json'))
            if receipt.get('run_id')!=rid: raise ValueError()
            if worker.alive(receipt.get('worker_pid'),receipt.get('worker_identity')): live+=1
            else: issues.append('receipt_orphan')
        except (OSError,ValueError): state_ok=False; issues.append('state_invalid')
    if state_ok and not stopped and timer and not controller and not reservations:
        if time.time()-(OPS/'state/units.state.json').stat().st_mtime>900: issues.append('controller_stale')
    if not billing.summary(OPS).get('fresh'): issues.append('billing_stale')
    try:
        port=int((Path.home()/'phpretro-dashboard/port').read_text().strip())
        if not 20000<=port<=60000: raise ValueError()
        connection=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
        try:
            connection.request('GET','/api/state')
            if connection.getresponse().status!=200: issues.append('dashboard_unavailable')
        finally: connection.close()
    except (OSError,ValueError,http.client.HTTPException): issues.append('dashboard_unavailable')
    stats=os.statvfs(OPS)
    if stats.f_bavail*stats.f_frsize<2*1024**3: issues.append('disk_pressure')
    return {'stop':stopped,'pipeline_active':bool(timer or controller),'controller_active':controller,
            'reservations':len(reservations),'workers':live,'state_valid':state_ok,'issues':sorted(set(issues))}


def numeric(value):
    return type(value) in (int,float) and __import__('math').isfinite(value) and value>=0


def public_summary(ops=OPS):
    """A strict metadata whitelist; never expose Codex messages or log paths."""
    try: data=load(ops/'state/codex-supervisor.json',limit=512*1024)
    except (OSError,ValueError): return {'mode':'disabled','enabled':False,'reason':'disabled','history':[]}
    account_data=data.get('account') if isinstance(data.get('account'),dict) else {}
    result={'mode':data.get('mode') if data.get('mode') in MODES else 'failed',
            'enabled':data.get('enabled') is True,'reason':data.get('reason') if data.get('reason') in REASONS else 'unavailable',
            'model':MODEL,'interval_minutes':30,'authenticated':account_data.get('authenticated') is True,
            'model_available':account_data.get('model_available') is True,'history':[]}
    for key in ('checked_at','next_check_at'):
        if numeric(data.get(key)): result[key]=data[key]
    quota=account_data.get('quota',{})
    for key in ('primary','secondary'):
        row=quota.get(key) if isinstance(quota,dict) else None
        if isinstance(row,dict) and account.window({'usedPercent':row.get('used_percent'),
            'windowDurationMins':row.get('duration_minutes'),'resetsAt':row.get('resets_at')}):
            result[key]={k:quota[key][k] for k in ('used_percent','duration_minutes','resets_at')}
    history=data.get('history') if isinstance(data.get('history'),list) else []
    for item in history[-20:]:
        if (not isinstance(item,dict) or item.get('mode') not in MODES or item.get('action') not in ACTIONS
                or item.get('reason') not in REASONS or not numeric(item.get('at'))): continue
        safe={k:item[k] for k in ('at','mode','action','reason')}
        for key in ('input_tokens','cached_input_tokens','output_tokens'):
            if type(item.get(key)) is int and item[key]>=0: safe[key]=item[key]
        result['history'].append(safe)
    return result


def eligible_action(action, before, current):
    return bool(action in ACTIONS and action!='defer' and not current['stop'] and current['pipeline_active']
        and current['state_valid'] and action in {REPAIRS.get(issue) for issue in current['issues']}
        and 'disk_pressure' not in current['issues']
        and action in {REPAIRS.get(issue) for issue in before['issues']}
        and (action not in ('start_controller','reconcile_receipts') or
             (not current['workers'] and not current['controller_active'])))


def execute(action):
    if action=='restart_billing': return run(['restart','phpretro-billing.service'],user=True,timeout=90).returncode
    if action=='restart_dashboard': return run(['restart','phpretro-dashboard.service'],user=True,timeout=30).returncode
    if action=='start_controller':
        return subprocess.run(['sudo','-n','systemctl','start','phpretro-orchestrator.service'],
                              capture_output=True,timeout=30).returncode
    if action=='reconcile_receipts':
        return subprocess.run(['python3',str(REPO/'ops/orchestrator.py'),'--no-dispatch'],
                              cwd=REPO,capture_output=True,timeout=90).returncode
    raise ValueError('unsupported repair')


def stop_process(proc):
    if proc.poll() is not None: return
    os.killpg(proc.pid,signal.SIGTERM)
    try: proc.wait(timeout=5)
    except subprocess.TimeoutExpired: os.killpg(proc.pid,signal.SIGKILL); proc.wait()


def decide(before, data, persist):
    """Sol selects an admitted routine repair. Host commands are controller-owned."""
    identity=str(uuid.uuid4()); private=BASE/'jobs'/identity
    private.mkdir(parents=True,mode=0o700)
    workspace=BASE/'work'; workspace.mkdir(mode=0o700,exist_ok=True)
    schema={'type':'object','properties':{'action':{'type':'string','enum':sorted(ACTIONS)},
        'reason':{'type':'string','enum':sorted(REASONS)}},'required':['action','reason'],'additionalProperties':False}
    control.atomic_json(private/'schema.json',schema)
    prompt=('You are PHPRetro operational supervision, using the user ChatGPT subscription. '
        'Choose ONE routine repair from the typed facts. Do not ask questions or use tools. '
        'Never remove STOP, raise limits, change routes, waive reviews or edit accounting. '
        'Do not start builders directly. Use defer for code defects, low disk, ambiguous facts or no safe repair. '
        'Supported issue-to-action mapping:'+json.dumps(REPAIRS)+'. Facts:'+json.dumps(before))
    command=[str(account.CLI),'exec','--json','--skip-git-repo-check','--ignore-user-config','--ignore-rules',
        '--sandbox','read-only','-c','approval_policy="never"','-c','forced_login_method="chatgpt"',
        '-c','web_search="disabled"','-c','model_reasoning_effort="low"','--disable','shell_tool',
        '--disable','unified_exec','--disable','multi_agent','--disable','hooks',
        '-m',MODEL,'-C',str(workspace),'--output-schema',str(private/'schema.json'),
        '-o',str(private/'decision.json'),prompt]
    data['attempts']=[at for at in data.get('attempts',[]) if numeric(at) and time.time()-at<86400]+[time.time()]
    data.update(mode='running',reason='repair_in_progress',job={'id':identity,'status':'prepared','started_at':time.time()})
    control.atomic_json(private/'status.json',data['job'])
    persist()
    fd=os.open(private/'events.jsonl',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as output:
        proc=subprocess.Popen(command,env=account.environment(),stdout=output,stderr=output,start_new_session=True,umask=0o077)
        data['job'].update(pid=proc.pid,process_identity=worker.process_identity(proc.pid),status='running'); persist()
        control.atomic_json(private/'status.json',data['job'])
        deadline=time.monotonic()+600; quota_at=0
        try:
            while proc.poll() is None:
                if (OPS/'STOP').exists() or not ENABLED.exists() or time.monotonic()>deadline or output.tell()>2*1024*1024:
                    raise InterruptedError('repair cancelled')
                if time.monotonic()>=quota_at:
                    if not account.allowed(account.read_account()): raise InterruptedError('quota unavailable or near limit')
                    quota_at=time.monotonic()+30
                time.sleep(1)
        finally:
            stop_process(proc)
            data['job']['status']='complete'; data['job']['rc']=proc.returncode; persist()
            control.atomic_json(private/'status.json',data['job'])
    if proc.returncode!=0: raise RuntimeError('repair decision failed')
    result=load(private/'decision.json',limit=4096)
    if set(result)!={'action','reason'} or result.get('action') not in ACTIONS or result.get('reason') not in REASONS:
        raise ValueError('invalid repair decision')
    usage={}
    for line in (private/'events.jsonl').read_text().splitlines():
        try:
            event=json.loads(line)
            if event.get('type')=='turn.completed':
                raw=event.get('usage',{})
                usage={k:raw[k] for k in ('input_tokens','cached_input_tokens','output_tokens') if type(raw.get(k)) is int and raw[k]>=0}
        except (ValueError,AttributeError): pass
    return result,usage


def cycle(inspect=False):
    BASE.mkdir(mode=0o700,exist_ok=True)
    with (BASE/'supervisor.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return
        try:
            data=load(STATE,limit=512*1024)
            if (data.get('schema')!='phpretro.codex-supervisor.v1' or not isinstance(data.get('attempts'),list)
                or not all(numeric(at) for at in data['attempts']) or not isinstance(data.get('history'),list)
                or not isinstance(data.get('job',{}),dict)):
                raise ValueError('invalid supervisor state')
        except FileNotFoundError: data={'schema':'phpretro.codex-supervisor.v1','history':[],'attempts':[]}
        except (OSError,ValueError): raise control.IntegrityError('supervisor state unreadable; preserve it')
        def persist(): control.atomic_json(STATE,data)
        previous=data.get('job',{})
        before=snapshot()
        data.update(enabled=ENABLED.exists(),checked_at=time.time(),next_check_at=time.time()+1800,
                    snapshot=before,mode='disabled',reason='disabled')
        if inspect or data['enabled']: data['account']=account.read_account()
        if worker.alive(previous.get('pid'),previous.get('process_identity')):
            data.update(mode='busy',reason='repair_in_progress'); persist(); return
        if not data['enabled']: persist(); return
        if before['stop']: data.update(mode='paused',reason='pipeline_paused'); persist(); return
        if not before['pipeline_active']: data.update(mode='paused',reason='pipeline_inactive'); persist(); return
        if not before['issues']: data.update(mode='healthy',reason='healthy'); persist(); return
        if inspect: data.update(mode='deferred',reason='no_safe_repair'); persist(); return
        if not before['state_valid'] or 'disk_pressure' in before['issues'] or not any(issue in REPAIRS for issue in before['issues']):
            data.update(mode='unresolved',reason='no_safe_repair'); persist(); return
        acct=data['account']
        if not account.allowed(acct):
            reason=('not_authenticated' if not acct.get('authenticated') else 'model_unavailable' if not acct.get('model_available')
                    else 'quota_unavailable' if not acct.get('quota',{}).get('available') else 'quota_margin')
            data.update(mode='deferred',reason=reason); persist(); return
        attempts=[at for at in data.get('attempts',[]) if numeric(at) and time.time()-at<86400]
        if len(attempts)>=2: data.update(mode='deferred',reason='daily_limit'); persist(); return
        if attempts and time.time()-max(attempts)<21600: data.update(mode='deferred',reason='cooldown'); persist(); return
        if not os.environ.get('INVOCATION_ID'): data.update(mode='deferred',reason='no_safe_repair'); persist(); return
        if not runtime_policy.ready(): data.update(mode='deferred',reason='validation_required'); persist(); return
        try:
            version=subprocess.check_output([str(account.CLI),'--version'],text=True,timeout=5).strip()
            if version!=VERSION: data.update(mode='deferred',reason='cli_changed'); persist(); return
            decision,usage=decide(before,data,persist)
            action=decision['action']; current=snapshot()
            if not eligible_action(action,before,current) or not account.allowed(account.read_account()):
                mode,reason='deferred','no_safe_repair'
            else:
                rc=execute(action)
                after=snapshot()
                issue=next(key for key,value in REPAIRS.items() if value==action)
                mode='repaired' if rc==0 and issue not in after['issues'] else 'unresolved'
                reason='repair_complete' if mode=='repaired' else 'repair_failed'
            data.update(mode=mode,reason=reason,account=account.read_account())
            data['history']=(data.get('history',[])+[{'at':time.time(),'mode':mode,'reason':reason,'action':action,**usage}])[-20:]
        except (OSError,ValueError,RuntimeError,InterruptedError,subprocess.TimeoutExpired):
            data.update(mode='failed',reason='repair_failed')
            data['history']=(data.get('history',[])+[{'at':time.time(),'mode':'failed','reason':'repair_failed','action':'defer'}])[-20:]
        persist()


def main():
    os.umask(0o077)
    def interrupted(*_): raise InterruptedError('supervisor stopped')
    signal.signal(signal.SIGTERM,interrupted)
    ap=argparse.ArgumentParser()
    ap.add_argument('--inspect',action='store_true',help='read health/auth/quota; never run a repair')
    ap.add_argument('--once',action='store_true')
    args=ap.parse_args()
    cycle(inspect=args.inspect)
    print(json.dumps(public_summary()))


if __name__=='__main__': main()

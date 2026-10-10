#!/usr/bin/env python3
"""Thirty-minute Claude supervision using the original controller ledger.

Healthy/paused checks use no inference. One tool-free typed decision can select
one existing reversible operation. Original token/cash caps and locks apply.
No arbitrary commands, code edits, approval bypass or automatic Deep Scan.
"""
import argparse,fcntl,json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrity as control,codex_supervisor as health,runtime_policy,worker
from claude_code import policy
OPS=runtime_policy.OPS;BASE=Path.home()/'phpretro-claude-code';STATE=OPS/'state/claude-supervisor.json'
ENABLED=BASE/'ENABLED'

def public_summary(ops=OPS):
    data=health.load(ops/'state/claude-supervisor.json') if (ops/'state/claude-supervisor.json').is_file() else {}
    return {k:data.get(k) for k in ('mode','reason','checked_at','next_check_at','history','authenticated','enabled')} | {
      'model':runtime_policy.load()['model_roles']['supervisor'],'runtime':'claude-code','interval_minutes':30,
      'quota_status':'unavailable; original request/token/cash bounds and provider backoff apply'}

def cycle(inspect=False):
    BASE.mkdir(mode=0o700,parents=True,exist_ok=True)
    with (BASE/'supervisor.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        before=health.snapshot()
        data=health.load(STATE) if STATE.exists() else {'schema':'phpretro.claude-supervisor.v1','history':[],'attempts':[]}
        if data.get('schema')!='phpretro.claude-supervisor.v1' or not isinstance(data.get('attempts'),list):
            raise control.IntegrityError('Invalid Claude supervisor state; preserve it')
        data.update(checked_at=time.time(),next_check_at=time.time()+1800,enabled=ENABLED.is_file(),
                    snapshot=before,mode='disabled',reason='disabled',authenticated=policy.authenticated(runtime_policy.load()))
        def save():control.atomic_json(STATE,data)
        if not data['enabled']:save();return
        if before['stop']:data.update(mode='paused',reason='pipeline_paused');save();return
        if not before['issues']:data.update(mode='healthy',reason='healthy');save();return
        if inspect or not before['state_valid'] or before['workers'] or 'disk_pressure' in before['issues']:
            data.update(mode='deferred',reason='no_safe_repair');save();return
        attempts=[at for at in data['attempts'] if type(at) in (int,float) and 0<=time.time()-at<86400]
        if len(attempts)>=2 or attempts and time.time()-max(attempts)<21600:
            data.update(mode='deferred',reason='daily_limit_or_cooldown');save();return
        if not os.environ.get('INVOCATION_ID') or not runtime_policy.ready():
            data.update(mode='deferred',reason='validation_or_auth_required');save();return
        # Serialize admission with the root controller. Never overlap a paid job.
        with (OPS/'locks/orchestrator.lock').open('a') as controller_lock:
            try:fcntl.flock(controller_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:data.update(mode='busy',reason='controller_active');save();return
            import orchestrator
            state=orchestrator.load_state()
            if state.get('reservations'):data.update(mode='busy',reason='worker_active');save();return
            prompt=('Choose exactly one action and reason; JSON {"action":"...","reason":"..."}. '
              'Allowed actions:'+json.dumps(sorted(health.ACTIONS))+'. Allowed reasons:'+json.dumps(sorted(health.REASONS))+
              '. Use defer if no supported safe action. Never remove STOP, raise limits or change review policy. '
              'Mapping:'+json.dumps(health.REPAIRS)+'. Facts:'+json.dumps(before))
            data['attempts']=attempts+[time.time()];data.update(mode='running',reason='decision_running');save()
            rc,text,usage=orchestrator.hermes_run('claude-supervisor',runtime_policy.load()['model_roles']['supervisor'],
              prompt,'',BASE,'claude-supervisor',180,role='reviewer',state=state)
            if usage.get('admission_denied') is True:data['attempts']=attempts
            state['tokens_today']=int(state.get('tokens_today',0))+orchestrator.usage_tokens(usage)
            if state['tokens_today']>orchestrator.DAILY_TOKEN_CAP:
                raise control.IntegrityError('Supervisor exceeded unchanged daily token cap')
            orchestrator.write_json(orchestrator.STATE_JSON,state)
        if rc!=0:
            data.update(mode='deferred',reason='decision_failed_or_budget_wait');save();return
        try:
            decision=json.loads(text)
            if set(decision)!={'action','reason'} or decision['action'] not in health.ACTIONS or decision['reason'] not in health.REASONS:raise ValueError()
        except (ValueError,TypeError,KeyError):data.update(mode='failed',reason='invalid_decision');save();return
        action=decision['action'];current=health.snapshot()
        if not health.eligible_action(action,before,current):data.update(mode='deferred',reason='no_safe_repair');save();return
        result=health.execute(action);after=health.snapshot()
        issue=next(k for k,v in health.REPAIRS.items() if v==action)
        data.update(mode='repaired' if result==0 and issue not in after['issues'] else 'unresolved',reason=decision['reason'])
        data['history']=(data['history']+[{'at':time.time(),'action':action,'mode':data['mode'],
          'tokens':usage.get('total_tokens'),'usage_complete':usage.get('usage_complete')}])[-20:];save()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--inspect',action='store_true');args=parser.parse_args();cycle(args.inspect)

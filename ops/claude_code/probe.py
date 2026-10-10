#!/usr/bin/env python3
"""Explicit charged native-provider acceptance under the owned migration pause.

No availability polling, unit rerouting or budget reset. The normal controller
reservation, worker, timeout, ledger and strict usage parser remain mandatory.
"""
import argparse,fcntl,json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrity as control,orchestrator as controller,runtime_policy,worker
from claude_code import policy

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true');args=parser.parse_args()
    if not args.run:parser.error('Explicit --run required')
    os.umask(0o077);ops=runtime_policy.OPS;data=runtime_policy.load();fingerprint=runtime_policy.fingerprint()
    if not policy.bootstrap_ready(data,ops,fingerprint):raise control.IntegrityError('Authorized paused installation, owned STOP and private provider credentials required')
    destination=ops/'state/claude-code-provider.json'
    if destination.is_file():
        old=json.loads(destination.read_text())
        if old.get('implementation_sha256')==fingerprint and old.get('attempted') is True:
            raise control.IntegrityError('Provider acceptance already attempted for this source; inspect its receipt')
    with (ops/'locks/orchestrator.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state=controller.load_state()
        if state.get('reservations'):raise control.IntegrityError('Existing reservations must drain')
        for receipt in (ops/'state/receipts').glob('*.json'):
            if receipt.name.count('.')!=1:continue
            row=json.loads(receipt.read_text())
            if row.get('status')=='running' or worker.alive(row.get('worker_pid'),row.get('worker_identity')):
                raise control.IntegrityError('An existing worker must drain')
        evidence={'attempted':True,'implementation_sha256':fingerprint,'started_at':time.time(),'models':{},'provider_models':{},
          'note':'Actual native harness compatibility with existing providers; not an availability poll or unit review.'}
        control.atomic_json(destination,evidence)
        complete=True;charged=0
        for model,settings in data['models'].items():
            if not settings.get('automatic'):continue
            rc,_,usage=controller.hermes_run('claude-bootstrap',model,
              "Use execute exactly once with command: printf 'CLAUDE_BRIDGE_ACCEPTED\\n'. Then finish with CLAUDE_BRIDGE_ACCEPTED. Do not edit files or use additional tools.",
              '',controller.REPO,'claude-provider-acceptance',180,role='builder',state=state,bootstrap=True)
            tokens=controller.usage_tokens(usage);charged+=tokens
            state['tokens_today']=int(state.get('tokens_today',0))+tokens;controller.write_json(controller.STATE_JSON,state)
            rid=usage.get('run_id');context=controller.read_json(ops/'state/receipts'/(str(rid)+'.context.json'),{})
            tool_ok=context.get('tool_calls')==1 and context.get('tool_errors')==0
            ok=rc==0 and usage.get('usage_complete') is True and tool_ok and usage.get('model')==model
            evidence['models'][model]={'tool_calls':tool_ok,'usage':ok,'cli_version':data['cli_version'],'native_session_id':usage.get('session_id'),'run_id':rid,'rc':rc}
            provider=usage.get('provider','').removeprefix('custom:')
            if ok and provider in ('a6api','portdan'):
                evidence['provider_models'].setdefault(provider,{})[model]={'tool_calls':True,'usage':True,'reported_model':usage.get('reported_model'),'checked_at':time.time()}
            evidence['completed_at']=time.time();control.atomic_json(destination,evidence)
            if not ok:complete=False;break  # No unchanged retry and no repeated paid acceptance.
        if runtime_policy.fingerprint()!=fingerprint:raise control.IntegrityError('Source changed during provider acceptance')
        print(json.dumps({'passed':complete,'models':list(evidence['models']),'tokens':charged,'STOP':(ops/'STOP').is_file()}))
        return 0 if complete else 1
if __name__=='__main__':raise SystemExit(main())

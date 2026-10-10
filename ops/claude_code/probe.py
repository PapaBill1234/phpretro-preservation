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

def model_plan(data,fingerprint,old,selected=None,provider='a6api'):
    automatic=[model for model,settings in data['models'].items() if settings.get('automatic')]
    models=[selected] if selected else automatic
    if not models or any(model not in automatic for model in models):raise control.IntegrityError('Select one configured automatic model')
    if provider not in ('a6api','portdan') or any(provider not in data['models'][m].get('provider_order',[]) for m in models):
        raise control.IntegrityError('Select one configured provider route')
    if provider!='a6api' and selected is None:raise control.IntegrityError('Fallback acceptance requires one explicit model')
    if old.get('implementation_sha256')==fingerprint and old.get('attempted') is True:
        records=old.get('models',{})
        if not isinstance(records,dict):raise control.IntegrityError('Prior acceptance records are invalid')
        used=old.get('attempted_models',list(records))
        if not isinstance(used,list) or not used or any(not isinstance(model,str) for model in used):
            raise control.IntegrityError('Prior acceptance scope is unknown; inspect its receipt')
        routes=old.get('attempted_routes')
        if routes is None:routes=['a6api:'+model for model in set(used)|set(records)]
        if not isinstance(routes,list) or any(not isinstance(route,str) or route not in [p+':'+m for p in ('a6api','portdan') for m in automatic] for route in routes):
            raise control.IntegrityError('Prior acceptance route scope is unknown; inspect its receipt')
        if any(provider+':'+model in routes for model in models):
            raise control.IntegrityError('Selected route already attempted for this source; inspect its receipt')
    return models

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',action='store_true')
    parser.add_argument('--model',choices=('gpt-6-luna','gpt-6.1-sol','deepseek-v4.1-flash'),help='Explicitly check only an unattempted model; never repeat a failed model')
    parser.add_argument('--provider',choices=('a6api','portdan'),default='a6api',help='One distinct configured route acceptance under STOP; no unchanged route retry')
    args=parser.parse_args()
    if not args.run:parser.error('Explicit --run required')
    os.umask(0o077);ops=runtime_policy.OPS;data=runtime_policy.load();fingerprint=runtime_policy.fingerprint()
    if not policy.bootstrap_ready(data,ops,fingerprint):raise control.IntegrityError('Authorized paused installation, owned STOP and private provider credentials required')
    destination=ops/'state/claude-code-provider.json'
    with (ops/'locks/orchestrator.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # Read attempt state under the same lock as the physical execution.
        # Another invocation may have finished while this one prepared.
        old=json.loads(destination.read_text()) if destination.is_file() else {}
        models=model_plan(data,fingerprint,old,args.model,args.provider)
        if old.get('implementation_sha256')!=fingerprint and old.get('attempted') is True:
            prior=old.get('implementation_sha256','')
            if isinstance(prior,str) and len(prior)==64 and all(c in '0123456789abcdef' for c in prior):
                archive=ops/'state'/('claude-code-provider-'+prior+'.json')
                if not archive.exists():control.atomic_json(archive,old)
        state=controller.load_state()
        if state.get('reservations'):raise control.IntegrityError('Existing reservations must drain')
        for receipt in (ops/'state/receipts').glob('*.json'):
            if receipt.name.count('.')!=1:continue
            row=json.loads(receipt.read_text())
            if row.get('status')=='running' or worker.alive(row.get('worker_pid'),row.get('worker_identity')):
                raise control.IntegrityError('An existing worker must drain')
        evidence=dict(old) if old.get('implementation_sha256')==fingerprint else {'attempted':True,'implementation_sha256':fingerprint,'started_at':time.time(),'models':{},'provider_models':{},
          'note':'Actual native harness compatibility with existing providers; not an availability poll or unit review.'}
        evidence.setdefault('attempted_models',list(evidence['models']))
        evidence.setdefault('provider_models',{})
        evidence.setdefault('attempted_routes',['a6api:'+model for model in set(evidence['attempted_models'])|set(evidence['models'])])
        evidence.setdefault('route_attempts',{'a6api:'+model:dict(row) for model,row in evidence['models'].items()})
        complete=True;charged=0
        for model in models:
            if model not in evidence['attempted_models']:evidence['attempted_models'].append(model)
            route=args.provider+':'+model
            evidence['attempted_routes'].append(route);control.atomic_json(destination,evidence)
            rc,_,usage=controller.hermes_run('claude-bootstrap',model,
              "Use execute exactly once with command: printf 'CLAUDE_BRIDGE_ACCEPTED\\n'. Then finish with CLAUDE_BRIDGE_ACCEPTED. Do not edit files or use additional tools.",
              '',controller.REPO,'claude-provider-acceptance',180,role='builder',state=state,bootstrap=True,bootstrap_provider=args.provider)
            tokens=controller.usage_tokens(usage);charged+=tokens
            state['tokens_today']=int(state.get('tokens_today',0))+tokens;controller.write_json(controller.STATE_JSON,state)
            rid=usage.get('run_id');context=controller.read_json(ops/'state/receipts'/(str(rid)+'.context.json'),{})
            tool_ok=context.get('tool_calls')==1 and context.get('tool_errors')==0
            provider=usage.get('provider','').removeprefix('custom:')
            ok=rc==0 and usage.get('usage_complete') is True and tool_ok and usage.get('model')==model and provider==args.provider
            row={'tool_calls':tool_ok,'usage':ok,'cli_version':data['cli_version'],'native_session_id':usage.get('session_id'),'run_id':rid,'rc':rc,'provider':args.provider}
            evidence['route_attempts'][route]=row
            if ok or evidence['models'].get(model,{}).get('usage') is not True:evidence['models'][model]=row
            if ok and provider in ('a6api','portdan'):
                evidence['provider_models'].setdefault(provider,{})[model]={'tool_calls':True,'usage':True,'reported_model':usage.get('reported_model'),'checked_at':time.time()}
            evidence['completed_at']=time.time();control.atomic_json(destination,evidence)
            if not ok:complete=False;break  # No unchanged retry and no repeated paid acceptance.
        if runtime_policy.fingerprint()!=fingerprint:raise control.IntegrityError('Source changed during provider acceptance')
        all_passed=all(evidence['models'].get(model,{}).get('usage') is True for model,settings in data['models'].items() if settings.get('automatic'))
        print(json.dumps({'passed':complete,'all_models_passed':all_passed,'selected_models':models,'models':list(evidence['models']),'tokens':charged,'STOP':(ops/'STOP').is_file()}))
        return 0 if complete else 1
if __name__=='__main__':raise SystemExit(main())

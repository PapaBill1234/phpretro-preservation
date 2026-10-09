"""Read-only session evidence for OpenHands and provider calls; never transcripts."""
import json
from pathlib import Path
import context_usage

def read(path, default=None):
    try:
        if path.is_symlink() or path.stat().st_size > 8_000_000:return default
        return json.loads(path.read_text())
    except (OSError,ValueError):return default

def number(value):
    return value if type(value) in (int,float) and 0 <= value < 1e15 else None

def sessions(home=None):
    home=Path(home or Path.home()); state=home/'phpretro-ops/state'
    rows=[]
    files=sorted((state/'receipts').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    for p in files:
        if p.name.count('.')!=1:continue
        d=read(p,{})
        if not isinstance(d,dict):continue
        if d.get('runtime')!='openhands' or not d.get('run_id'):continue
        usage=d.get('usage') or {}; context=read(p.with_suffix('.context.json'),{})
        if not isinstance(usage,dict):usage={}
        if not isinstance(context,dict):context={}
        try:observed=context_usage.summary(context)
        except ValueError:observed={}
        context_requests=[]
        if observed:
            context_requests=[{k:r[k] for k in ('estimated_context_tokens','estimated_tool_schema_tokens','estimated_system_tokens')} for r in context['requests']]
        rows.append({'id':d['run_id'],'unit':d.get('unit'),'role':d.get('role'),'model':d.get('model'),
          'provider':usage.get('provider'),'status':d.get('status'),'rc':d.get('rc'),
          'started':number(d.get('ts_start') or d.get('prepared_at')),
          'ended':number(d.get('completed_at')),'tokens':number(usage.get('total_tokens')),
          'input':number(usage.get('input_tokens')),'output':number(usage.get('output_tokens')),
          'cached':number(usage.get('cache_read_tokens')),'requests':number(usage.get('api_calls')),
          'complete':usage.get('usage_complete') is True,
          'context':{k:number(context.get(k)) for k in ('tool_calls','tool_errors','repeated_commands','events','brief_chars')},
          'context_complete':observed.get('usage_status')=='complete',
          'context_requests':context_requests,'unused_tools':observed.get('unused_tools',[])})
        if len(rows)==500:break
    billing=read(state/'a6api-billing.json',{})
    if not isinstance(billing,dict):billing={}
    calls=billing.get('account_rows',billing.get('rows',[]))
    if not isinstance(calls,list):calls=[]
    safe_calls=[{k:r.get(k) for k in ('request_id','created_at','model','input_tokens_including_cache','cache_read_tokens','output_tokens','billed_usd')} for r in calls if isinstance(r,dict)]
    return {'sessions':rows,'provider_calls':safe_calls,'billing_collected_at':billing.get('collected_at'),
            'billing_scope':billing.get('account_rows_scope','coding key, today only'),
            'session_limit':500,'evidence':'Receipts and context counters; older runs may lack metadata. SDK conversation transcripts were not retained. Provider calls are billing evidence, not sessions; costs must not be added twice.'}

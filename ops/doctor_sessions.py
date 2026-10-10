"""Read-only, scoped runtime sessions, live findings and billing evidence."""
import datetime,json,time,uuid,yaml
from pathlib import Path
import context_usage
import session_journal

def read(path, default=None):
    try:
        if path.is_symlink() or path.stat().st_size > 8_000_000:return default
        return json.loads(path.read_text())
    except (OSError,ValueError):return default

def number(value):
    return value if type(value) in (int,float) and 0 <= value < 1e15 else None

def timestamp(value):
    numeric=number(value)
    if numeric is not None:return numeric
    if isinstance(value,str):
        try:
            date=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
            return date.replace(tzinfo=date.tzinfo or datetime.timezone.utc).timestamp()
        except ValueError:pass
    return None

def ordered_files(path,pattern):
    rows=[]
    for p in path.glob(pattern):
        try:
            if not p.is_symlink():rows.append((p.stat().st_mtime,p))
        except OSError:pass
    return [p for _,p in sorted(rows,reverse=True)]

def optimization_metadata(raw):
    if not isinstance(raw,dict):return None
    keys=('compact-tool-output','reviewer-thinking')
    values=raw.get('values');versions=raw.get('versions')
    if not isinstance(values,dict) or not isinstance(versions,dict) or set(values)!=set(keys) or set(versions)!=set(keys):return None
    if any(type(values[k]) is not bool for k in keys):return None
    try:
        revision=raw['revision']
        if revision!='default' and str(uuid.UUID(revision))!=revision:return None
        for v in versions.values():
            if v is not None and str(uuid.UUID(v))!=v:return None
    except (KeyError,ValueError,TypeError,AttributeError):return None
    return {'revision':revision,'values':{k:values[k] for k in keys},'versions':{k:versions[k] for k in keys}}

def native_sessions(home):
    rows=[]
    for path in ordered_files(home/'phpretro-codex/jobs','*/schema.json')[:500]:
        folder=path.parent
        try:str(uuid.UUID(folder.name))
        except ValueError:continue
        usage={};events=0;failed=False;parse_complete=True
        log=folder/'events.jsonl'
        try:
            if log.is_symlink() or log.stat().st_size>4_000_000:raise ValueError()
            for line in log.read_text().splitlines():
                event=json.loads(line);events+=1
                if event.get('type')=='turn.failed':failed=True
                if event.get('type')=='turn.completed':
                    raw=event.get('usage',{})
                    for key in ('input_tokens','cached_input_tokens','output_tokens'):
                        value=number(raw.get(key))
                        if value is not None:usage[key]=usage.get(key,0)+value
        except (OSError,ValueError,AttributeError):parse_complete=False
        decision=read(folder/'decision.json',{})
        finished=isinstance(decision,dict) and decision.get('action') in ('restart_billing','restart_dashboard','start_controller','reconcile_receipts','defer')
        status=read(folder/'status.json',{});status=status if isinstance(status,dict) else {}
        running=False
        if status.get('status')=='running':
            import worker
            running=worker.alive(status.get('pid'),status.get('process_identity'))
        failed=failed or status.get('rc') not in (None,0)
        rows.append({'id':folder.name,'runtime':'codex','unit':'Operations','role':'supervisor','model':'gpt-6.1-sol',
          'provider':'ChatGPT subscription','status':'running' if running else 'failed' if failed else 'complete' if finished else 'incomplete',
          'rc':status.get('rc'),'started':number(status.get('started_at')) or path.stat().st_mtime,'tokens':usage.get('input_tokens',0)+usage.get('output_tokens',0) if usage else None,
          'input':usage.get('input_tokens'),'output':usage.get('output_tokens'),'cached':usage.get('cached_input_tokens'),
          'complete':bool(usage and finished and parse_complete and not running and status.get('rc')==0),'context_complete':False,'context':{'events':events},'context_requests':[],
          'unused_tools':[],'journal_available':False,'action':decision.get('action') if finished else None})
    return rows

def journal(identity,home=None):
    try:
        if str(uuid.UUID(identity))!=identity:raise ValueError()
    except (ValueError,TypeError,AttributeError):return None
    home=Path(home or Path.home());path=home/'phpretro-ops/state/receipts'/(identity+'.session.json')
    data=read(path,{})
    if not isinstance(data,dict) or data.get('schema')!=session_journal.SCHEMA:return None
    events=data.get('events')
    if not isinstance(events,list) or len(events)>512:return None
    safe=[]
    for row in events:
        if not isinstance(row,dict) or row.get('kind') not in session_journal.KINDS:continue
        item={'kind':row['kind'],'at':number(row.get('at')),'text':session_journal.redact(str(row.get('text',''))[:4000])}
        for key in ('rc','request','provider'):
            if type(row.get(key)) is int or key=='provider' and row.get(key) in ('a6api','portdan'):item[key]=row[key]
        safe.append(item)
    return {'events':safe,'complete':data.get('complete') is True,'truncated':data.get('truncated') is True}

def findings(rows,state,billing,canvas):
    issues=[]
    def add(code,severity,title,summary,session=None,recommendation='Inspect the retained evidence before changing the runtime.'):
        issues.append({'id':'runtime:'+code+(':'+session['id'] if session else ''),'kind':'context','severity':severity,
          'title':title,'summary':summary,'resourceNames':[session.get('runtime','openhands'),session.get('unit',''),session.get('role',''),session.get('model','')] if session else ['PHPRetro runtime'],
          'resourceIds':[],'evidence':[{'label':'Session','value':session['id']}] if session else [],'recommendation':recommendation,
          'detectionMethod':'Retained runtime metadata','runtime':session.get('runtime') if session else 'all','session_id':session['id'] if session else None})
    latest={}
    for row in rows:
        key=(row.get('runtime'),row.get('unit'),row.get('role'),row.get('model'))
        if key not in latest:latest[key]=row
    for row in latest.values():
        if row.get('rc') not in (None,0) or row.get('status') in ('error','stuck','incomplete','failed'):
            historical=row.get('unit_state')=='merged'
            add('failed','info' if historical else 'med','Historical agent failure' if historical else 'Agent run needs review',f"{row.get('unit')} · {row.get('role')} · {row.get('model')} ended with {row.get('status')} / exit {row.get('rc','unknown')}."+(' The unit subsequently merged.' if historical else ''),row,
                'Check provider errors and the run allowance. Continue the same work only through the controller; retain charges and exact-head review requirements.')
        if row.get('context',{}).get('tool_errors',0):add('tool-errors','low','Tool executions returned errors',f"{row['context']['tool_errors']} recorded tool errors.",row)
        if row.get('context',{}).get('repeated_commands',0):add('repeats','low','Repeated commands consumed context',f"{row['context']['repeated_commands']} repeated commands recorded.",row,'Inspect the timeline for avoidable repetition. Repeated test or inspection commands may be necessary; savings are not yet measured.')
        if not row.get('context_complete'):add('context-gap','info','Session context coverage is partial','Missing or truncated history cannot establish unused instructions or tools.',row)
        if row.get('unused_tools'):add('unused-tool','info','No Execute calls in an observed run','The completed observed session recorded zero Execute calls.',row,'Review the schema overhead for this role. Keep the tool available when later work needs it.')
    collected=number(billing.get('collected_at'))
    if collected is None or time.time()-collected>900:add('billing-stale','med','A6API billing collection is stale','Latest account-call evidence is missing or more than fifteen minutes old.','' or None,'Restart the read-only billing collector; do not change charges or budgets.')
    if canvas and not canvas.get('available'):add('canvas-unavailable','med','OpenHands Web UI session evidence is unavailable','The local read-only Canvas metadata request failed. Retained SDK sessions remain available.')
    reservations=state.get('reservations',{}) if isinstance(state,dict) else {}
    known={s['id'] for s in rows}
    if isinstance(reservations,dict):
        for identity in reservations:
            if identity not in known:add('missing-receipt','med','A live reservation lacks readable session evidence','The controller reservation exists but its receipt is missing or invalid.')
    return issues

def sessions(home=None,canvas=None):
    home=Path(home or Path.home()); state=home/'phpretro-ops/state'
    rows=[]
    units=read(state/'units.state.json',{});units=units if isinstance(units,dict) else {}
    unit_states={}
    try:
        path=state/'units.live.yaml'
        if path.is_symlink() or path.stat().st_size>2_000_000:raise ValueError()
        roadmap=yaml.safe_load(path.read_text())
        if isinstance(roadmap,dict) and isinstance(roadmap.get('units'),list):
            unit_states={r['id']:r.get('status') for r in roadmap['units'][:2000] if isinstance(r,dict) and isinstance(r.get('id'),str) and isinstance(r.get('status'),str)}
    except (OSError,ValueError,yaml.YAMLError):pass
    reservations=units.get('reservations',{});reservations=reservations if isinstance(reservations,dict) else {}
    files=ordered_files(state/'receipts','*.json')
    for p in files:
        if p.name.count('.')!=1:continue
        d=read(p,{})
        if not isinstance(d,dict):continue
        if d.get('runtime')!='openhands' or not isinstance(d.get('run_id'),str) or not 0<len(d['run_id'])<=80:continue
        if any(d.get(k) is not None and not isinstance(d[k],str) for k in ('unit','role','model')):continue
        usage=d.get('usage') or {}; context=read(p.with_suffix('.context.json'),{})
        running=d['run_id'] in reservations
        if running:
            path=Path(d.get('usage_path') if isinstance(d.get('usage_path'),str) else '').resolve()
            live=read(path,{}) if path.is_relative_to((home/'phpretro-ops/logs').resolve()) and path.name.endswith('.usage.json') else {}
            if isinstance(live,dict) and live.get('session_id')==d['run_id']:usage=live
        if not isinstance(usage,dict):usage={}
        if not isinstance(context,dict):context={}
        try:observed=context_usage.summary(context)
        except ValueError:observed={}
        context_requests=[]
        if observed:
            context_requests=[{k:r[k] for k in ('estimated_context_tokens','estimated_tool_schema_tokens','estimated_system_tokens')} for r in context['requests']]
        rows.append({'id':d['run_id'],'runtime':'openhands','unit':d.get('unit') or 'Unknown','unit_state':unit_states.get(d.get('unit'),'unknown'),'role':d.get('role') or 'Unknown','model':d.get('model') or 'Unknown',
          'provider':usage.get('provider'),'status':'running' if running else 'failed' if d.get('rc') not in (None,0) else 'succeeded' if d.get('status')=='complete' and d.get('rc')==0 else 'incomplete',
          'receipt_status':d.get('status'),'rc':d.get('rc'),
          'started':timestamp(d.get('ts_start')) or timestamp(d.get('prepared_at')),
          'ended':number(d.get('completed_at')),'tokens':number(usage.get('total_tokens')),
          'input':number(usage.get('input_tokens')),'output':number(usage.get('output_tokens')),
          'cached':number(usage.get('cache_read_tokens')),'requests':number(usage.get('api_calls')),
          'cache_write':number(usage.get('cache_write_tokens')),'reasoning':number(usage.get('reasoning_tokens')),
          'conservative_tokens':number(usage.get('conservative_tokens')),'unknown_requests':number(usage.get('unknown_api_calls')),
          'complete':usage.get('usage_complete') is True,
          'context':{k:number(observed.get(k)) for k in ('tool_calls','tool_errors','repeated_commands','events','brief_chars')},
          'context_complete':observed.get('usage_status')=='complete',
          'context_requests':context_requests,'unused_tools':observed.get('unused_tools',[]),
          'journal_available':p.with_suffix('.session.json').is_file() and not p.with_suffix('.session.json').is_symlink(),
          'optimization':optimization_metadata(context.get('optimization')),
          'reported_reasoning_tokens':number(context.get('reported_reasoning_tokens')) if context.get('reasoning_reports_complete') is True else None,
          'tool_output_chars':{k:number(context.get(k)) for k in ('original_tool_output_chars','sent_tool_output_chars','truncated_observations')},
          'resources':[{'name':'System prompt','kind':'instructions','required':True,'tokens':context_requests[0]['estimated_system_tokens'] if context_requests else None},
                       {'name':'Unit brief / full review diff and message envelope','kind':'instructions','required':True,'tokens':max(0,context_requests[0]['estimated_context_tokens']-context_requests[0]['estimated_system_tokens']-context_requests[0]['estimated_tool_schema_tokens']) if context_requests else None},
                       {'name':'Execute schema','kind':'tool','required':d.get('role')=='builder','tokens':context_requests[0]['estimated_tool_schema_tokens'] if context_requests else None}],
          'skills':{'activated':[],'invoked':[],'coverage':'The SDK runner disables automatic skill loading; unit instructions are supplied explicitly.'}})
        if len(rows)==500:break
    billing=read(state/'a6api-billing.json',{})
    if not isinstance(billing,dict):billing={}
    calls=billing.get('account_rows',billing.get('rows',[]))
    if not isinstance(calls,list):calls=[]
    safe_calls=[{k:(str(r.get(k,''))[:100] if k in ('request_id','model') else number(r.get(k))) for k in ('request_id','created_at','model','input_tokens_including_cache','cache_read_tokens','output_tokens','billed_usd')} for r in calls[:2000] if isinstance(r,dict)]
    rows+=native_sessions(home)
    if canvas:rows+=canvas.get('sessions',[])
    rows.sort(key=lambda r:r.get('started') or 0,reverse=True)
    supervisor=read(state/'codex-supervisor.json',{});supervisor=supervisor if isinstance(supervisor,dict) else {}
    runtimes=[{'id':'openhands','label':'OpenHands SDK builders and reviewers','state':'paused' if (home/'phpretro-ops/STOP').exists() else 'STOP absent; controller admission applies',
               'sessions':sum(r['runtime']=='openhands' for r in rows),'source':'Controller receipts, usage checkpoints, context observers and private event journals'},
              {'id':'openhands-ui','label':'OpenHands Web UI','state':'available' if canvas and canvas.get('available') else 'unavailable' if canvas else 'not collected',
               'sessions':sum(r['runtime']=='openhands-ui' for r in rows),'source':'Dedicated Canvas API metadata; full conversation viewer linked separately'},
              {'id':'codex','label':'Sol 6.1 native supervisor','state':supervisor.get('mode','disabled'),
               'sessions':sum(r['runtime']=='codex' for r in rows),'source':'Real native CLI jobs and retained subscription usage; actual Codex history is mounted read-only'},
              {'id':'doctor','label':'Skill Doctor analysis','state':'manual Deep Scan / local audit timer','sessions':None,'source':'Scan records page; A6API Sol high and embeddings. No automated Deep Scan.'},
              {'id':'a6api','label':'A6API account calls','state':'billing evidence','sessions':len(safe_calls),'source':'All account inference keys in the stated daily window; calls are not sessions'},
              {'id':'portdan','label':'Portdan fallback','state':'cash checks disabled by user','sessions':None,'source':'SDK receipts record fallback usage. No fabricated Portdan billing or prices.'}]
    return {'sessions':rows[:500],'provider_calls':safe_calls,'billing_collected_at':billing.get('collected_at'),
            'billing_scope':billing.get('account_rows_scope','coding key, today only'),
            'session_limit':500,'collected_at':time.time(),'runtimes':runtimes,'issues':findings(rows,units,billing,canvas),
            'evidence':'Older SDK conversation transcripts were not retained. New SDK timelines are bounded and redacted; completeness is explicit. Native and Canvas sessions retain their own identity. Provider calls are billing evidence, not sessions; costs must not be added twice.'}

#!/usr/bin/env python3
"""Actual human launcher, native tools/resume and real ledger in disposable state."""
import json,os,sys,tempfile,subprocess,uuid,time
from pathlib import Path

def child(folder,sid=None,mode=""):
 recover=mode=="recover"
 root=Path(__file__).resolve().parents[2];folder=Path(folder)
 os.environ.update(PHPRETRO_RUNTIME='claude-code',PHPRETRO_OPS=str(folder/'phpretro-ops'),PHPRETRO_REPO=str(root),RUNS_LOG=str(folder/'phpretro-ops/state/runs.jsonl'))
 sys.path.insert(0,str(root/'ops'))
 import runtime_policy,orchestrator,doctor_sessions
 from claude_code import interactive,gateway
 interactive.BASE=folder/'phpretro-claude-code';interactive.PROJECT=folder/'work/claude-project';interactive.PROJECT.mkdir(parents=True,exist_ok=True)
 orchestrator.ensure_dirs();runtime_policy.ready=lambda *a:True;interactive.validate_project=lambda *a:interactive.PROJECT
 # Explicit synthetic billing fixture, no provider requests: original cash
 # guard still requires fresh billing before resuming an unknown physical hold.
 orchestrator.billing.summary=lambda _: {'fresh':True,'day':orchestrator.now()[:10],'account_day_billed_usd':0.1,'account_balance_usd':100}
 gateway.credentials=lambda *a:{'a6api_api_key':'synthetic-only'}
 calls=[]
 prior=interactive.load_continuation(interactive.BASE/'terminal-home'/sid,sid) if sid else {}
 def upstream(endpoint,key,body,timeout):
  assert key=='synthetic-only';calls.append(body)
  if prior or len(calls)>1:assert any(item.get('type')=='reasoning' and item.get('encrypted_content')=='private-fixture-encrypted' for item in body['input'])
  if prior and len(calls)==1:assert any(item.get('type')=='reasoning' and item.get('encrypted_content')=='private-fixture-final-encrypted' for item in body['input'])
  items=[{'type':'reasoning','id':'rs_'+str(uuid.uuid4()),'encrypted_content':'private-fixture-encrypted','summary':[]},{'type':'function_call','call_id':'fixture_'+str(uuid.uuid4())+'_'+str(len(calls)),'name':'Bash','arguments':json.dumps({'command':'phpretro-doctor'})}] if len(calls)==1 else [{'type':'reasoning','id':'rs_final_'+str(uuid.uuid4()),'encrypted_content':'private-fixture-final-encrypted','summary':[]},{'type':'message','content':[{'type':'output_text','text':'TERMINAL_LIFECYCLE_OK'}]}]
  return {'status':'completed','model':interactive.MODEL,'output':items,'usage':{'input_tokens':100,'output_tokens':10,'total_tokens':110,'input_tokens_details':{'cached_tokens':0}}}
 Original=interactive.InteractiveGateway
 class Synthetic(Original):
  def __init__(self,*a,**k):super().__init__(*a,**k,invoke=upstream,routes=['a6api'])
 interactive.InteractiveGateway=Synthetic
 bindir=folder/'bin';bindir.mkdir(exist_ok=True);report=bindir/'phpretro-doctor';report.write_text('#!/bin/sh\nprintf terminal-lifecycle-fixture\n');report.chmod(0o755)
 original_env=interactive.environment
 def environment(*a):
  env=original_env(*a);env['PATH']=str(bindir)+':'+env['PATH'];return env
 interactive.environment=environment
 if mode=='prelaunch':
  import integrity
  sid=str(uuid.uuid4());claim=interactive.worker.claim
  interactive.worker.claim=lambda *a:(_ for _ in ()).throw(OSError('fixture crash before worker ownership'))
  try:
   try:interactive.launch(print_mode=True)
   except OSError:pass
  finally:interactive.worker.claim=claim
  records=list((orchestrator.STATE_DIR/'receipts').glob('*.json'));path=next(p for p in records if p.name.count('.')==1)
  rec=json.loads(path.read_text());sid=rec['native_session_id'];raw=json.loads(Path(rec['usage_path']).read_text())
  assert raw['session_id']==sid and raw['api_calls']==0 and raw['conservative_tokens']==0
  rec.update(worker_pid=99999999,worker_identity='missing');integrity.atomic_json(path,rec)
  orchestrator.settle_worker_receipts();orchestrator.write_json(orchestrator.STATE_JSON,orchestrator.load_state())
  assert interactive.prior_usage(runtime_policy.OPS,sid)==(True,0)
  print(json.dumps({'passed':True,'case':'pretransport-crash-recovery','native_session_id':sid,'charged_tokens':0,'physical_fixture_requests':0,'live_provider_calls':0}),flush=True);return
 if recover:
  import integrity,request_accounting
  state=orchestrator.load_state();rid=orchestrator.admit_paid(state,None,'interactive',limit=interactive.CONVERSATION_CAP)
  rec=dict(state['reservations'][rid]);usage=orchestrator.LOG_DIR/(rid+'.usage.json');path=orchestrator.STATE_DIR/'receipts'/(rid+'.json')
  raw=interactive.runner.zero(sid,interactive.MODEL,request_accounting.INTERACTIVE_CEILING)
  raw.update(usage_schema=request_accounting.INTERACTIVE_SCHEMA,interactive_token_budget=300000,provider='custom:a6api',estimated_cost_usd=0.1,cost_status='conservative-bound',api_calls=1,unknown_api_calls=1,unknown_request_ceilings=[100000],conservative_tokens=100000,usage_complete=False)
  rec.update(runtime='claude-code',profile='claude-interactive',model=interactive.MODEL,native_session_id=sid,status='running',profile_home=str(interactive.BASE/'terminal-home'/sid),cwd=str(interactive.PROJECT),usage_path=str(usage),prepared_at=time.time(),timeout=1800,worker_pid=99999999,worker_identity='missing')
  integrity.atomic_json(path,rec);integrity.atomic_json(usage,raw)
  orchestrator.settle_worker_receipts();orchestrator.write_json(orchestrator.STATE_JSON,orchestrator.load_state())
  fixed=json.loads(path.read_text());found,charged=interactive.prior_usage(runtime_policy.OPS,sid)
  assert fixed['status']=='complete' and fixed['recovered'] and fixed['rc']==130 and found and charged==100440
  print(json.dumps({'passed':True,'case':'orphan-recovery','native_session_id':sid,'charged_tokens':charged,'retained_unknown_hold':100000,'reservations':len(orchestrator.load_state()['reservations']),'live_provider_calls':0}),flush=True);return
 rc=interactive.launch(sid,prompt='/doctor' if not sid else 'Continue the same conversation.',print_mode=True)
 state=json.loads(orchestrator.STATE_JSON.read_text());rows=doctor_sessions.sessions(folder)['sessions']
 assert rc==0 and state['reservations']=={} and len(calls)==2
 records=[json.loads(p.read_text()) for p in (orchestrator.STATE_DIR/'receipts').glob('*.json') if p.name.count('.')==1]
 native=records[-1]['native_session_id'];found,used=interactive.prior_usage(runtime_policy.OPS,native)
 expected=220*sum(r.get('rc')==0 for r in records)+100000*int(any(r.get('usage',{}).get('unknown_api_calls')==1 for r in records))
 assert found and used==expected and state['tokens_today']==used
 recovered={r['run_id'] for r in records if r.get('recovered')}
 assert all(row['role']=='interactive' for row in rows)
 assert all(row['journal_available'] for row in rows if row['id'] not in recovered)
 assert all(not row['journal_available'] for row in rows if row['id'] in recovered)  # Seeded missing history remains unknown.
 print(json.dumps({'passed':True,'receipts':len(records),'native_session_id':native,'charged_tokens':used,'reservations':len(state['reservations']),'physical_fixture_requests':len(calls),'reasoning_continuation_observed':True,'live_provider_calls':0}),flush=True)

def run():
 with tempfile.TemporaryDirectory(prefix='phpretro-terminal-lifecycle-') as folder:
  sid=None
  for i in range(5):
   r=subprocess.run([sys.executable,__file__,'--child',folder,sid or '',*(['prelaunch'] if i==0 else ['recover'] if i==3 else [])],text=True,capture_output=True,timeout=90)
   rows=[]
   for line in r.stdout.splitlines():
    try:rows.append(json.loads(line))
    except ValueError:pass
   summary=next((r for r in reversed(rows) if r.get('passed') is True),None)
   if r.returncode or summary is None:raise AssertionError({'rc':r.returncode,'stderr':r.stderr[-1000:]})
   print(json.dumps(summary),flush=True);sid=summary['native_session_id']
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='--child':child(sys.argv[2],sys.argv[3] or None if len(sys.argv)>3 else None,sys.argv[4] if len(sys.argv)>4 else '')
 else:run()

#!/usr/bin/env python3
"""Actual human launcher, native tools/resume and real ledger in disposable state."""
import json,os,sys,tempfile,subprocess,uuid,time
from pathlib import Path

def child(folder,sid=None):
 root=Path(__file__).resolve().parents[2];folder=Path(folder)
 os.environ.update(PHPRETRO_RUNTIME='claude-code',PHPRETRO_OPS=str(folder/'phpretro-ops'),PHPRETRO_REPO=str(root),RUNS_LOG=str(folder/'phpretro-ops/state/runs.jsonl'))
 sys.path.insert(0,str(root/'ops'))
 import runtime_policy,orchestrator,doctor_sessions
 from claude_code import interactive,gateway
 interactive.BASE=folder/'phpretro-claude-code';interactive.PROJECT=folder/'work/claude-project';interactive.PROJECT.mkdir(parents=True,exist_ok=True)
 orchestrator.ensure_dirs();runtime_policy.ready=lambda *a:True
 gateway.credentials=lambda *a:{'a6api_api_key':'synthetic-only'}
 calls=[]
 def upstream(endpoint,key,body,timeout):
  assert key=='synthetic-only';calls.append(body)
  items=[{'type':'function_call','call_id':'fixture_'+str(len(calls)),'name':'Bash','arguments':json.dumps({'command':'phpretro-doctor'})}] if len(calls)==1 else [{'type':'message','content':[{'type':'output_text','text':'TERMINAL_LIFECYCLE_OK'}]}]
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
 rc=interactive.launch(sid,prompt='/doctor' if not sid else 'Continue the same conversation.',print_mode=True)
 state=json.loads(orchestrator.STATE_JSON.read_text());rows=doctor_sessions.sessions(folder)['sessions']
 assert rc==0 and state['reservations']=={} and len(calls)==2
 records=[json.loads(p.read_text()) for p in (orchestrator.STATE_DIR/'receipts').glob('*.json') if p.name.count('.')==1]
 native=records[-1]['native_session_id'];found,used=interactive.prior_usage(runtime_policy.OPS,native)
 assert found and used==220*len(records) and state['tokens_today']==used
 assert all(row['role']=='interactive' and row['journal_available'] for row in rows)
 print(json.dumps({'passed':True,'receipts':len(records),'native_session_id':native,'charged_tokens':used,'reservations':len(state['reservations']),'tool_calls':2,'live_provider_calls':0}),flush=True)

def run():
 with tempfile.TemporaryDirectory(prefix='phpretro-terminal-lifecycle-') as folder:
  sid=None
  for i in range(2):
   r=subprocess.run([sys.executable,__file__,'--child',folder,*([sid] if sid else [])],text=True,capture_output=True,timeout=90)
   rows=[]
   for line in r.stdout.splitlines():
    try:rows.append(json.loads(line))
    except ValueError:pass
   summary=next((r for r in reversed(rows) if r.get('passed') is True),None)
   if r.returncode or summary is None:raise AssertionError({'rc':r.returncode,'stderr':r.stderr[-1000:]})
   print(json.dumps(summary),flush=True);sid=summary['native_session_id']
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='--child':child(sys.argv[2],sys.argv[3] if len(sys.argv)>3 else None)
 else:run()

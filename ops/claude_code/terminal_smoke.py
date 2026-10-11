#!/usr/bin/env python3
"""Pinned native /doctor, conversation continuation and TUI startup, no provider calls."""
import json,os,subprocess,sys,tempfile,time,uuid,threading
from pathlib import Path
os.environ.setdefault('PHPRETRO_RUNTIME','claude-code')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from claude_code import interactive,gateway,runner
import runtime_policy,context_usage,session_journal

def run():
 with tempfile.TemporaryDirectory(prefix='claude-terminal-fixture-') as temp:
  home=Path(temp);sid=str(uuid.uuid4());project=home/'project';project.mkdir()
  interactive.initialize(home,project)
  policy=runtime_policy.load();total=runner.zero(sid,interactive.MODEL,64096);total.update(usage_schema=gateway.SCHEMA,unknown_request_ceilings=[])
  context=context_usage.Recorder(home/'context.json',list(interactive.TOOLS));journal=session_journal.Journal(home/'journal.json')
  manifest={'run_id':str(uuid.uuid4()),'_receipt_path':str(home/'receipt.json'),'role':'interactive','profile':'claude-interactive','prepared_at':time.time(),'timeout':120,'reserved_tokens':300000,'reserved_cost_estimate':1.0}
  seen=[]
  def upstream(endpoint,key,body,timeout):
   assert key=='fixture-only'
   seen.append({'tool_names':[t['name'] for t in body.get('tools',[])],'input_chars':len(json.dumps(body)),'doctor_text':'doctor' in json.dumps(body).lower()})
   return {'id':'response-fixture','model':interactive.MODEL,'status':'completed','output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'DOCTOR_TERMINAL_FIXTURE_OK'}]}],'usage':{'input_tokens':100,'output_tokens':10,'total_tokens':110,'input_tokens_details':{'cached_tokens':0},'output_tokens_details':{'reasoning_tokens':0}}}
  client=interactive.InteractiveGateway(policy,manifest,interactive.MODEL,total,lambda:None,journal,context,{'a6api_api_key':'fixture-only'},invoke=upstream,routes=['a6api']);client.interactive_lock=threading.Lock()
  env=interactive.environment(home,client)
  try:
   for index,prompt in enumerate(['/doctor','Continue with the retained conversation.']):
    command=interactive.native_command(home,sid,resume=index>0,prompt=prompt)+['-p','--verbose','--output-format','stream-json']
    r=subprocess.run(command,cwd=project,env=env,text=True,capture_output=True,timeout=80)
    events=[]
    for line in r.stdout.splitlines():
     try:events.append(json.loads(line))
     except ValueError:pass
    init=next((e for e in events if e.get('type')=='system' and e.get('subtype')=='init'),{})
    final=next((e for e in reversed(events) if e.get('type')=='result'),{})
    result={'case':'native-doctor' if index==0 else 'native-same-session-resume','rc':r.returncode,'doctor_available':'doctor' in init.get('slash_commands',[]),'tools':init.get('tools',[]),'same_session':init.get('session_id')==sid,'final_error':final.get('is_error'),'result_marker':'DOCTOR_TERMINAL_FIXTURE_OK' in final.get('result',''),'physical_requests':total['api_calls'],'guard':client.error_guard}
    print(json.dumps(result),flush=True)
    assert r.returncode==0 and result['result_marker'] and result['doctor_available'] and result['same_session'],result
   assert len(seen)==2 and seen[0]['doctor_text'] and total['total_tokens']==220
   import selectors,shlex,signal
   tui_sid=str(uuid.uuid4());total['session_id']=tui_sid;fresh_home=home/'fresh-terminal';interactive.initialize(fresh_home,project)
   tui_env=interactive.environment(fresh_home,client)
   args=interactive.native_command(fresh_home,tui_sid)
   tui=subprocess.Popen(['script','-q','-e','-c',shlex.join(args),'/dev/null'],cwd=project,env=tui_env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True)
   selector=selectors.DefaultSelector();selector.register(tui.stdout,selectors.EVENT_READ);screen=b'';sent=False;deadline=time.time()+25;started=time.time()
   try:
    while time.time()<deadline:
     for key,_ in selector.select(.2):
      data=os.read(key.fileobj.fileno(),65536)
      if not data:break
      screen+=data
     if not sent and time.time()-started>4:
      tui.stdin.write(b'/doctor\r');tui.stdin.flush();sent=True
     if len(seen)>2 and b'DOCTOR_TERMINAL_FIXTURE_OK' in screen:break
     if tui.poll() is not None:break
    flags={'case':'native-terminal-doctor','no_login_setup':b'Select login method' not in screen and b'How would you like to log in' not in screen,'no_theme_setup':b'Choose the text style' not in screen,'doctor_response':len(seen)>2 and b'DOCTOR_TERMINAL_FIXTURE_OK' in screen}
    print(json.dumps(flags),flush=True);assert all(flags[k] for k in ('no_login_setup','no_theme_setup','doctor_response')),flags
    tui.stdin.write(b'/exit\r');tui.stdin.flush()
    tui.wait(timeout=10)
   finally:
    selector.close()
    if tui.poll() is None:os.killpg(tui.pid,signal.SIGTERM);tui.wait(timeout=10)
   assert len(seen)==3 and total['total_tokens']==330
   interactive.transcript_observations(home,sid,context)
   assert 'doctor' in context.data['native_interactive']['invoked'],context.data['native_interactive']
   print(json.dumps({'passed':True,'cases':3,'live_provider_calls':0,'physical_fixture_requests':len(seen),'usage':330,'observed_doctor_invocation':True}),flush=True)
  finally:client.halted=True;client.close()
if __name__=='__main__':run()

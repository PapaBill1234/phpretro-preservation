import json,os,sys,tempfile,time,uuid,threading,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from claude_code import interactive,gateway,runner
import context_usage,session_journal,doctor_sessions,integrity

class TerminalTests(unittest.TestCase):
 def test_native_command_enables_doctor_without_weakening_worker_flags(self):
  with tempfile.TemporaryDirectory() as t:
   sid=str(uuid.uuid4());args=interactive.native_command(Path(t),sid)
   self.assertNotIn('--bare',args);self.assertNotIn('--disable-slash-commands',args)
   self.assertIn('--restricted',args);self.assertIn('high',args)
   self.assertEqual(args[0],str(interactive.RAW));self.assertIn(sid,args)
   from claude_code import command
   ordinary=command.command({'cli':'claude','model_roles':{'builder':'gpt-6-luna','reviewer':'gpt-6.1-sol'},'auth_mode':'gateway'},sid,Path(t)/'mcp','system',builder=True)
   self.assertIn('--bare',ordinary);self.assertIn('--disable-slash-commands',ordinary)
 def test_new_profile_initializes_only_own_config(self):
  with tempfile.TemporaryDirectory() as t:
   home=Path(t);config=interactive.initialize(home,home/'project')
   v=json.loads((config/'.claude.json').read_text());self.assertTrue(v['hasCompletedOnboarding'])
   (config/'.claude.json').write_text('{"retain":true}')
   interactive.initialize(home,home/'project');self.assertEqual(json.loads((config/'.claude.json').read_text()),{'retain':True})
 def test_environment_does_not_forward_host_provider_credentials(self):
  class Client:
   def environment(self):return {'ANTHROPIC_AUTH_TOKEN':'ephemeral-fixture','ANTHROPIC_BASE_URL':'http://127.0.0.1:1234'}
  with patch.dict(os.environ,{'A6API_API_KEY':'private-fixture','ANTHROPIC_API_KEY':'private-fixture'}):
   env=interactive.environment(Path('/tmp/profile'),Client())
  self.assertNotIn('A6API_API_KEY',env);self.assertNotIn('ANTHROPIC_API_KEY',env)
  self.assertNotIn('CLAUDE_CODE_DISABLE_POLICY_SKILLS',env)
 def test_default_adapter_still_rejects_native_tools_and_system_messages(self):
  body={'messages':[{'role':'system','content':'doctor'}],'tools':[]}
  with self.assertRaises(integrity.IntegrityError):gateway.chat_request(body,interactive.MODEL,{})
  body={'messages':[{'role':'user','content':'doctor'}],'tools':[{'name':'Bash','input_schema':{'type':'object'}}]}
  with self.assertRaises(integrity.IntegrityError):gateway.chat_request(body,interactive.MODEL,{})
  chat=gateway.chat_request(body,interactive.MODEL,{},gateway.INTERACTIVE_TOOLS,True)
  self.assertEqual(chat['tools'][0]['function']['name'],'Bash')
 def test_resume_preserves_conversation_charges_and_rejects_running_receipt(self):
  with tempfile.TemporaryDirectory() as t:
   ops=Path(t);receipts=ops/'state/receipts';receipts.mkdir(parents=True);sid=str(uuid.uuid4())
   usage=runner.zero(sid,interactive.MODEL,64096);usage.update(usage_schema=gateway.SCHEMA,total_tokens=150,conservative_tokens=150,api_calls=1,completed_api_calls=1,usage_known_calls=1,unknown_request_ceilings=[])
   p=receipts/(str(uuid.uuid4())+'.json');p.write_text(json.dumps({'profile':'claude-interactive','native_session_id':sid,'status':'complete','usage':usage}))
   self.assertEqual(interactive.prior_usage(ops,sid),(True,150))
   v=json.loads(p.read_text());v['status']='running';p.write_text(json.dumps(v))
   with self.assertRaises(integrity.IntegrityError):interactive.prior_usage(ops,sid)
 def test_real_invocation_markers_only_not_file_catalog(self):
  with tempfile.TemporaryDirectory() as t:
   home=Path(t);sid=str(uuid.uuid4());root=home/'.claude/projects/project';root.mkdir(parents=True)
   (root/(sid+'.jsonl')).write_text(json.dumps({'type':'user','uuid':str(uuid.uuid4()),'message':{'content':'<command-message>doctor</command-message><command-name>/doctor</command-name>'}})+'\n')
   context=context_usage.Recorder(home/'context.json',list(interactive.TOOLS))
   interactive.transcript_observations(home,sid,context)
   self.assertEqual(context.data['native_interactive']['invoked'],['doctor'])
   self.assertEqual(doctor_sessions.interactive_skills(context.data)['invoked'],['doctor'])
   self.assertEqual(doctor_sessions.interactive_skills({})['activated'],[])
 def test_doctor_collects_interactive_and_all_controlled_roles(self):
  with tempfile.TemporaryDirectory() as t:
   home=Path(t);state=home/'phpretro-ops/state';receipts=state/'receipts';receipts.mkdir(parents=True)
   roles=['builder','reviewer','interactive','reviewer']
   for i,role in enumerate(roles):
    rid=str(uuid.uuid4());profile='claude-interactive' if i==2 else 'claude-supervisor' if i==3 else 'unit'
    (receipts/(rid+'.json')).write_text(json.dumps({'run_id':rid,'runtime':'claude-code','role':role,'profile':profile,'model':interactive.MODEL,'status':'complete','rc':0,'prepared_at':time.time(),'usage':{'session_id':str(uuid.uuid4()),'total_tokens':10,'usage_complete':True}}))
   result=doctor_sessions.sessions(home);self.assertEqual(len(result['sessions']),4)
   self.assertEqual({r['role'] for r in result['sessions']},{'builder','reviewer','interactive','supervisor'})
   chat=next(r for r in result['sessions'] if r['role']=='interactive')
   self.assertEqual(chat['unit'],'Interactive');self.assertIn('Native interactive',chat['skills']['coverage'])
 def test_gateway_multi_turn_and_terminal_unknown_usage_stop(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);sid=str(uuid.uuid4());rid=str(uuid.uuid4())
   import runtime_policy
   policy=runtime_policy.load();total=runner.zero(sid,interactive.MODEL,64096);total.update(usage_schema=gateway.SCHEMA,unknown_request_ceilings=[])
   context=context_usage.Recorder(root/'context.json',list(interactive.TOOLS));journal=session_journal.Journal(root/'journal.json');snapshots=[]
   manifest={'run_id':rid,'_receipt_path':str(root/'receipt.json'),'role':'interactive','profile':'claude-interactive','prepared_at':time.time(),'timeout':30,'reserved_tokens':300000,'reserved_cost_estimate':1}
   def upstream(*args):return {'status':'completed','model':interactive.MODEL,'output':[{'type':'message','content':[{'type':'output_text','text':'ok'}]}],'usage':{'input_tokens':10,'output_tokens':2,'total_tokens':12,'input_tokens_details':{'cached_tokens':0}}}
   client=interactive.InteractiveGateway(policy,manifest,interactive.MODEL,total,lambda:snapshots.append(json.loads(json.dumps(total))),journal,context,{'a6api_api_key':'synthetic-fixture'},invoke=upstream,routes=['a6api']);client.interactive_lock=threading.Lock()
   body={'metadata':{'user_id':json.dumps({'session_id':sid})},'model':interactive.MODEL,'max_tokens':4096,'messages':[{'role':'system','content':'native doctor'},{'role':'user','content':'x'*70000}],'tools':[{'name':'Read','input_schema':{'type':'object'}}]}
   try:
    client.call(body);client.call(body)
    self.assertEqual(total['api_calls'],2);self.assertEqual(total['total_tokens'],24)
    self.assertFalse(snapshots[0]['usage_complete']);self.assertGreater(snapshots[0]['conservative_tokens'],64096)
    def exiting(*args):
     client.halted=True;raise gateway.ProviderError(503)
    client.invoke=exiting
    with self.assertRaises(Exception):client.call(body)
    self.assertTrue(client.halted);count=total['api_calls'];self.assertEqual(count,3)
    with self.assertRaises(integrity.IntegrityError):client.call(body)
    self.assertEqual(total['api_calls'],count);self.assertGreater(total['conservative_tokens'],24)
   finally:client.close()

 def test_native_identity_change_is_rejected_before_physical_attempt(self):
  client=object.__new__(interactive.InteractiveGateway)
  client.interactive_lock=threading.Lock();client.halted=False
  client.total={'session_id':str(uuid.uuid4()),'api_calls':0}
  with tempfile.TemporaryDirectory() as t,patch.object(interactive.runtime_policy,'OPS',Path(t)):
   body={'metadata':{'user_id':json.dumps({'session_id':str(uuid.uuid4())})},'tools':[]}
   with self.assertRaises(integrity.IntegrityError):client.call(body)
  self.assertTrue(client.halted);self.assertEqual(client.total['api_calls'],0)

 def test_headless_workers_delegate_to_pinned_binary_while_human_print_is_tracked(self):
  class Executed(Exception):pass
  with patch.object(interactive.os,'execv',side_effect=Executed) as execute,patch.dict(os.environ,{'ANTHROPIC_BASE_URL':'http://127.0.0.1:1234','ANTHROPIC_AUTH_TOKEN':'fixture'}):
   with self.assertRaises(Executed):interactive.main(['-p','--disable-slash-commands','worker'])
  self.assertEqual(execute.call_args.args[0],str(interactive.RAW))
  with patch.object(interactive,'launch',return_value=0) as launch,patch.dict(os.environ,{}):
   self.assertEqual(interactive.main(['-p','--output-format','json','hello']),0)
  launch.assert_called_once_with(None,'hello',True,'json')

 def test_large_unknown_physical_hold_is_projected_and_charged_only_for_interactive(self):
  import request_accounting,worker
  with tempfile.TemporaryDirectory() as t:
   sid=str(uuid.uuid4());row=runner.zero(sid,interactive.MODEL,request_accounting.INTERACTIVE_CEILING)
   row.update(usage_schema=request_accounting.INTERACTIVE_SCHEMA,interactive_token_budget=200000,api_calls=1,unknown_api_calls=1,unknown_request_ceilings=[100000],conservative_tokens=100000,usage_complete=False)
   self.assertEqual(request_accounting.bounded_tokens(row,0),100000)
   path=Path(t)/'usage.json';path.write_text(json.dumps(row))
   projected=worker.usage_snapshot(path,Path(t)/'missing','marker','claude-code')
   self.assertEqual(request_accounting.bounded_tokens(projected,0),100000)
   for override in ({'usage_schema':gateway.SCHEMA,'request_token_ceiling':64096},{'model':'gpt-6-luna'},{'interactive_token_budget':99999}):
    with self.assertRaises(integrity.IntegrityError):request_accounting.bounded_tokens({**row,**override},0)

 def test_malformed_transcript_containers_do_not_break_accounting_observer(self):
  with tempfile.TemporaryDirectory() as t:
   home=Path(t);sid=str(uuid.uuid4());root=home/'.claude/projects/project';root.mkdir(parents=True)
   values=[None,[],{'type':'user','uuid':'u','message':None},{'message':{'content':[{'type':'tool_use','name':'Skill','input':None}]}},{'type':'user','message':{'content':'<command-message>doctor</command-message><command-name>/doctor</command-name>'}},{'type':'assistant','message':{'content':'<command-message>quoted</command-message><command-name>/quoted</command-name>'}}]
   (root/(sid+'.jsonl')).write_text('\n'.join(json.dumps(v) for v in values))
   context=context_usage.Recorder(home/'context.json',list(interactive.TOOLS));journal=session_journal.Journal(home/'session.json')
   interactive.transcript_observations(home,sid,context,journal)
   self.assertEqual(context.data['native_interactive']['invoked'],['doctor'])

 def test_halted_terminal_denies_routing_retry_before_another_physical_attempt(self):
  client=object.__new__(interactive.InteractiveGateway);client.halted=True
  with self.assertRaises(InterruptedError):client.cancelled()

 def test_human_checkout_must_be_a_registered_separate_project_worktree(self):
  import subprocess
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'repo';root.mkdir();project=Path(t)/'human';other=Path(t)/'other';other.mkdir()
   subprocess.run(['git','init','-q',str(root)],check=True)
   subprocess.run(['git','-C',str(root),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--allow-empty','-qm','fixture'],check=True)
   subprocess.run(['git','-C',str(root),'worktree','add','-qb','codex/claude-human-terminal',str(project),'HEAD'],check=True)
   self.assertEqual(interactive.validate_project(project,root),project)
   for wrong in (root,other):
    with self.assertRaises(integrity.IntegrityError):interactive.validate_project(wrong,root)
   link=Path(t)/'linked';link.symlink_to(project,target_is_directory=True)
   with self.assertRaises(integrity.IntegrityError):interactive.validate_project(link,root)

 def test_prelaunch_recovery_can_start_same_uuid_but_missing_charged_history_is_denied(self):
  with tempfile.TemporaryDirectory() as t:
   home=Path(t);sid=str(uuid.uuid4())
   self.assertFalse(interactive.native_resume(home,sid,True,0))
   with self.assertRaises(integrity.IntegrityError):interactive.native_resume(home,sid,True,100)
   root=home/'.claude/projects/project';root.mkdir(parents=True);(root/(sid+'.jsonl')).write_text('{}')
   interactive.save_continuation(home,sid,{})
   self.assertTrue(interactive.native_resume(home,sid,True,100))

 def test_private_provider_continuation_is_bound_to_uuid_and_reloaded(self):
  with tempfile.TemporaryDirectory() as t:
   home=Path(t);sid=str(uuid.uuid4());value={'call_fixture':[{'type':'reasoning','id':'rs_fixture','encrypted_content':'private-fixture','summary':[]}]}
   interactive.save_continuation(home,sid,value)
   self.assertEqual(interactive.load_continuation(home,sid,required=True),value)
   with self.assertRaises(integrity.IntegrityError):interactive.load_continuation(home,str(uuid.uuid4()),required=True)
   (home/'provider-continuation.json').chmod(0o644)
   with self.assertRaises(integrity.IntegrityError):interactive.load_continuation(home,sid)

 def test_installer_restores_every_replaced_file_and_symlink_on_failure(self):
  with patch.dict(os.environ,{}):
   from claude_code import install_terminal
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);backup=root/'backup';backup.mkdir();raw=root/'raw';raw.write_text('native')
   cli=root/'claude';cli.symlink_to(raw);report=root/'report';report.write_text('old report');desktop=root/'desktop';desktop.write_text('old desktop')
   original=install_terminal.control.atomic_text
   def fail(path,text,*args,**kwargs):
    if path==desktop:raise OSError('fixture install failure')
    return original(path,text,*args,**kwargs)
   with patch.object(install_terminal.control,'atomic_text',side_effect=fail):
    with self.assertRaises(OSError):install_terminal.replace_files([(cli,'new cli',0o755),(report,'new report',0o755),(desktop,'new desktop',0o755)],backup)
   self.assertTrue(cli.is_symlink());self.assertEqual(cli.resolve(),raw)
   self.assertEqual(report.read_text(),'old report');self.assertEqual(desktop.read_text(),'old desktop')

 def test_unmanaged_native_history_in_terminal_profiles_remains_unknown(self):
  from claude_code import native_sessions
  with tempfile.TemporaryDirectory() as t:
   home=Path(t);sid=str(uuid.uuid4());profile=str(uuid.uuid4())
   root=home/'phpretro-claude-code/terminal-home'/profile/'.claude/projects/project';root.mkdir(parents=True)
   row={'sessionId':sid,'cwd':str(home/'work/claude-project'),'type':'assistant','timestamp':time.time(),'message':{'id':'msg','model':'gpt-6.1-sol','usage':None}}
   (root/(sid+'.jsonl')).write_text('malformed\n'+json.dumps({'sessionId':sid,'cwd':row['cwd'],'type':'assistant','message':None})+'\n'+json.dumps(row)+'\n')
   result=native_sessions.collect(home,set());self.assertEqual(len(result),1)
   self.assertEqual(result[0]['native_session_id'],sid);self.assertIsNone(result[0]['tokens']);self.assertFalse(result[0]['complete'])
   self.assertEqual(native_sessions.collect(home,{sid}),[])

if __name__=='__main__':unittest.main()

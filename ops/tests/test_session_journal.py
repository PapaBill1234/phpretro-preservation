import json,tempfile,unittest,uuid
from pathlib import Path
import session_journal as j
import doctor_sessions as d
import doctor_canvas as canvas

class JournalTest(unittest.TestCase):
 def test_secrets_are_removed_and_private_timeline_stays_bounded(self):
  with tempfile.TemporaryDirectory() as root:
   path=Path(root)/'timeline.json';journal=j.Journal(path,['actual-private-key'])
   journal.add('tool','actual-private-key Authorization=Bearer private-value\nsk-1234567890abcdefgh\nordinary output',rc=1)
   journal.finish(True);text=path.read_text()
   for secret in ('actual-private-key','private-value','sk-1234567890abcdefgh'):self.assertNotIn(secret,text)
   self.assertIn('ordinary output',text);self.assertTrue(json.loads(text)['complete'])
   journal.add('assistant','x'*4001);journal.finish(True)
   self.assertFalse(journal.data['complete']);self.assertTrue(journal.data['truncated'])
   self.assertEqual(path.stat().st_mode&0o777,0o600)
 def test_timeline_identity_and_symlink_do_not_escape_receipts(self):
  with tempfile.TemporaryDirectory() as root:
   home=Path(root);receipts=home/'phpretro-ops/state/receipts';receipts.mkdir(parents=True)
   identity=str(uuid.uuid4());journal=j.Journal(receipts/(identity+'.session.json'))
   journal.add('assistant','safe');journal.finish(True)
   self.assertEqual(d.journal(identity,home)['events'][0]['text'],'safe')
   self.assertIsNone(d.journal('../private/auth',home))
   path=receipts/(str(uuid.uuid4())+'.session.json');path.symlink_to(receipts/(identity+'.session.json'))
   self.assertIsNone(d.journal(path.name.split('.')[0],home))
 def test_canvas_never_exports_agents_registry_or_workspaces(self):
  row=canvas.normalize({'id':str(uuid.uuid4()),'execution_status':'running','current_model_id':'sol',
    'agent':{'llm':{'api_key':'secret'}},'secret_registry':'secret','workspace':'private-path',
    'metrics':{'accumulated_token_usage':{'prompt_tokens':10,'completion_tokens':4,'cache_read_tokens':2}},
    'activated_knowledge_skills':['one'],'invoked_skills':['one']})
  self.assertEqual(row['tokens'],14);self.assertFalse(row['complete'])
  self.assertNotIn('secret',json.dumps(row));self.assertNotIn('private-path',json.dumps(row))
 def test_live_usage_and_issues_come_from_scoped_checkpoints(self):
  with tempfile.TemporaryDirectory() as root:
   home=Path(root);ops=home/'phpretro-ops';receipts=ops/'state/receipts';receipts.mkdir(parents=True);(ops/'logs').mkdir()
   identity=str(uuid.uuid4());usage=ops/'logs/test.usage.json'
   usage.write_text(json.dumps({'session_id':identity,'total_tokens':99,'usage_complete':False}))
   (receipts/(identity+'.json')).write_text(json.dumps({'runtime':'openhands','run_id':identity,'unit':'F1','role':'builder','model':'sol','status':'running','usage_path':str(usage)}))
   (ops/'state/units.state.json').write_text(json.dumps({'reservations':{identity:{}}}))
   context={'schema':'phpretro.context-usage.v1','complete':False,'enabled_tools':['execute'],'tool_calls':2,'tool_errors':1,'repeated_commands':1,'events':4,'brief_chars':4,'requests':[{'estimated_context_tokens':50,'estimated_tool_schema_tokens':8,'estimated_system_tokens':10}]}
   (receipts/(identity+'.context.json')).write_text(json.dumps(context))
   report=d.sessions(home,canvas={'available':True,'sessions':[]})
   self.assertEqual(report['sessions'][0]['tokens'],99);self.assertEqual(report['sessions'][0]['status'],'running')
   self.assertTrue(any(i['title']=='Tool executions returned errors' for i in report['issues']))
   self.assertTrue(any(i['title']=='Repeated commands consumed context' for i in report['issues']))
   self.assertEqual(len(report['runtimes']),6)

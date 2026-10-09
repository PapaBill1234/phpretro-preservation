import json,tempfile,unittest
from pathlib import Path
import doctor_sessions as d
class SessionsTest(unittest.TestCase):
 def test_receipts_are_not_codex_sessions_or_transcripts(self):
  with tempfile.TemporaryDirectory() as directory:
   home=Path(directory);state=home/'phpretro-ops/state';(state/'receipts').mkdir(parents=True)
   (state/'receipts/test.json').write_text(json.dumps({'runtime':'openhands','run_id':'test','role':'builder','model':'sol','prompt':'secret','usage':{'total_tokens':30,'usage_complete':False}}))
   (state/'receipts/test.context.json').write_text(json.dumps({'tool_calls':0,'complete':False,'command':'secret'}))
   (state/'a6api-billing.json').write_text(json.dumps({'account_rows':[{'request_id':'call','model':'sol','secret':'secret'}],'account_rows_scope':'all today'}))
   report=d.sessions(home);self.assertEqual(len(report['sessions']),1)
   self.assertFalse(report['sessions'][0]['context_complete']);self.assertEqual(report['sessions'][0]['tokens'],30)
   self.assertNotIn('secret',json.dumps(report));self.assertEqual(len(report['provider_calls']),1)
 def test_empty_history_stays_empty(self):
  with tempfile.TemporaryDirectory() as home:self.assertEqual(d.sessions(home)['sessions'],[])
 def test_truncated_context_never_claims_complete_or_unused(self):
  with tempfile.TemporaryDirectory() as directory:
   home=Path(directory);receipts=home/'phpretro-ops/state/receipts';receipts.mkdir(parents=True)
   (receipts/'test.json').write_text(json.dumps({'runtime':'openhands','run_id':'test'}))
   (receipts/'test.context.json').write_text(json.dumps({'schema':'phpretro.context-usage.v1','complete':True,'requests_truncated':True,'enabled_tools':['execute'],'tool_calls':1,'tool_errors':0,'repeated_commands':0,'events':2,'brief_chars':10,'requests':[{'estimated_context_tokens':20,'estimated_tool_schema_tokens':3,'estimated_system_tokens':4,'secret':'secret'}]}))
   row=d.sessions(home)['sessions'][0]
   self.assertFalse(row['context_complete']);self.assertNotIn('secret',json.dumps(row))
   self.assertEqual(row['context_requests'][0]['estimated_context_tokens'],20)

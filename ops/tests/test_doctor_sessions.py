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

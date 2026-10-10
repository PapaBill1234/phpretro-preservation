import json,tempfile,unittest
from pathlib import Path
import context_usage as c

class ContextUsageTests(unittest.TestCase):
    def test_counts_without_conversation_content(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'report.json'; r=c.Recorder(path)
            r.request(100,80,20); r.tool('private-command'); r.tool('private-command');r.finish(True)
            text=path.read_text(); self.assertNotIn('private-command',text)
            s=c.summary(json.loads(text)); self.assertEqual(s['repeated_commands'],1)
            self.assertEqual(s['peak_tool_schema_tokens'],20);self.assertEqual(s['unused_tools'],[])
    def test_unused_requires_complete_observed_requests(self):
        with tempfile.TemporaryDirectory() as d:
            r=c.Recorder(Path(d)/'report.json');r.finish(True)
            self.assertEqual(c.summary(r.data)['unused_tools'],[])
            r.request(100,80,20);r.finish(False)
            self.assertEqual(c.summary(r.data)['unused_tools'],[])
            r.finish(True); self.assertEqual(c.summary(r.data)['unused_tools'],['execute'])
    def test_bounded_history_and_invalid_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            r=c.Recorder(Path(d)/'report.json')
            for _ in range(130):r.request(100,80,20)
            r.finish(True);self.assertEqual(c.summary(r.data)['usage_status'],'partial')
            self.assertEqual(len(r.data['requests']),128)
            r.data['tool_calls']=True
            with self.assertRaises(ValueError):c.summary(r.data)
    def test_tool_free_review_is_complete_without_unused_execute(self):
        with tempfile.TemporaryDirectory() as d:
            r=c.Recorder(Path(d)/'report.json',enabled_tools=[])
            r.request(100,100,20);r.finish(True)
            s=c.summary(r.data)
            self.assertEqual(s['usage_status'],'complete')
            self.assertEqual(s['unused_tools'],[])
            self.assertEqual(s['peak_tool_schema_tokens'],0)
            r.data['tool_calls']=1
            with self.assertRaises(ValueError):c.summary(r.data)

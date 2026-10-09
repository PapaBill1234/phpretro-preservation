import json, tempfile, unittest
from pathlib import Path
import skill_doctor as s
from unittest.mock import patch
from types import SimpleNamespace

class SkillDoctorTests(unittest.TestCase):
    def test_public_report_is_metadata_only(self):
        with tempfile.TemporaryDirectory() as directory:
            ops=Path(directory); (ops/'state').mkdir()
            raw={'schema':'phpretro.skill-doctor.v1','checked_at':1,'secret':'private',
                 'audits':[{'id':'project','estimated_tokens':100,'items':2,'sourcePath':'private','text':'private'},
                           {'id':'unknown','estimated_tokens':1,'items':1},
                           {'id':'supervisor','estimated_tokens':True,'items':1}]}
            (ops/'state/skill-doctor.json').write_text(json.dumps(raw))
            result=s.public_summary(ops)
            self.assertEqual(result['audits'],[{'id':'project','estimated_tokens':100,'items':2}])
            self.assertNotIn('private',json.dumps(result))
    def test_missing_or_corrupt_report_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            ops=Path(directory); (ops/'state').mkdir()
            self.assertFalse(s.public_summary(ops)['available'])
            (ops/'state/skill-doctor.json').write_text('{}')
            self.assertFalse(s.public_summary(ops)['available'])
    def test_collector_invocation_is_isolated_and_does_not_scan_mcp(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(s,'BASE',Path(directory)), patch.object(s.control,'atomic_json'), patch.object(s.subprocess,'run') as run, patch.dict(s.os.environ,{'API_KEY':'private'}):
            run.return_value=SimpleNamespace(stdout=json.dumps({'summary':{'totalEstimatedTokens':12},'items':[]}))
            self.assertEqual(s.cost(Path(directory),'project')['estimated_tokens'],12)
            args=run.call_args.args[0]; env=run.call_args.kwargs['env']
            self.assertEqual(args[args.index('--source')+1],'skill')
            self.assertEqual(args[args.index('--scope')+1],'project')
            self.assertNotIn('API_KEY',env)
            self.assertEqual(env['HOME'],str(Path(directory)/'audit-home'))

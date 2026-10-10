import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import harness
import integrity
from claude_code import probe
from claude_code.probe import model_plan

class ProbeScopeTests(unittest.TestCase):
    def setUp(self):
        self.data={'models':{'gpt-6-luna':{'automatic':True},'deepseek-v4.1-flash':{'automatic':True},'gpt-6.1-sol':{'automatic':True},'retired':{'automatic':False}}}
        self.old={'implementation_sha256':'source','attempted':True,'models':{'gpt-6-luna':{'usage':True},'deepseek-v4.1-flash':{'usage':False}}}
    def test_unattempted_sol_is_explicit_without_repeating_failed_deepseek(self):
        self.assertEqual(model_plan(self.data,'source',self.old,'gpt-6.1-sol'),['gpt-6.1-sol'])
        for selected in (None,'gpt-6-luna','deepseek-v4.1-flash'):
            with self.subTest(selected=selected),self.assertRaises(integrity.IntegrityError):model_plan(self.data,'source',self.old,selected)
    def test_a_prepared_attempt_cannot_be_reused_without_a_result(self):
        old={**self.old,'attempted_models':['gpt-6.1-sol']}
        with self.assertRaises(integrity.IntegrityError):model_plan(self.data,'source',old,'gpt-6.1-sol')
    def test_unknown_legacy_attempt_scope_and_retired_models_fail_closed(self):
        with self.assertRaises(integrity.IntegrityError):model_plan(self.data,'source',{**self.old,'models':{}},'gpt-6.1-sol')
        for model in ('retired','unknown'):
            with self.subTest(model=model),self.assertRaises(integrity.IntegrityError):model_plan(self.data,'source',{},model)
    def test_new_source_is_a_new_scope_without_mutating_old_evidence(self):
        self.assertEqual(model_plan(self.data,'new-source',self.old,'gpt-6.1-sol'),['gpt-6.1-sol'])
        self.assertEqual(list(self.old['models']),['gpt-6-luna','deepseek-v4.1-flash'])
    def test_attempt_finished_before_lock_is_not_repeated(self):
        with tempfile.TemporaryDirectory() as directory:
            ops=Path(directory);(ops/'locks').mkdir();(ops/'state/receipts').mkdir(parents=True)
            destination=ops/'state/claude-code-provider.json'
            initial={**self.old,'models':{'gpt-6-luna':{'usage':True}}}
            destination.write_text(json.dumps(initial))
            latest={**initial,'attempted_models':['gpt-6-luna','gpt-6.1-sol'],'models':{**initial['models'],'gpt-6.1-sol':{'usage':False}}}
            def acquire(*args):destination.write_text(json.dumps(latest))
            with patch.object(probe.runtime_policy,'OPS',ops),patch.object(probe.runtime_policy,'load',return_value=self.data),patch.object(probe.runtime_policy,'fingerprint',return_value='source'),patch.object(probe.policy,'bootstrap_ready',return_value=True),patch.object(probe.fcntl,'flock',side_effect=acquire),patch.object(probe.controller,'load_state',return_value={}),patch.object(probe.controller,'hermes_run') as run,patch.object(probe.sys,'argv',['probe.py','--run','--model','gpt-6.1-sol']):
                with self.assertRaises(integrity.IntegrityError):probe.main()
                run.assert_not_called()
            self.assertEqual(json.loads(destination.read_text()),latest)

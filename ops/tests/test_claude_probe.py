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
        for settings in self.data['models'].values():settings['provider_order']=['a6api','portdan']
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
    def test_distinct_fallback_attempt_preserves_failed_primary_and_cannot_repeat(self):
        self.assertEqual(model_plan(self.data,'source',self.old,'deepseek-v4.1-flash','portdan'),['deepseek-v4.1-flash'])
        old={**self.old,'attempted_routes':['a6api:deepseek-v4.1-flash','portdan:deepseek-v4.1-flash']}
        for provider in ('a6api','portdan'):
            with self.subTest(provider=provider),self.assertRaises(integrity.IntegrityError):model_plan(self.data,'source',old,'deepseek-v4.1-flash',provider)
        self.assertFalse(self.old['models']['deepseek-v4.1-flash']['usage'])
    def test_unknown_or_unconfigured_routes_and_fallback_batches_fail_closed(self):
        for provider in ('unconfigured','portdan'):
            with self.subTest(provider=provider),self.assertRaises(integrity.IntegrityError):model_plan(self.data,'source',{},None,provider)
        old={**self.old,'attempted_routes':['unknown:deepseek-v4.1-flash']}
        with self.assertRaises(integrity.IntegrityError):model_plan(self.data,'source',old,'deepseek-v4.1-flash','portdan')
        self.data['models']['deepseek-v4.1-flash']['provider_order']=['a6api']
        with self.assertRaises(integrity.IntegrityError):model_plan(self.data,'source',{},'deepseek-v4.1-flash','portdan')
    def test_controller_rejects_ordinary_provider_selector_before_reservation(self):
        with patch.object(probe.controller.runtime_policy,'model_settings',return_value=self.data['models']['deepseek-v4.1-flash']),patch.object(probe.controller,'admit_paid') as admit:
            rc,_,usage=probe.controller.hermes_run('builder','deepseek-v4.1-flash','fixture','',Path('.'),'fixture',30,role='builder',state={},unit='F61',bootstrap_provider='portdan')
            self.assertEqual(rc,75);self.assertTrue(usage['admission_denied']);self.assertEqual(usage['api_calls'],0);admit.assert_not_called()
    def test_successful_fallback_retains_failed_primary_and_charges_actual_run(self):
        import contextlib,io
        with tempfile.TemporaryDirectory() as directory:
            ops=Path(directory);(ops/'locks').mkdir();(ops/'state/receipts').mkdir(parents=True)
            destination=ops/'state/claude-code-provider.json';destination.write_text(json.dumps(self.old))
            usage={'run_id':'fixture','usage_complete':True,'session_id':'native-fixture','provider':'custom:portdan','model':'deepseek-v4.1-flash','total_tokens':42}
            with patch.object(probe.runtime_policy,'OPS',ops),patch.object(probe.runtime_policy,'load',return_value={**self.data,'cli_version':'fixture'}),patch.object(probe.runtime_policy,'fingerprint',return_value='source'),patch.object(probe.policy,'bootstrap_ready',return_value=True),patch.object(probe.controller,'load_state',return_value={'tokens_today':100}),patch.object(probe.controller,'hermes_run',return_value=(0,'',usage)) as run,patch.object(probe.controller,'read_json',return_value={'tool_calls':1,'tool_errors':0}),patch.object(probe.controller,'write_json') as write,patch.object(probe.sys,'argv',['probe.py','--run','--model','deepseek-v4.1-flash','--provider','portdan']),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(probe.main(),0)
                self.assertEqual(run.call_args.kwargs['bootstrap_provider'],'portdan')
                self.assertEqual(write.call_args.args[1]['tokens_today'],142)
            row=json.loads(destination.read_text())
            self.assertFalse(row['route_attempts']['a6api:deepseek-v4.1-flash']['usage'])
            self.assertTrue(row['route_attempts']['portdan:deepseek-v4.1-flash']['usage'])
            self.assertTrue(row['provider_models']['portdan']['deepseek-v4.1-flash']['usage'])
            self.assertEqual(row['attempted_routes'].count('portdan:deepseek-v4.1-flash'),1)
            with self.assertRaises(integrity.IntegrityError):model_plan(self.data,'source',row,'deepseek-v4.1-flash','portdan')
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

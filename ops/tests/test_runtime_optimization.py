import harness
import json
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
import runtime_optimization as opt
import doctor_sessions


class RuntimeOptimizationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.row = {'id': str(uuid.uuid4()), 'runtime': 'openhands', 'unit': 'F61',
                    'role': 'reviewer', 'model': 'deepseek-v4.1-flash',
                    'provider': 'custom:a6api', 'started': time.time()-100,
                    'status': 'succeeded', 'rc': 0, 'complete': True,
                    'context_complete': True, 'context': {}, 'tokens': 120,'requests':1,
                    'input': 80, 'cached': 10, 'cache_write': 0, 'output': 30,
                    'reasoning': 20, 'reported_reasoning_tokens': 20}
        self.report = {'sessions': [self.row]}

    def preview(self):
        return opt.preview(self.row['id'], 'reviewer-thinking', True, self.home, self.report)

    def apply(self):
        preview = self.preview()
        return opt.apply(preview['id'], preview['confirmation'], self.home)

    def test_manual_preview_apply_verify_and_undo_with_no_inference(self):
        self.assertFalse(opt.load(self.home)['values']['reviewer-thinking'])
        preview = self.preview()
        self.assertFalse(opt.load(self.home)['values']['reviewer-thinking'])
        operation = opt.apply(preview['id'], preview['confirmation'], self.home)
        self.assertTrue(opt.load(self.home)['values']['reviewer-thinking'])
        self.assertEqual(opt.verify(operation['id'], self.home, self.report)['status'], 'pending')
        newer = {**self.row, 'id':str(uuid.uuid4()), 'started':time.time()+1,
                 'reported_reasoning_tokens':0, 'optimization':opt.snapshot(self.home)}
        result = opt.verify(operation['id'], self.home, {'sessions':[newer]})
        self.assertEqual(result['status'], 'observed')
        self.assertIsNone(result['measured_savings'])
        opt.undo(operation['id'], self.home)
        self.assertFalse(opt.load(self.home)['values']['reviewer-thinking'])
        self.assertEqual(opt.verify(operation['id'],self.home,self.report)['status'],'restored')

    def test_stale_preview_and_wrong_confirmation_do_not_write_settings(self):
        one, two = self.preview(), self.preview()
        with self.assertRaises(ValueError):opt.apply(one['id'],'wrong',self.home)
        opt.apply(one['id'],one['confirmation'],self.home)
        with self.assertRaises(ValueError):opt.apply(two['id'],two['confirmation'],self.home)

    def test_interrupted_apply_retains_durable_undo_and_does_not_leak_extra_settings(self):
        preview=self.preview();atomic=opt.control.atomic_json;operation_writes=0
        def fail_last_record(path,data):
            nonlocal operation_writes
            if path.name.endswith('.operation.json'):
                operation_writes+=1
                if operation_writes==2:raise OSError('Injected interruption')
            return atomic(path,data)
        with patch.object(opt.control,'atomic_json',side_effect=fail_last_record):
            with self.assertRaises(OSError):opt.apply(preview['id'],preview['confirmation'],self.home)
        self.assertTrue(opt.load(self.home)['values']['reviewer-thinking'])
        operation=opt.operations(self.home)[0]
        self.assertEqual(operation['status'],'prepared')
        opt.undo(operation['id'],self.home)
        settings=opt.base(self.home)/'settings.json';raw=json.loads(settings.read_text());raw['unrelated']='NEVER_PUBLIC';atomic(settings,raw)
        self.assertFalse(opt.load(self.home)['values']['reviewer-thinking'])
        self.assertNotIn('NEVER_PUBLIC',json.dumps(opt.overview(self.home,self.report)))

    def test_conflicting_undo_cannot_overwrite_newer_operator_change(self):
        one = self.apply()
        other = opt.preview(self.row['id'],'reviewer-thinking',False,self.home,self.report)
        opt.apply(other['id'],other['confirmation'],self.home)
        with self.assertRaises(ValueError):opt.undo(one['id'],self.home)
        self.assertFalse(opt.load(self.home)['values']['reviewer-thinking'])

    def test_preview_is_bound_to_source_and_expires_without_changing_settings(self):
        preview = self.preview()
        with patch.object(opt,'source_digest',return_value='changed'):
            with self.assertRaises(ValueError):opt.apply(preview['id'],preview['confirmation'],self.home)
        with patch.object(opt.time,'time',return_value=preview['expires_at']+1):
            with self.assertRaises(ValueError):opt.apply(preview['id'],preview['confirmation'],self.home)
        self.assertFalse(opt.load(self.home)['values']['reviewer-thinking'])

    def test_role_model_runtime_and_id_boundaries(self):
        for row in [{**self.row,'runtime':'codex'},{**self.row,'role':'builder'},
                    {**self.row,'model':'gpt-6.1-sol'}]:
            with self.assertRaises(ValueError):opt.preview(row['id'],'reviewer-thinking',True,self.home,{'sessions':[row]})
        with self.assertRaises(ValueError):opt.preview('../../secrets','reviewer-thinking',True,self.home,self.report)
        with self.assertRaises(ValueError):opt.preview(self.row['id'],'remove-acceptance',True,self.home,self.report)

    def test_partial_or_omitted_reasoning_evidence_cannot_verify_effect(self):
        operation = self.apply()
        row = {**self.row,'started':time.time()+1,'optimization':opt.snapshot(self.home)}
        result=opt.verify(operation['id'],self.home,{'sessions':[{**row,'reported_reasoning_tokens':None}]})
        self.assertEqual(result['status'],'effect-unverified')
        result=opt.verify(operation['id'],self.home,{'sessions':[{**row,'complete':False,'rc':1}]})
        self.assertEqual(result['status'],'observed-partial')
        result=opt.verify(operation['id'],self.home,{'sessions':[{**row,'requests':0,'reported_reasoning_tokens':0}]})
        self.assertEqual(result['status'],'effect-unverified')

    def test_compaction_keeps_beginning_end_and_explicit_marker(self):
        text='HEAD_ERROR'+('x'*20000)+'TAIL_ERROR'
        compact=opt.compact_output(text,True)
        self.assertLessEqual(len(compact),8192)
        self.assertTrue(compact.startswith('HEAD_ERROR'));self.assertTrue(compact.endswith('TAIL_ERROR'))
        self.assertIn('truncated',compact)
        self.assertEqual(opt.compact_output(text,False),text)
        self.assertEqual(opt.compact_output('short',True),'short')

    def test_quotes_do_not_double_count_cache_or_provider_calls(self):
        with patch('runtime_policy.model_settings',return_value={'input':1,'output':2,'cache_read':.1,'cache_write':1}):
            result=opt.overview(self.home,self.report)
        self.assertAlmostEqual(result['sessions'][0]['cost']['usd'],141/1e6)
        for provider in ('custom:portdan','mixed:a6api-portdan','ChatGPT subscription'):
            self.assertIsNone(opt.costs({**self.row,'provider':provider})['usd'])
        self.assertIsNone(opt.costs({**self.row,'input':None})['usd'])
        with patch('runtime_policy.model_settings',return_value={'input':1,'output':2,'cache_read':.1,'cache_write':1}):
            self.assertIn('excludes unknown calls',opt.costs({**self.row,'complete':False,'unknown_requests':1})['basis'])

    def test_private_settings_and_symlink_guards(self):
        root=opt.base(self.home);root.mkdir(parents=True,mode=0o700)
        outside=self.home/'outside';outside.write_text('{}')
        (root/'settings.json').symlink_to(outside)
        with self.assertRaises(ValueError):opt.load(self.home)

    def test_outcome_is_separate_from_receipt_lifecycle_and_metadata_is_whitelisted(self):
        receipts=self.home/'phpretro-ops/state/receipts';receipts.mkdir(parents=True)
        identity=self.row['id']
        (receipts/(identity+'.json')).write_text(json.dumps({'runtime':'openhands','run_id':identity,'status':'complete','rc':1,'model':'deepseek-v4.1-flash','role':'reviewer','usage':{'total_tokens':120,'reasoning_tokens':30}}))
        (receipts/(identity+'.context.json')).write_text(json.dumps({'optimization':{**opt.snapshot(self.home),'secret':'NEVER_PUBLIC'}}))
        row=doctor_sessions.sessions(self.home)['sessions'][0]
        self.assertEqual(row['status'],'failed');self.assertEqual(row['receipt_status'],'complete')
        self.assertIsNone(row['reported_reasoning_tokens'])
        self.assertNotIn('NEVER_PUBLIC',json.dumps(row))

    def test_unknown_dates_and_empty_period_do_not_claim_zero_usage(self):
        report=opt.overview(self.home,{'sessions':[{**self.row,'started':None}]})
        self.assertEqual(report['sessions'],[])
        self.assertIn('Missing counters remain unknown',report['evidence'])


if __name__=='__main__':unittest.main()

import copy,json,unittest
from unittest.mock import Mock,patch
from test_maintenance import Isolated,unit,state
import orchestrator as o
import planner_stage as p
import throughput as t

class Staging(Isolated):
    def setUp(self):
        super().setUp()
        (self.repo/'docs/roadmap').mkdir(parents=True)
        (self.repo/'docs/roadmap/spec.md').write_text('Approved observable behavior: correct behavior.\n')
        self.parent=unit('P',status='design',model='',design_doc='docs/roadmap/spec.md',severity='high')
        self.road={'P':self.parent};self.st=state()
    def plan(self,**changes):
        args={'model':'','fixtures':['docs/roadmap/spec.md'],'acceptance':['correct behavior'],'tests':['go test ./internal/x']}
        args.update(changes);new=unit('Pa',**args)
        return 'units:\n'+o.dump_unit_yaml({k:v for k,v in new.items() if k!='model'})
    def launch(self,out=None,rc=0,usage=None):
        out=self.plan() if out is None else out
        usage={'total_tokens':7,'api_calls':1,'completed':True} if usage is None else usage
        def spawn(cmd,**kw):
            self.assertEqual(cmd[cmd.index('--reasoning')+1],'low')
            o.control.atomic_json(o.Path(cmd[cmd.index('--usage-file')+1]),usage)
            kw['stdout'].write(out);kw['stdout'].flush()
            return Mock(wait=Mock(return_value=rc))
        with patch.object(p.subprocess,'Popen',side_effect=spawn): return p.start(o,self.road,self.st)
    def test_proposal_cannot_mutate_board_and_only_one_planner(self):
        before=copy.deepcopy(self.road);job=self.launch()
        self.assertEqual(self.road,before);self.assertEqual(self.st['tokens_today'],0)
        self.assertIsNone(p.start(o,self.road,self.st))
        self.assertEqual(p.finish(o,job,self.road,self.st),'applied')
        self.assertEqual(self.road['Pa']['severity'],'high')
        self.assertFalse(self.st['reservations']);self.assertEqual(self.st['tokens_today'],7)
    def test_build_lifecycle_progress_does_not_stale_contract(self):
        self.road['B']=unit('B',paths=['internal/b'],status='building')
        job=self.launch();self.road['B'].update(status='merged',tokens=123,attempts=1)
        self.assertEqual(p.finish(o,job,self.road,self.st),'applied')
        self.assertEqual(self.road['B']['tokens'],123)
    def test_topology_change_rejects_once_and_preserves_ids(self):
        job=self.launch();self.road['B']=unit('B',paths=['internal/b'],status='merged')
        self.assertEqual(p.finish(o,job,self.road,self.st),'stale')
        self.assertNotIn('Pa',self.road);self.assertEqual(self.parent['planner_retries'],1)
        self.assertFalse(p.targets(o,self.road))
    def test_changed_source_rejects(self):
        job=self.launch();(self.repo/'docs/roadmap/spec.md').write_text('Changed acceptance')
        self.assertEqual(p.finish(o,job,self.road,self.st),'stale');self.assertNotIn('Pa',self.road)
    def test_deleted_source_rejects_and_retains_spend(self):
        job=self.launch();(self.repo/'docs/roadmap/spec.md').unlink()
        self.assertEqual(p.finish(o,job,self.road,self.st),'stale');self.assertNotIn('Pa',self.road)
        self.assertEqual(self.st['tokens_today'],7);self.assertFalse(self.st['reservations'])
    def test_dispatch_receipt_failure_drains_planner_before_settlement(self):
        with patch.object(o,'process_event',side_effect=OSError('metadata unavailable')):
            job=self.launch()
            with self.assertRaises(o.control.IntegrityError): p.finish(o,job,self.road,self.st)
        self.assertTrue(o.STOP_FILE.exists());self.assertNotIn('Pa',self.road)
        self.assertFalse(self.st['reservations']);self.assertEqual(self.st['tokens_today'],7)
    def test_stop_between_prepare_and_apply_keeps_gate(self):
        job=self.launch();o.STOP_FILE.touch()
        self.assertEqual(p.finish(o,job,self.road,self.st),'STOP');self.assertNotIn('Pa',self.road)
        self.assertEqual(self.st['tokens_today'],7)
    def test_caps_admission_never_spawns(self):
        for key,value in [('tokens_today',o.DAILY_TOKEN_CAP),('merged_today',o.MAX_MERGE_PER_DAY)]:
            self.st[key]=value
            with patch.object(p.subprocess,'Popen',side_effect=AssertionError('worker launch denied')): self.assertIsNone(p.start(o,self.road,self.st))
            self.st=state()
    def test_current_cap_prevents_proposal_apply(self):
        job=self.launch();self.st['merged_today']=o.MAX_MERGE_PER_DAY
        self.assertEqual(p.finish(o,job,self.road,self.st),'rejected');self.assertNotIn('Pa',self.road)
    def test_provider_fault_consumes_spend_not_retry(self):
        job=self.launch('API HTTP error 502',rc=1)
        self.assertEqual(p.finish(o,job,self.road,self.st),'provider_error')
        self.assertEqual(self.parent.get('planner_retries',0),0);self.assertEqual(self.parent['status'],'design')
        self.assertEqual(self.st['tokens_today'],7);self.assertEqual(self.st['provider_errors'],1)
    def test_missing_usage_has_conservative_charge(self):
        job=self.launch('bad output',usage={})
        p.finish(o,job,self.road,self.st)
        self.assertEqual(self.st['tokens_today'],o.TIMEOUT_FALLBACK_TOKENS)
    def test_evidence_and_overlapping_paths_rejected_atomically(self):
        for changes in ({'fixtures':['docs/roadmap/missing.md']},{'fixtures':[]},{'paths':['ops/x.py']}):
            self.setUp_case=copy.deepcopy(self.road)
            job=self.launch(self.plan(**changes));self.assertEqual(p.finish(o,job,self.road,self.st),'rejected')
            self.assertNotIn('Pa',self.road)
            self.parent['planner_retries']=0;self.parent['status']='design'
        self.road['B']=unit('B',status='building')
        job=self.launch();self.assertEqual(p.finish(o,job,self.road,self.st),'rejected');self.assertNotIn('Pa',self.road)
    def test_missing_parent_source_is_not_a_ready_plan(self):
        self.parent['design_doc']='docs/roadmap/missing.md'
        self.assertFalse(p.targets(o,self.road))
    def test_reserved_acceptance_and_adapter_gaps_do_not_invent_scope(self):
        for uid in ('F31','F38'):
            self.parent['id']=uid;self.road={uid:self.parent}
            self.assertFalse(p.targets(o,self.road))
    def test_exhausted_parent_does_not_block_other_planning(self):
        self.parent['tokens']=o.PER_UNIT_TOKEN_CAP
        self.road['Q']=unit('Q',status='design',model='',paths=['internal/q'],design_doc='docs/roadmap/spec.md')
        job=self.launch();self.assertEqual(job['target']['id'],'Q')
        p.finish(o,job,self.road,self.st)
    def test_buffer_target_eight_and_disjoint_count(self):
        for i in range(8):
            self.road[str(i)]=unit(str(i),paths=[f'internal/a{i}'],fixtures=['docs/roadmap/spec.md'],tests=['go test ./...'],acceptance=['correct behavior'])
        self.assertEqual(len(t.ready_buffer(self.road,self.repo,o.PER_UNIT_TOKEN_CAP)),8)
        self.assertFalse(p.targets(o,self.road))
        self.road['7']['paths']=['internal/a0/x.go']
        self.assertEqual(len(t.ready_buffer(self.road,self.repo,o.PER_UNIT_TOKEN_CAP)),7)
        self.assertTrue(p.targets(o,self.road))
    def test_permanent_guard_refusal_and_depth_bound(self):
        self.parent.update(status='parked',reason='protected-path guard refusal')
        self.assertFalse(p.targets(o,self.road))
        self.parent.update(status='design',reason='',planner_depth=2)
        self.assertFalse(p.targets(o,self.road))
    def test_two_rejections_clear_split_deadlock_without_raising_attempt_cap(self):
        self.parent.update(status='todo',split_requested=True,planner_retries=1,attempts=2)
        job=self.launch('bad output')
        self.assertEqual(p.finish(o,job,self.road,self.st),'rejected')
        self.assertFalse(self.parent['split_requested']);self.assertEqual(self.parent['status'],'todo');self.assertEqual(self.parent['attempts'],2)

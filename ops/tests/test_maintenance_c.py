import json,time,unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from test_maintenance import Isolated,unit,state
import orchestrator as o
import planner_stage as p
import telemetry as tel

class RoleLaunches(Isolated):
    def test_effective_reasoning_telemetry_for_each_role(self):
        u=unit(paths=['internal/session']);st=state()
        def worker(cmd,**kw):
            o.control.atomic_json(o.Path(cmd[cmd.index('--usage-file')+1]),{'total_tokens':7,'api_calls':1,'completed':True})
            return 0,'done'
        for profile,role,expected in [('builder','builder','medium'),('reviewer','reviewer','medium'),('planner','planner','low'),('auditor','audit','medium')]:
            with patch.object(o,'sh',side_effect=worker) as run:
                o.hermes_run(profile,o.MODEL['sol'],'PRIVATE PROMPT','file',self.repo,'mocked',1,role=role,state=st,budget_unit=u)
            self.assertEqual(run.call_args.args[0][run.call_args.args[0].index('--reasoning')+1],expected)
        records=o.control.ledger_records(o.STATE_DIR)
        completed=[r for r in records if r.get('record_type')=='run']
        self.assertEqual([r['reasoning'] for r in completed],['medium','medium','low','medium'])
        self.assertNotIn('PRIVATE PROMPT',(o.STATE_DIR/'process-events.jsonl').read_text())
    def test_changed_job_counter_does_not_change_launch_policy(self):
        u=unit(model_override=o.MODEL['deepseek']);st=state()
        with patch.object(o,'ensure_worktree',return_value=self.repo),patch.object(o.subprocess,'Popen',side_effect=OSError('worker unavailable')) as launch:
            with self.assertRaises(OSError): o.start_build(u,st,{'X':u})
        cmd=launch.call_args.args[0]
        self.assertEqual(cmd[cmd.index('-m')+1],o.MODEL['luna'])
        self.assertEqual(cmd[cmd.index('--reasoning')+1],'medium')
        self.assertFalse(st['reservations'])
    def test_legacy_high_risk_deepseek_author_gets_other_family(self):
        self.assertEqual(o.reviewer_model_for(o.MODEL['deepseek'],unit(paths=['internal/session'])),o.MODEL['sol'])
    def test_sync_dispatch_receipt_failure_never_launches_and_releases(self):
        u=unit();st=state()
        with patch.object(o,'process_event',side_effect=OSError('metadata unavailable')),patch.object(o,'sh') as worker:
            with self.assertRaises(o.control.IntegrityError):
                o.hermes_run('reviewer',o.MODEL['deepseek'],'prompt','file',self.repo,'review',1,state=st,budget_unit=u)
        worker.assert_not_called();self.assertTrue(o.STOP_FILE.exists());self.assertFalse(st['reservations'])
        self.assertEqual(o.control.accounting(o.control.ledger_records(o.STATE_DIR),st['day'],o.TIMEOUT_FALLBACK_TOKENS)['tokens_today'],0)
    def test_sync_completion_receipt_failure_retains_usage_and_entire_board(self):
        u=unit();st=state();o.save_roadmap({'X':u,'Y':unit('Y')})
        def worker(cmd,**kw):
            o.control.atomic_json(o.Path(cmd[cmd.index('--usage-file')+1]),{'total_tokens':7,'api_calls':1,'completed':True})
            return 0,'done'
        with patch.object(o,'process_event',side_effect=[None,OSError('metadata unavailable')]),patch.object(o,'sh',side_effect=worker):
            with self.assertRaises(o.control.IntegrityError):
                o.hermes_run('reviewer',o.MODEL['deepseek'],'prompt','file',self.repo,'review',1,state=st,budget_unit=u)
        self.assertTrue(o.STOP_FILE.exists());self.assertFalse(st['reservations']);self.assertEqual(st['tokens_today'],7)
        self.assertEqual({row['id'] for row in o.parse_yaml(o.LIVE_UNITS.read_text())['units']},{'X','Y'})
    def test_integrity_failure_drains_all_already_running_builders(self):
        a=unit('A',paths=['internal/a']);b=unit('B',paths=['internal/b'])
        jobs=[{'unit':a},{'unit':b}]
        with patch.object(o,'select_ready',return_value=[a,b]),patch.object(o,'start_build',side_effect=jobs),patch.object(p,'start',return_value=None),patch.object(o,'finish_build',side_effect=[o.control.IntegrityError('receipt failed'),None]) as finish:
            with self.assertRaises(o.control.IntegrityError): o.dispatch({'A':a,'B':b},state())
        self.assertEqual(finish.call_count,2);self.assertTrue(jobs[1]['metadata_error']);self.assertTrue(o.STOP_FILE.exists())
    def test_no_concurrent_same_path_builders(self):
        a=unit('A',paths=['internal/x']);b=unit('B',paths=['internal/x/sub.go'])
        with patch.object(o,'select_ready',return_value=[a,b]),patch.object(o,'start_build',return_value={'unit':a}) as start,patch.object(o,'finish_build'),patch.object(p,'start',return_value=None):
            o.dispatch({'A':a,'B':b},state())
        self.assertEqual(start.call_count,1);self.assertIs(start.call_args.args[0],a)
    def test_completion_receipt_failure_stops_without_losing_usage(self):
        u=unit(attempts=1);st=state();rid=o.admit_paid(st,u,'builder')
        usage=o.LOG_DIR/'builder.usage.json';usage.write_text('{"total_tokens":7,"api_calls":1,"completed":true}')
        observer=SimpleNamespace(join=Mock(side_effect=RuntimeError('receipt unavailable')),rc=0,ended=10,ended_wall=time.time())
        job={'unit':u,'proc':Mock(),'started':time.time(),'started_mono':0,'observer':observer,'usage':usage,
             'logfile':Mock(),'wt':self.repo,'ts_start':o.now(),'run_id':rid}
        with patch.object(o,'_publish_attempt') as publish:
            with self.assertRaises(o.control.IntegrityError): o.finish_build(job,{'X':u},st)
        publish.assert_not_called();self.assertTrue(o.STOP_FILE.exists())
        self.assertFalse(st['reservations']);self.assertEqual(st['tokens_today'],7)

class Recovery(Isolated):
    def test_merge_queue_never_rewrites_remote_history_and_keeps_gates(self):
        u=unit('X',pr=1,attempts=1)
        with patch.object(o,'git',return_value=(0,'')) as git,patch.object(o,'git_out',side_effect=lambda *a,**k:'same-head' if a[0]=='rev-parse' else ''),patch.object(o,'run_check',return_value=(0,'passed')) as check,patch.object(o,'quality_gate',return_value={'ok':False}) as quality,patch.object(o,'ensure_reviewed') as review:
            self.assertFalse(o.merge_queue(u,self.repo,state()))
        self.assertIn(('merge','--no-edit','origin/main'),[c.args for c in git.call_args_list])
        self.assertFalse(any('force' in str(c.args) for c in git.call_args_list))
        check.assert_called_once();quality.assert_called_once();review.assert_not_called()
    def test_diverged_history_merged_before_all_gates(self):
        u=unit('F38',attempts=2);st=state()
        def command(*args,**kw): return (1,'diverged') if args[0]=='merge-base' else (0,'')
        def value(*args,**kw): return '4' if args[0]=='rev-list' else ''
        with patch.object(o,'git',side_effect=command) as git,patch.object(o,'git_out',side_effect=value),patch.object(o,'attach_worktree',return_value=self.repo),patch.object(o,'run_check',return_value=(0,'passed')) as check,patch.object(o,'record_history'),patch.object(o,'push_and_open_pr',return_value=99):
            self.assertTrue(o.recover_branch(u,{},st))
        self.assertIn(('merge','--no-edit','refs/remotes/origin/unit/F38'),[c.args for c in git.call_args_list])
        self.assertFalse(any('force' in str(c.args) for c in git.call_args_list));check.assert_called_once()
        self.assertEqual(u['attempts'],2)
    def test_conflict_and_dirty_checkout_preserve_history_no_push(self):
        for dirty in ('','M internal/x/x.go'):
            u=unit('F38',attempts=2)
            def command(*args,**kw): return (0,'') if args[:2]==('merge','--abort') or args[0]=='fetch' else (1,'conflict')
            def value(*args,**kw): return '4' if args[0]=='rev-list' else dirty if args[0]=='status' else ''
            with patch.object(o,'git',side_effect=command),patch.object(o,'git_out',side_effect=value),patch.object(o,'attach_worktree',return_value=self.repo),patch.object(o,'push_and_open_pr') as push,patch.object(o,'run_check') as check:
                self.assertTrue(o.recover_branch(u,{},state()))
            push.assert_not_called();check.assert_not_called()
            self.assertEqual(u['status'],'parked');self.assertEqual(u['attempts'],2)

class Metadata(unittest.TestCase):
    def test_planning_bounds_and_stale_revision_survive_serialization(self):
        u=unit(planner_root='ROOT',planner_depth=2,planner_stale_revision='revision')
        restored=o.parse_yaml('units:\n'+o.dump_unit_yaml(u))['units'][0]
        for key in ('planner_root','planner_depth','planner_stale_revision'):
            self.assertEqual(restored[key],u[key])
    def test_usage_does_not_store_prompt_or_transcript(self):
        usage={'total_tokens':7,'model':'gpt-6-luna','messages':[{'content':'PRIVATE'}],'prompt':'PRIVATE','request':{'Authorization':'PRIVATE'}}
        safe=tel.safe_usage(usage)
        self.assertEqual(safe,{'total_tokens':7,'model':'gpt-6-luna'})
    def test_cache_tariff_missing_never_claims_total_cost(self):
        prices={'gpt-6-luna':{'input':.018,'output':.09}}
        self.assertIsNone(tel.estimate_cost({'model':'gpt-6-luna','input_tokens':1,'output_tokens':1,'cache_read_tokens':1000},prices))

if __name__=='__main__': unittest.main()

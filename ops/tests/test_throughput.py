import subprocess,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from harness import tmpdir
import throughput as t
import orchestrator as o

class ModelPolicy(unittest.TestCase):
    def test_ordinary_attempts_and_fourth(self):
        u={'paths':['frontend/src/theme.ts'],'title':'theme view'}
        self.assertEqual([o.builder_model(u,a) for a in range(1,5)],[o.MODEL['luna']]*3+[o.MODEL['sol']])
    def test_sensitive_paths_and_behavior_use_sol_from_first(self):
        for path in ('internal/account/a.go','internal/session/a.go','internal/cache/a.go','internal/audit/a.go','migrations/a.sql','internal/server/a.go'):
            self.assertEqual(o.builder_model({'paths':[path]},1),o.MODEL['sol'],path)
        for title in ('durable replay','password reset','Redis contract','SSRF fix'):
            self.assertEqual(o.builder_model({'paths':['internal/x'],'title':title},1),o.MODEL['sol'],title)
    def test_role_reasoning_and_review_independence(self):
        self.assertEqual(t.reasoning('builder'),'medium')
        self.assertEqual(t.reasoning('audit'),'medium')
        self.assertEqual(t.reasoning('planner',{'paths':['internal/auth']}),'low')
        self.assertEqual(t.reasoning('reviewer',{'paths':['internal/auth']}),'medium')
        self.assertEqual(t.reasoning('reviewer',{},'diff --git a/internal/session/x.go b/internal/session/x.go'),'medium')
        self.assertNotEqual(o.reviewer_model_for(o.MODEL['sol']),o.MODEL['sol'])
    def test_authflow_and_frontend_security_paths_are_high_risk_without_title_hints(self):
        for path in ('internal/authflow/flow.go','internal/registration/form.go','internal/recovery/reset.go',
                     'frontend/src/auth.ts','frontend/src/sessionStore.ts','internal/x/storage.go'):
            u={'paths':[path],'title':'view wiring'}
            self.assertEqual(o.builder_model(u,1),o.MODEL['sol'],path)
            self.assertEqual(t.reasoning('reviewer',u),'medium',path)
        self.assertEqual(t.reasoning('reviewer',{},'diff --git a/frontend/src/auth.ts b/frontend/src/auth.ts'),'medium')
    def test_qa_priority_is_severity_not_id(self):
        items=[{'id':'F1','severity':'medium'},{'id':'QA3','severity':'high'},{'id':'F2','severity':'critical'}]
        self.assertEqual([u['id'] for u in sorted(items,key=t.priority)],['F2','QA3','F1'])
    def test_brief_prefix_identical_and_constraints_retained(self):
        a=o.builder_brief({'id':'A','title':'first'},1,o.MODEL['luna'],'repair')
        b=o.builder_brief({'id':'B','title':'second'},4,o.MODEL['sol'],'other')
        self.assertEqual(a.split('UNIT BRIEF')[0],b.split('UNIT BRIEF')[0])
        for text in ('scripts/check.sh','Never edit AGENTS.md','Coverage','fidelity: guessed','Polaris','Compile errors','Never ask questions'):
            self.assertIn(text,a)
        self.assertIn('unit(A):',a);self.assertIn('docs/units/A.md',a)
    def test_overlap_strings_globs_and_directory_paths(self):
        self.assertTrue(t.overlap(['internal/a'], 'internal/a/x.go'))
        self.assertTrue(t.overlap(['internal/a/*.go'],['internal/a/x.go']))
        self.assertFalse(t.overlap(['internal/a/x.go'],['internal/a/y.go']))

class CompletionEvidence(unittest.TestCase):
    def test_deadline_from_dispatch_even_when_observer_starts_late(self):
        proc=Mock();proc.wait.return_value=0
        calls=[]
        result=t.Completion(proc,10,25,Mock(),calls.append,clock=lambda:20,wall=lambda:100)
        result.observe()
        proc.wait.assert_called_once_with(timeout=15)
        self.assertEqual(result.ended,20);self.assertEqual(calls,[result])
    def test_absolute_deadline_timeout_uses_existing_timeout_handler(self):
        proc=Mock();proc.wait.side_effect=subprocess.TimeoutExpired('worker',1)
        kill=Mock();result=t.Completion(proc,10,25,kill,Mock(),clock=lambda:40,wall=lambda:100)
        result.observe();proc.wait.assert_called_once_with(timeout=.01);kill.assert_called_once_with(proc)
        self.assertEqual(result.rc,124)
    def test_receipt_failure_visible(self):
        result=t.Completion(Mock(wait=Mock(return_value=0)),0,25,Mock(),Mock(side_effect=OSError('disk')),clock=lambda:1)
        result.observe();self.assertIsInstance(result.error,OSError)
    def test_occupancy_ignores_late_publication_and_deliveries_deduplicate(self):
        def e(ts,kind,**kw): return {'ts':t.iso(ts),'kind':kind,**kw}
        rows=[e(0,'process_dispatched',role='builder',unit='A',run_id='1'),e(10,'process_dispatched',role='builder',unit='B',run_id='2'),e(20,'process_completed',role='builder',run_id='1'),e(30,'process_completed',role='builder',run_id='2'),e(120,'merged',unit='A'),e(150,'merged',unit='A')]
        m=t.metrics(rows,0,200)
        self.assertEqual(m['average_builders'],.2)
        self.assertEqual(m['median_minutes_per_merged_unit'],2)
        self.assertEqual(m['timed_merged_units'],1)
        self.assertIsNone(t.metrics([],0,200)['average_builders'])

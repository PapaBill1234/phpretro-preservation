"""Subscription supervision: no network, authentication files or model calls."""
import contextlib
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch
from harness import tmpdir
import codex_account as a
import codex_supervisor as s
import integrity


def account():
    return {'authenticated':True,'model_available':True,'quota':{'available':True,
        'ordinary_allowed':True,'blocked':False,'primary':{'used_percent':10,'duration_minutes':300,'resets_at':int(time.time()+600)},
        'secondary':{'used_percent':80,'duration_minutes':10080,'resets_at':int(time.time()+600)}}}


class QuotaTests(unittest.TestCase):
    def test_limits_never_infer_permission_or_redeem_credits(self):
        for used in (90,95,100):
            state=account(); state['quota']['primary']['used_percent']=used
            self.assertFalse(a.allowed(state))
            state=account(); state['quota']['secondary']['used_percent']=used
            self.assertFalse(a.allowed(state))
        for key in ('ordinary_allowed','available'):
            state=account(); state['quota'][key]=False; self.assertFalse(a.allowed(state))
        state=account(); state['quota']['primary']['resets_at']=0; self.assertFalse(a.allowed(state))
        self.assertTrue(a.allowed(account()))

    def test_unknown_windows_and_non_codex_buckets_fail_closed(self):
        self.assertFalse(a.sanitize_limits({'rateLimitsByLimitId':{}})['available'])
        self.assertFalse(a.sanitize_limits({'rateLimits':{'limitId':'other'}})['available'])
        for value in (True,-1,101,'10',None):
            self.assertIsNone(a.window({'usedPercent':value,'windowDurationMins':300,'resetsAt':1}))

    def test_env_never_inherits_provider_keys_or_api_billing(self):
        with patch.dict(os.environ,{'CODEX_API_KEY':'secret','OPENAI_API_KEY':'secret','A6API_API_KEY':'secret','OPENAI_BASE_URL':'bad'}):
            environment=a.environment()
        for key in ('CODEX_API_KEY','OPENAI_API_KEY','A6API_API_KEY','OPENAI_BASE_URL'): self.assertNotIn(key,environment)


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.root=tmpdir('subscription-supervisor-')
        self.ops=self.root/'ops'; (self.ops/'state').mkdir(parents=True)
        self.base=self.root/'native'; self.base.mkdir()
        self.state=self.ops/'state/codex-supervisor.json'
        self.enabled=self.base/'ENABLED'
        self.facts={'stop':False,'pipeline_active':True,'controller_active':False,
            'state_valid':True,'reservations':0,'workers':0,'issues':['billing_stale']}
        self.stack=contextlib.ExitStack(); self.addCleanup(self.stack.close)
        for key,value in (('OPS',self.ops),('BASE',self.base),('STATE',self.state),('ENABLED',self.enabled)):
            self.stack.enter_context(patch.object(s,key,value))
        self.stack.enter_context(patch.dict(os.environ,{'INVOCATION_ID':'synthetic'}))
        self.stack.enter_context(patch.object(s.runtime_policy,'ready',return_value=True))
        self.read=self.stack.enter_context(patch.object(a,'read_account',return_value=account()))
        self.snap=self.stack.enter_context(patch.object(s,'snapshot',side_effect=lambda:dict(self.facts)))
        self.real_decide=s.decide
        self.decide=self.stack.enter_context(patch.object(s,'decide',return_value=({'action':'restart_billing','reason':'billing_stale'},{})))
        self.execute=self.stack.enter_context(patch.object(s,'execute',return_value=0))
        self.stack.enter_context(patch.object(s.subprocess,'check_output',return_value=s.VERSION))

    def status(self): return json.loads(self.state.read_text())
    def enable(self): self.enabled.touch()

    def test_disabled_and_inspect_never_run_model_or_repairs(self):
        s.cycle(); self.assertEqual(self.status()['mode'],'disabled'); self.read.assert_not_called()
        self.enable(); s.cycle(inspect=True); self.decide.assert_not_called(); self.execute.assert_not_called()

    def test_stop_inactive_and_healthy_never_run_model(self):
        self.enable()
        for updates,mode in (({'stop':True},'paused'),({'stop':False,'pipeline_active':False},'paused'),
                             ({'pipeline_active':True,'issues':[]},'healthy')):
            self.facts.update(updates); s.cycle(); self.assertEqual(self.status()['mode'],mode)
        self.decide.assert_not_called()

    def test_auth_quota_or_source_failure_defers_without_model(self):
        self.enable()
        for value in (False,True):
            state=account(); state['quota']['available']=value; state['quota']['secondary']['used_percent']=90
            self.read.return_value=state; s.cycle(); self.assertEqual(self.status()['mode'],'deferred')
        self.read.return_value=account()
        with patch.object(s.runtime_policy,'ready',return_value=False): s.cycle()
        self.assertEqual(self.status()['reason'],'validation_required'); self.decide.assert_not_called()

    def test_daily_cap_and_cooldown_preserve_attempt_records(self):
        self.enable()
        for attempts,reason in (([time.time()-100],'cooldown'),([time.time()-30000,time.time()-25000],'daily_limit')):
            integrity.atomic_json(self.state,{'schema':'phpretro.codex-supervisor.v1','attempts':attempts,'history':[]})
            s.cycle(); self.assertEqual(self.status()['reason'],reason); self.assertEqual(self.status()['attempts'],attempts)
        self.decide.assert_not_called()

    def test_corrupt_state_never_resets_repair_budget(self):
        self.enable(); self.state.write_text('{broken')
        with self.assertRaises(integrity.IntegrityError): s.cycle()
        self.assertEqual(self.state.read_text(),'{broken'); self.decide.assert_not_called()

    def test_supported_repair_is_verified_after_execution(self):
        self.enable()
        def execute(_): self.facts['issues']=[]; return 0
        self.execute.side_effect=execute
        s.cycle(); self.execute.assert_called_once_with('restart_billing')
        self.assertEqual(self.status()['mode'],'repaired'); self.assertEqual(len(self.status()['history']),1)

    def test_stop_created_during_decision_prevents_action(self):
        self.enable()
        def decide(*_): self.facts['stop']=True; return {'action':'restart_billing','reason':'billing_stale'},{}
        self.decide.side_effect=decide
        s.cycle(); self.execute.assert_not_called()

    def test_unrelated_action_and_low_disk_cannot_execute(self):
        before=dict(self.facts)
        self.assertFalse(s.eligible_action('start_controller',before,before))
        self.assertFalse(s.eligible_action('delete_state',before,before))
        current={**before,'issues':['billing_stale','disk_pressure']}
        self.assertFalse(s.eligible_action('restart_billing',before,current))
        self.assertTrue(s.eligible_action('restart_billing',before,{**before,'controller_active':True,'workers':2}))

    def test_public_metadata_never_contains_private_output_or_account_ids(self):
        secret='PRIVATE_SENTINEL'
        integrity.atomic_json(self.state,{'mode':'disabled','enabled':False,'reason':secret,
            'account':{'authenticated':True,'email':secret,'accountId':secret,'quota':account()['quota']},
            'history':[{'at':1,'mode':'repaired','reason':'repair_complete','action':'restart_billing',
                        'raw_log':secret,'input_tokens':123,'output_tokens':True}], 'job':{'prompt':secret}})
        public=s.public_summary(self.ops)
        self.assertNotIn(secret,json.dumps(public)); self.assertEqual(public['reason'],'unavailable')
        self.assertEqual(public['history'][0]['input_tokens'],123); self.assertNotIn('output_tokens',public['history'][0])

    def test_malformed_public_account_fields_cannot_break_dashboard(self):
        for value in (None,[],{'quota':{'primary':'bad','secondary':False}}):
            integrity.atomic_json(self.state,{'account':value,'history':None})
            self.assertEqual(s.public_summary(self.ops)['history'],[])

    def test_real_subprocess_decision_uses_private_logs_and_no_api_key_env(self):
        self.enable()
        cli=self.base/'synthetic-cli'
        cli.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
args=sys.argv[1:]
assert args[0]=='exec' and args[args.index('-m')+1]=='gpt-6.1-sol'
assert args[args.index('--sandbox')+1]=='read-only'
for feature in ('shell_tool','unified_exec','multi_agent','hooks'):
    assert any(args[i:i+2]==['--disable',feature] for i in range(len(args)))
assert 'OPENAI_API_KEY' not in os.environ and 'CODEX_API_KEY' not in os.environ
pathlib.Path(args[args.index('-o')+1]).write_text(json.dumps({'action':'restart_billing','reason':'billing_stale'}))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':321,'cached_input_tokens':100,'output_tokens':21}}))
''')
        cli.chmod(0o700)
        data={'attempts':[]}; saved=[]
        # Exercise the real function rather than the cycle's mocked decision.
        with patch.object(a,'CLI',cli):
            result,usage=self.real_decide(self.facts,data,lambda:saved.append(json.loads(json.dumps(data))))
        self.assertEqual(result['action'],'restart_billing'); self.assertEqual(usage['input_tokens'],321)
        self.assertEqual(data['job']['status'],'complete'); self.assertEqual(len(data['attempts']),1)
        self.assertTrue(any(row['job']['status']=='prepared' for row in saved))
        log=next((self.base/'jobs').glob('*/events.jsonl'))
        self.assertEqual(log.stat().st_mode & 0o777,0o600)


if __name__=='__main__': unittest.main()

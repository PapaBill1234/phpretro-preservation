"""Real receipt metadata renewal; disposable fixtures, no inference or charges."""
import copy,json,tempfile,time,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import harness,worker,runtime_policy
from claude_code import observations,runner,validate


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.ops=Path(self.folder.name);self.receipts=self.ops/'state/receipts';self.receipts.mkdir(parents=True)
        self.now=time.time();self.rid=str(uuid.uuid4());self.model='gpt-6-luna';self.sid=str(uuid.uuid4())
        self.settings=json.loads((Path(__file__).parents[1]/'claude_code/policy.json').read_text())['models']
        self.usage=runner.zero(self.sid,self.model,64096)
        self.usage.update(usage_schema='phpretro.claude-gateway-usage.v2',unknown_request_ceilings=[],
          provider='custom:a6api',reported_model='cb/gpt-6-luna',input_tokens=80,output_tokens=15,
          cache_read_tokens=5,total_tokens=100,conservative_tokens=100,api_calls=2,
          completed_api_calls=2,usage_known_calls=2,cost_status='quoted-estimate')
        self.context={'schema':'phpretro.context-usage.v1','enabled_tools':['execute'],'tool_calls':1,
          'tool_errors':0,'complete':False,'requests':[],'updated_at':self.now}
        self.receipt={'run_id':self.rid,'runtime':'claude-code','model':self.model,'status':'complete',
          'rc':0,'prepared_at':self.now-10,'completed_at':self.now+1,'reserved_tokens':64096,'usage':copy.deepcopy(self.usage)}
        self.path=self.receipts/(self.rid+'.json');self.write(self.path,self.receipt)
        self.write(self.path.with_suffix('.context.json'),self.context)
        with patch.object(observations.time,'time',return_value=self.now):
            observations.record(self.path,'source',self.usage,self.context)
    def write(self,path,value):path.write_text(json.dumps(value))
    def evidence(self):return observations.recent(self.ops,'source',self.settings,self.now+2)
    def test_real_worker_usage_projection_renews_route_without_changing_charges(self):
        usage_file=self.path.with_suffix('.usage.json');self.write(usage_file,self.usage)
        self.receipt['usage']=worker.usage_snapshot(usage_file,self.ops/'absent.db','',runtime='claude-code')
        self.write(self.path,self.receipt)
        before=self.path.read_bytes()
        old={'a6api':{self.model:{'tool_calls':True,'usage':True,'checked_at':self.now-86401}}}
        original=copy.deepcopy(old)
        rows=observations.merge(self.ops,'source',self.settings,old,self.now+2)
        self.assertEqual(rows['a6api'][self.model]['checked_at'],self.now)
        self.assertEqual(rows['a6api'][self.model]['run_id'],self.rid)
        self.assertEqual(old,original);self.assertEqual(before,self.path.read_bytes())
        self.assertFalse(self.context['complete'])  # No fabricated complete prompt-tokenization coverage.
    def test_failed_pending_unknown_and_over_budget_receipts_never_admit(self):
        for changes in ({'rc':1},{'rc':False},{'status':'running'},{'reserved_tokens':99}):
            self.write(self.path,{**self.receipt,**changes})
            with self.subTest(changes=changes):self.assertEqual(self.evidence(),{})
        for changes in ({'usage_complete':False},{'unknown_api_calls':1},{'reported_model':'wrong'},
          {'total_tokens':True},{'input_tokens':81},{'api_calls':1},{'provider':'mixed:a6api-portdan'}):
            self.write(self.path,{**self.receipt,'usage':{**self.usage,**changes}})
            with self.subTest(changes=changes):self.assertEqual(self.evidence(),{})
    def test_missing_tool_and_error_context_do_not_renew(self):
        for changes in ({'tool_calls':0},{'tool_calls':True},{'tool_errors':1},{'enabled_tools':[]}):
            self.write(self.path.with_suffix('.context.json'),{**self.context,**changes})
            with self.subTest(changes=changes):self.assertEqual(self.evidence(),{})
        self.path.with_suffix('.context.json').unlink();self.assertEqual(self.evidence(),{})
    def test_old_source_expired_future_and_unfinished_time_are_rejected(self):
        self.assertEqual(observations.recent(self.ops,'other',self.settings,self.now+2),{})
        self.assertEqual(observations.recent(self.ops,'source',self.settings,self.now+86401),{})
        self.assertEqual(observations.recent(self.ops,'source',self.settings,self.now-1),{})
        self.write(self.path,{**self.receipt,'completed_at':self.now-1});self.assertEqual(self.evidence(),{})
    def test_changed_usage_context_and_symlinks_are_not_proof(self):
        self.write(self.path,{**self.receipt,'usage':{**self.usage,'output_tokens':16,'total_tokens':101,'conservative_tokens':101}})
        self.assertEqual(self.evidence(),{})
        self.write(self.path,self.receipt)
        changed={**self.context,'tool_calls':2};self.write(self.path.with_suffix('.context.json'),changed)
        self.assertEqual(self.evidence(),{})
        self.write(self.path.with_suffix('.context.json'),self.context)
        self.assertIn('a6api',self.evidence())
        other=self.receipts/'outside.json';self.write(other,self.context)
        target=self.path.with_suffix('.context.json');target.unlink();target.symlink_to(other)
        self.assertEqual(self.evidence(),{})
    def test_unobserved_fallback_and_tool_free_record_are_not_created(self):
        rows=self.evidence();self.assertNotIn('portdan',rows)
        route=self.path.with_suffix('.route.json');route.unlink()
        observations.record(self.path,'source',self.usage,{**self.context,'tool_calls':0})
        self.assertFalse(route.exists())
        observations.record(self.path,'source',{**self.usage,'usage_complete':False},self.context)
        self.assertFalse(route.exists())
    def test_runtime_routes_include_only_real_current_source_receipts(self):
        data={'runtime':'claude-code','models':self.settings}
        with patch.object(runtime_policy,'OPS',self.ops),patch.object(runtime_policy,'fingerprint',return_value='source'),\
             patch.object(runtime_policy,'load',return_value=data),patch.object(runtime_policy.canary,'operator_route',return_value=False),\
             patch.object(observations.time,'time',return_value=self.now+2):
            self.assertEqual(runtime_policy.verified_providers(self.model,{'provider_models':{}}),['a6api'])
            self.assertEqual(runtime_policy.verified_providers('deepseek-v4.1-flash',{'provider_models':{}}),[])
            with patch.object(runtime_policy,'fingerprint',return_value='different-source'):
                self.assertEqual(runtime_policy.verified_providers(self.model,{'provider_models':{}}),[])
    def test_validator_renews_observed_model_and_keeps_missing_models_pending(self):
        data={'models':self.settings,'cli_version':'native-version'}
        expired={'implementation_sha256':'source','completed_at':self.now-86401,
          'models':{m:{'tool_calls':True,'usage':True,'rc':0,'cli_version':'native-version'} for m in self.settings},
          'provider_models':{'a6api':{m:{'tool_calls':True,'usage':True,'checked_at':self.now-86401} for m in self.settings}}}
        before=copy.deepcopy(expired)
        with patch.object(observations.time,'time',return_value=self.now+2):
            models,routes=validate.provider_evidence(self.ops,'source',data,expired)
        self.assertTrue(models[self.model]['usage']);self.assertFalse(models['deepseek-v4.1-flash']['usage'])
        self.assertFalse(all(row['usage'] for row in models.values()))
        self.assertEqual(list(routes['a6api']),[self.model]);self.assertEqual(before,expired)
    def test_validator_keeps_initial_acceptance_source_time_and_cli_guards(self):
        data={'models':self.settings,'cli_version':'native-version'}
        provider={'implementation_sha256':'source','completed_at':self.now,
          'models':{'deepseek-v4.1-flash':{'tool_calls':True,'usage':True,'rc':0,'cli_version':'native-version'}},
          'provider_models':{'a6api':{'deepseek-v4.1-flash':{'tool_calls':True,'usage':True,'checked_at':self.now}}}}
        with patch.object(observations.time,'time',return_value=self.now+2):
            models,_=validate.provider_evidence(self.ops,'source',data,provider)
            self.assertTrue(models['deepseek-v4.1-flash']['usage'])
            for changes in ({'implementation_sha256':'old'},{'completed_at':self.now+5},
              {'completed_at':self.now-86401},{'models':{}},
              {'models':{'deepseek-v4.1-flash':{'tool_calls':True,'usage':True,'rc':0,'cli_version':'old-version'}}}):
                models,_=validate.provider_evidence(self.ops,'source',data,{**provider,**changes})
                with self.subTest(changes=changes):self.assertFalse(models['deepseek-v4.1-flash']['usage'])

    def test_unchanged_valid_primary_fallback_order_is_preserved(self):
        existing={'portdan':{self.model:{'tool_calls':True,'usage':True,'checked_at':self.now-5}}}
        with patch.object(runtime_policy,'OPS',self.ops),patch.object(runtime_policy,'fingerprint',return_value='source'),\
             patch.object(runtime_policy,'load',return_value={'runtime':'claude-code','models':self.settings}),\
             patch.object(runtime_policy.canary,'operator_route',return_value=False),\
             patch.object(observations.time,'time',return_value=self.now+2):
            self.assertEqual(runtime_policy.verified_providers(self.model,{'provider_models':existing}),['a6api','portdan'])
        self.assertEqual(existing['portdan'][self.model]['checked_at'],self.now-5)


if __name__=='__main__':unittest.main()

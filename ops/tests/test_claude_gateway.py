import contextlib,copy,io,json,tempfile,time,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import harness
import integrity,request_accounting,worker
from claude_code import gateway,runner

class Evidence:
    def __init__(self):self.data={}
    def save(self):pass
    def add(self,*args,**kwargs):pass
    def request(self,*args):pass

class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name)
        self.data=json.loads((Path(__file__).parents[1]/'claude_code/policy.json').read_text())
        self.row=runner.zero(str(uuid.uuid4()),'gpt-6.1-sol',64096)
        self.row.update(usage_schema=gateway.SCHEMA,unknown_request_ceilings=[])
        self.manifest={'_receipt_path':str(self.root/'receipt.json'),'role':'reviewer','prepared_at':time.time(),
          'timeout':30,'reserved_tokens':200000,'reserved_cost_estimate':1}
        self.body={'model':'gpt-6.1-sol','max_tokens':4096,'messages':[{'role':'user','content':'Synthetic fixture'}]}
        self.calls=[];self.writes=[];self.client=None
    def tearDown(self):
        if self.client:self.client.close()
        self.folder.cleanup()
    def response(self,model='gpt-6.1-sol'):
        return {'model':model,'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'ok'}]}],
          'usage':{'input_tokens':35,'output_tokens':4,'total_tokens':39,'input_tokens_details':{'cached_tokens':7}}}
    def start(self,invoke=None,routes=None,model='gpt-6.1-sol'):
        def fake(endpoint,key,body,timeout):
            self.assertEqual(self.writes[-1]['unknown_api_calls'],len(self.calls)+1)
            self.calls.append(endpoint)
            return self.response(model)
        self.body['model']=model;self.row['model']=model
        self.client=gateway.Gateway(self.data,self.manifest,model,self.row,
          lambda:self.writes.append(copy.deepcopy(self.row)),Evidence(),Evidence(),
          {'a6api_api_key':'synthetic-primary','portdan':{'openai':'synthetic-fallback','deepseek':'synthetic-fallback'}},
          invoke=invoke or fake,routes=routes or ['a6api','portdan'])
        self.client.arm();return self.client
    def test_numeric_inclusive_cache_converted_exactly(self):
        row=gateway.usage(self.response()['usage'],'responses')
        self.assertEqual((row['input_tokens'],row['cache_read_tokens'],row['total_tokens']),(28,7,39))
        for changes in ({'input_tokens':True},{'input_tokens':1},{'total_tokens':40},{'input_tokens_details':{}},{'output_tokens':'4'},{'output_tokens':0},{'input_tokens':0}):
            with self.assertRaises(integrity.IntegrityError):gateway.usage({**self.response()['usage'],**changes},'responses')
    def test_deepseek_hit_and_miss_must_reconcile(self):
        raw={'prompt_tokens':35,'completion_tokens':4,'total_tokens':39,'prompt_cache_hit_tokens':7,'prompt_cache_miss_tokens':28}
        self.assertEqual(gateway.usage(raw,'chat')['input_tokens'],28)
        with self.assertRaises(integrity.IntegrityError):gateway.usage({**raw,'prompt_cache_miss_tokens':27},'chat')
    def test_physical_request_hold_precedes_transport(self):
        client=self.start();message=client.call(self.body)
        self.assertEqual(message['usage']['input_tokens'],28);self.assertEqual(self.row['api_calls'],1)
        self.assertEqual(self.row['conservative_tokens'],39);self.assertTrue(self.row['usage_complete'])
        self.assertEqual(request_accounting.bounded_tokens(self.row,39),39)
        with self.assertRaises(integrity.IntegrityError):client.call(self.body)
        self.assertEqual(len(self.calls),1)
    def test_remaining_f61_hold_denies_before_any_paid_request(self):
        self.manifest['reserved_tokens']=4499;client=self.start()
        with self.assertRaises(integrity.IntegrityError):client.call(self.body)
        self.assertEqual(self.calls,[]);self.assertEqual(self.row['api_calls'],0)
    def test_oversize_and_unsupported_context_do_not_forward(self):
        client=self.start();self.body['messages'][0]['content']='x'*60000
        with self.assertRaises(integrity.IntegrityError):client.call(self.body)
        client.arm();self.body['messages'][0]['content']=[{'type':'image','source':{}}]
        with self.assertRaises(integrity.IntegrityError):client.call(self.body)
        self.assertEqual(self.calls,[])
    def test_reviewer_tools_and_provider_identity_fail_closed(self):
        client=self.start();self.body['tools']=[{'name':'mcp__phpretro__execute','input_schema':{'type':'object'}}]
        with self.assertRaises(integrity.IntegrityError):client.call(self.body)
        self.assertEqual(self.calls,[])
        client.arm();self.body.pop('tools');client.invoke=lambda *args:self.response('wrong-model')
        with self.assertRaises(integrity.IntegrityError):client.call(self.body)
        self.assertEqual(self.row['unknown_api_calls'],1);self.assertEqual(self.row['conservative_tokens'],64096)
    def test_disabled_portdan_cash_guard_is_not_free_recorded_usage(self):
        self.manifest['reserved_cost_estimate']=0;client=self.start(routes=['portdan'])
        client.call(self.body)
        self.assertGreater(self.row['estimated_cost_usd'],0)
        self.assertEqual(client.guard_spent,0);self.assertEqual(self.row['provider'],'custom:portdan')
    def test_unpriced_portdan_has_no_fabricated_cash_total(self):
        raw={'model':'deepseek-v4.1-flash','choices':[{'finish_reason':'stop','message':{'content':'ok'}}],
          'usage':{'prompt_tokens':35,'completion_tokens':4,'total_tokens':39,'prompt_cache_hit_tokens':7,'prompt_cache_miss_tokens':28}}
        client=self.start(invoke=lambda *args:raw,routes=['portdan'],model='deepseek-v4.1-flash')
        client.call(self.body);self.assertNotIn('estimated_cost_usd',self.row)
        self.assertEqual(self.row['cost_status'],'unknown-price')
    def test_fallback_unknown_request_hold_is_retained(self):
        def fake(endpoint,*args):
            self.calls.append(endpoint)
            if len(self.calls)==1:raise gateway.ProviderError(429)
            return self.response()
        client=self.start(invoke=fake);client.call(self.body)
        self.assertIn('a6api',self.calls[0]);self.assertIn('portdan',self.calls[1])
        self.assertFalse(self.row['usage_complete']);self.assertEqual(self.row['unknown_request_ceilings'],[64096])
        self.assertEqual(request_accounting.bounded_tokens(self.row,39),64096+39)
    def test_cancelled_backoff_cannot_reconnect(self):
        def fake(*args):
            self.calls.append('attempt');self.root.joinpath('receipt.cancel.json').write_text('{}')
            raise gateway.ProviderError(503)
        client=self.start(invoke=fake,routes=['a6api'])
        with self.assertRaises(InterruptedError):client.call(self.body)
        self.assertEqual(len(self.calls),1);self.assertEqual(self.row['unknown_api_calls'],1)
    def test_prelaunch_validation_denial_is_truthful_zero_calls(self):
        path=self.root/'receipt.json';usage=self.root/'usage.json'
        value={'run_id':str(uuid.uuid4()),'status':'running','role':'builder','model':'gpt-6.1-sol','profile':'Synthetic','unit':'Synthetic','usage_path':str(usage)}
        path.write_text(json.dumps(value))
        with patch.object(runner.runtime_policy,'load',return_value=self.data),patch.object(runner.runtime_policy,'model_settings',return_value=self.data['models']['gpt-6.1-sol']),patch.object(runner.runtime_policy,'ready',return_value=False):
            self.assertEqual(runner.main(path),75)
        actual=worker.usage_snapshot(usage,self.root/'none.db','',runtime='claude-code')
        self.assertTrue(actual['usage_complete']);self.assertEqual(actual['api_calls'],0)
        self.assertEqual(actual['conservative_tokens'],0)
    def test_response_reasoning_is_retained_in_tool_followup(self):
        chat={'model':'gpt-6.1-sol','messages':[{'role':'assistant','content':'','tool_calls':[{'id':'call_1','function':{'name':'mcp__phpretro__execute','arguments':'{}'}}]},
          {'role':'tool','tool_call_id':'call_1','content':'ok'}]}
        thought={'type':'reasoning','id':'rs_1','encrypted_content':'synthetic encrypted fixture'}
        value=gateway.responses_request(chat,{'call_1':[thought]})
        self.assertEqual(value['input'][0],thought);self.assertEqual(value['input'][-1]['type'],'function_call_output')

    def test_reviewed_bootstrap_can_measure_expired_primary_without_admitting_fallback(self):
        for model in ('gpt-6.1-sol','gpt-6-luna','deepseek-v4.1-flash'):
            with self.subTest(model=model):
                self.check_runner_routes(model,bootstrap=True,expected=['a6api'])

    def test_ordinary_jobs_cannot_use_bootstrap_to_bypass_expired_routes(self):
        self.check_runner_routes('gpt-6-luna',bootstrap=False,expected=[])

    def check_runner_routes(self,model,bootstrap,expected):
        rid=str(uuid.uuid4());path=self.root/(rid+'.json');usage=self.root/(rid+'.usage.json')
        path.write_text(json.dumps({'run_id':rid,'status':'running','role':'builder','model':model,
            'profile':'claude-bootstrap' if bootstrap else 'Synthetic','unit':'' if bootstrap else 'Synthetic',
            'usage_path':str(usage),'prepared_at':time.time(),'timeout':30,'cwd':str(self.root)}))
        secrets={'a6api_api_key':'synthetic-primary','portdan_api_key':'synthetic-unverified'}
        captured=[]
        def deny(*args,**kwargs):
            captured.append((kwargs['routes'],args[5].secrets))
            # No listener, transport, CLI or paid call. Stop at route selection.
            raise integrity.IntegrityError('Synthetic stop before transport')
        with patch.object(runner.runtime_policy,'load',return_value=self.data), \
             patch.object(runner.runtime_policy,'model_settings',return_value=self.data['models'][model]), \
             patch.object(runner.runtime_policy,'fingerprint',return_value='source'), \
             patch.object(runner.admission,'bootstrap_ready',return_value=bootstrap), \
             patch.object(runner.runtime_policy,'ready',return_value=not bootstrap), \
             patch.object(runner.runtime_policy,'verified_providers',return_value=[]) as admitted, \
             patch.object(runner.gateway,'credentials',return_value=secrets), \
             patch.object(runner.gateway,'Gateway',side_effect=deny), \
             patch.object(runner.sandbox,'Sandbox'),patch.object(runner.signal,'signal'), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(path),1)
            if bootstrap:admitted.assert_not_called()
            else:admitted.assert_called_once_with(model)
        self.assertEqual(captured[0][0],expected)
        if bootstrap:self.assertIn('synthetic-primary',captured[0][1])
        actual=json.loads(usage.read_text())
        self.assertEqual(actual['api_calls'],0)
        self.assertEqual(actual['conservative_tokens'],0)

class ResponseDiagnosticTests(unittest.TestCase):
    def test_response_diagnostics_keep_only_numeric_usage_and_known_shape(self):
        raw={'model':'gpt-6.1-sol','status':'completed','output':[{'text':'private content'}],
             'error':{'message':'private error'},'secret':'private key',
             'usage':{'input_tokens':12,'output_tokens':3,'total_tokens':15,'private':'sensitive',
               'input_tokens_details':{'cached_tokens':4,'secret':'sensitive'}}}
        with patch.object(gateway.runtime_policy,'model_label_matches',return_value=True):
            row=gateway.response_observation(raw,'gpt-6.1-sol')
        self.assertEqual(row['usage']['input_tokens'],12)
        self.assertTrue(row['identity_valid'])
        self.assertNotIn('private',json.dumps(row));self.assertNotIn('sensitive',json.dumps(row))
        self.assertNotIn('model',row)

if __name__=='__main__':unittest.main()

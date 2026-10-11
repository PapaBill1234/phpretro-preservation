import contextlib,copy,io,json,tempfile,time,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import harness
import integrity,request_accounting,worker
from claude_code import gateway,runner,usage_policy

class Evidence:
    def __init__(self):self.data={}
    def save(self):pass
    def add(self,*args,**kwargs):pass
    def request(self,*args):pass

class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name)
        self.data=json.loads((Path(__file__).parents[1]/'claude_code/policy.json').read_text())
        loaded=patch.object(gateway.runtime_policy,'load',return_value=self.data);loaded.start();self.addCleanup(loaded.stop)
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
          'usage':{'input_tokens':35,'output_tokens':4,'total_tokens':39,'input_tokens_details':{'cached_tokens':7},'output_tokens_details':{'reasoning_tokens':0}}}
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

    def test_malformed_details_cannot_hide_behind_other_cache_counters(self):
        chat={'prompt_tokens':35,'completion_tokens':4,'total_tokens':39,'prompt_cache_hit_tokens':7,'prompt_cache_miss_tokens':28}
        for value in ('invalid',[],True,4):
            for key in ('prompt_tokens_details','completion_tokens_details'):
                with self.subTest(key=key,value=value),self.assertRaises(integrity.IntegrityError):
                    gateway.usage({**chat,key:value},'chat')
            response={**self.response()['usage'],'prompt_cache_hit_tokens':7,'prompt_cache_miss_tokens':28,'input_tokens_details':value}
            with self.assertRaises(integrity.IntegrityError):gateway.usage(response,'responses')

    def test_nullable_chat_details_are_unknown_not_fabricated_zero(self):
        chat={'prompt_tokens':35,'completion_tokens':4,'total_tokens':39,'prompt_cache_hit_tokens':7,'prompt_cache_miss_tokens':28,
              'prompt_tokens_details':None,'completion_tokens_details':{'reasoning_tokens':None}}
        self.assertIsNone(gateway.usage(chat,'chat')['reasoning_tokens'])
        self.assertIsNone(gateway.compatible_usage({**chat,'prompt_cache_miss_tokens':29},'chat',True)['reasoning_tokens'])
        for value in (None,{'reasoning_tokens':None},'invalid'):
            with self.assertRaises(integrity.IntegrityError):
                gateway.usage({**self.response()['usage'],'output_tokens_details':value},'responses')

    def test_supplied_responses_reasoning_details_must_be_valid(self):
        for details in (None,{}, {'reasoning_tokens':None}, {'reasoning_tokens':True}, {'reasoning_tokens':'0'}):
            if self.client:self.client.close();self.client=None
            self.row=runner.zero(str(uuid.uuid4()),'gpt-6.1-sol',64096)
            self.row.update(usage_schema=gateway.SCHEMA,unknown_request_ceilings=[])
            raw=self.response()
            raw['usage']['output_tokens_details']=details
            with self.subTest(details=details):
                client=self.start(invoke=lambda *args:raw,routes=['a6api'])
                with self.assertRaises(integrity.IntegrityError):client.call(self.body)
                self.assertFalse(self.row['usage_complete'])
                self.assertEqual(self.row['unknown_api_calls'],1)
                self.assertEqual(self.row['conservative_tokens'],64096)

    def test_observed_a6api_sol_billing_does_not_invent_missing_reasoning(self):
        raw=self.response()
        raw['usage']={'input_tokens':253,'output_tokens':102,'total_tokens':355,
          'input_tokens_details':{'cached_tokens':249},'cache_creation_input_tokens':1}
        client=self.start(invoke=lambda *args:raw,routes=['a6api'])
        message=client.call(self.body)
        self.assertTrue(self.row['usage_complete'])
        self.assertEqual(self.row['unknown_api_calls'],0)
        self.assertEqual(self.row['conservative_tokens'],355)
        self.assertEqual((self.row['input_tokens'],self.row['output_tokens'],self.row['cache_read_tokens'],self.row['cache_write_tokens']),(3,102,249,1))
        self.assertIsNone(client.last['usage']['reasoning_tokens'])
        self.assertFalse(client.last['usage']['reasoning_breakdown_complete'])
        self.assertEqual(client.context.data['provider_response_observations'][0]['reasoning_breakdown_status'],'unavailable')
        self.assertEqual(sum(message['usage'].values()),355)

    def test_observed_deepseek_alias_does_not_waive_conflicting_usage(self):
        model='deepseek-v4.1-flash';alias='cb/deepseek-v4.1-flash'
        self.data['models'][model]['usage_conflict_policy']='strict'
        raw={'model':alias,'choices':[{'finish_reason':'stop','message':{'content':'ok'}}],
          'usage':{'prompt_tokens':486,'completion_tokens':137,'total_tokens':682,
            'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':545}}
        with patch.object(gateway.runtime_policy,'load',return_value=self.data):
            self.assertTrue(gateway.runtime_policy.model_label_matches(model,alias))
            for wrong in ('cb/deepseek-v4.1-pro','cb/cb/deepseek-v4.1-flash','cb/deepseek-v4.1-flash/suffix'):
                self.assertFalse(gateway.runtime_policy.model_label_matches(model,wrong))
            client=self.start(invoke=lambda *args:raw,routes=['a6api'],model=model)
            with self.assertRaisesRegex(integrity.IntegrityError,'Cache hit/miss counters disagree'):
                client.call(self.body)
        self.assertEqual(self.row['unknown_api_calls'],1)
        self.assertEqual(self.row['conservative_tokens'],64096)
        self.assertFalse(self.row['usage_complete'])
        diagnostic=client.context.data['provider_response_observations'][0]
        self.assertEqual(diagnostic['reported_model'],alias)
        self.assertTrue(diagnostic['identity_valid'])

    def conflicting_response(self):
        return {'model':'cb/deepseek-v4.1-flash','choices':[{'finish_reason':'stop','message':{'content':'ok'}}],
          'usage':{'prompt_tokens':486,'completion_tokens':88,'total_tokens':633,
                   'prompt_cache_hit_tokens':0,'prompt_cache_miss_tokens':545,
                   'completion_tokens_details':{'reasoning_tokens':30}}}

    def test_user_override_retains_unknown_holds_raw_counters_and_worker_metadata(self):
        raw=self.conflicting_response();client=self.start(invoke=lambda *args:raw,routes=['a6api'],model=usage_policy.MODEL)
        for call in range(2):
            client.arm();wire=client.call(self.body)
            self.assertEqual(wire['usage']['input_tokens'],545)
            self.assertEqual(wire['usage']['output_tokens'],88)
            self.assertEqual(self.row['usage_conflict_calls'],call+1)
            self.assertTrue(usage_policy.continuation_allowed(self.data,self.row))
        self.assertFalse(self.row['usage_complete']);self.assertEqual(self.row['total_tokens'],0)
        self.assertEqual(self.row['conservative_tokens'],128192)
        self.assertEqual(self.row['unknown_request_ceilings'],[64096,64096])
        self.assertEqual(self.row['usage_known_calls'],0)
        self.assertGreater(self.row['estimated_cost_usd'],0)
        self.assertEqual(client.context.data['provider_response_observations'][0]['usage'],raw['usage'])
        path=self.root/'usage.json';path.write_text(json.dumps(self.row))
        projected=worker.usage_snapshot(path,self.root/'absent.db','',runtime='claude-code')
        self.assertEqual(projected['usage_conflict_calls'],2)
        self.assertEqual(projected['usage_conflict_policy'],usage_policy.POLICY)
        self.assertFalse(projected['usage_complete'])
        self.assertEqual(request_accounting.bounded_tokens(projected,0),128192)
        for changes in ({'usage_conflict_calls':3},{'usage_conflict_calls':True},{'conservative_tokens':0},
                        {'model':'gpt-6-luna'},{'usage_complete':True}):
            with self.subTest(changes=changes),self.assertRaises(integrity.IntegrityError):
                request_accounting.bounded_tokens({**projected,**changes},0)

    def test_conflict_evidence_survives_bounded_diagnostic_limit(self):
        count=0
        def upstream(*args):
            nonlocal count
            count+=1
            raw=self.conflicting_response()
            if count<=16:raw['usage']={'prompt_tokens':35,'completion_tokens':4,'total_tokens':39,'prompt_cache_hit_tokens':7,'prompt_cache_miss_tokens':28}
            return raw
        client=self.start(invoke=upstream,routes=['a6api'],model=usage_policy.MODEL)
        for _ in range(17):client.arm();client.call(self.body)
        self.assertEqual(len(client.context.data['provider_response_observations']),16)
        evidence=json.loads((self.root/'receipt.usage-conflict-17.json').read_text())
        self.assertEqual(evidence['physical_request'],17)
        self.assertEqual(evidence['provider'],'a6api')
        self.assertEqual(evidence['reported_model'],'cb/deepseek-v4.1-flash')
        self.assertEqual(evidence['usage'],self.conflicting_response()['usage'])
        self.assertEqual(self.row['conservative_tokens'],16*39+64096)
        self.assertTrue(usage_policy.continuation_allowed(self.data,self.row))

    def test_conflict_cannot_continue_without_durable_counter_evidence(self):
        client=self.start(invoke=lambda *args:self.conflicting_response(),routes=['a6api'],model=usage_policy.MODEL)
        with patch.object(gateway.control,'atomic_json',side_effect=OSError('Synthetic storage failure')):
            with self.assertRaises(OSError):client.call(self.body)
        self.assertEqual(self.row['conservative_tokens'],64096)
        self.assertNotIn('usage_conflict_calls',self.row)
        self.assertIsNone(client.last)

    def test_numeric_exception_cannot_hide_later_invalid_fields_or_output(self):
        raw=self.conflicting_response()
        for changes in ({'completion_tokens':True},{'total_tokens':'633'},{'prompt_cache_miss_tokens':None},
                        {'prompt_tokens_details':{'cached_tokens':False}},
                        {'cache_creation_input_tokens':-1},{'completion_tokens_details':{'reasoning_tokens':89}}):
            with self.subTest(changes=changes),self.assertRaises(integrity.IntegrityError):
                gateway.compatible_usage({**raw['usage'],**changes},'chat',True)
        for value in ({**raw,'model':'wrong-model'},{**raw,'choices':[]},
                      {**raw,'choices':[{'finish_reason':'length','message':{'content':'truncated'}}]}):
            with self.subTest(value=value),self.assertRaises(integrity.IntegrityError):
                gateway.output(value,'chat',usage_policy.MODEL,set(),{},{},True)
        with self.assertRaises(integrity.IntegrityError):
            gateway.output({**raw,'model':'gpt-6-luna'},'chat','gpt-6-luna',set(),{},{},True)

    def test_override_cannot_admit_other_unknown_attempts_or_exceed_original_caps(self):
        raw=self.conflicting_response();client=self.start(invoke=lambda *args:raw,routes=['a6api'],model=usage_policy.MODEL)
        client.call(self.body)
        self.assertTrue(usage_policy.continuation_allowed(self.data,self.row))
        self.row['unknown_api_calls']+=1;self.row['api_calls']+=1
        self.row['unknown_request_ceilings'].append(64096);self.row['conservative_tokens']+=64096
        self.assertFalse(usage_policy.continuation_allowed(self.data,self.row))
        self.manifest['reserved_tokens']=self.row['conservative_tokens']+4499
        client.arm()
        with self.assertRaisesRegex(integrity.IntegrityError,'Remaining original token hold'):
            client.call(self.body)
        self.assertEqual(self.row['api_calls'],2)

    def test_conflicting_response_with_oversize_usage_is_not_forwarded(self):
        raw=self.conflicting_response();raw['usage']['prompt_cache_miss_tokens']=70000
        client=self.start(invoke=lambda *args:raw,routes=['a6api'],model=usage_policy.MODEL)
        with self.assertRaises(integrity.IntegrityError):client.call(self.body)
        self.assertNotIn('usage_conflict_calls',self.row)
        self.assertFalse(usage_policy.continuation_allowed(self.data,self.row))

    def test_actual_runner_continues_same_session_and_exports_only_admitted_conflicts(self):
        for transport_unknown,bootstrap in ((False,False),(False,True),(True,False),(True,True)):
            with self.subTest(transport_unknown=transport_unknown,bootstrap=bootstrap):
                rid=str(uuid.uuid4());path=self.root/(rid+'.json');usage=path.with_suffix('.usage.json')
                prompt=self.root/'brief.txt';prompt.write_text('Synthetic unit')
                model=usage_policy.MODEL
                path.write_text(json.dumps({'run_id':rid,'status':'running','role':'builder','model':model,
                  'profile':'claude-bootstrap' if bootstrap else 'Synthetic','unit':'' if bootstrap else 'Synthetic','usage_path':str(usage),'prompt_path':str(prompt),
                  'prepared_at':time.time(),'timeout':30,'cwd':str(self.root),'reserved_tokens':300000,
                  'reserved_cost_estimate':1,'allowed_paths':['example.py']}))
                clients=[];physical=[];sessions=[];real_gateway=gateway.Gateway
                def upstream(*args):
                    physical.append('request')
                    if transport_unknown and len(physical)==1:raise gateway.ProviderError(429)
                    raw=self.conflicting_response()
                    if len(sessions)==1:
                        raw['choices']=[{'finish_reason':'tool_calls','message':{'content':None,
                          'tool_calls':[{'id':'fixture_call','function':{'name':'mcp__phpretro__execute',
                          'arguments':'{"command":"echo fixture"}'}}]}}]
                    return raw
                def client(*args,**kwargs):
                    instance=real_gateway(*args,**kwargs,invoke=upstream);clients.append(instance);return instance
                def native(args,env,cwd,brief,stream,deadline,cancel,update):
                    sessions.append(stream.sid)
                    system=args[args.index('--system-prompt')+1]
                    if bootstrap:
                        self.assertNotIn('Read AGENTS.md',system)
                        self.assertIn('capability check',system)
                        if len(sessions)>1:self.assertIn('without additional tools',brief)
                    else:
                        self.assertIn('Read AGENTS.md',system)
                        if len(sessions)>1:self.assertIn('same unit',brief)
                    message=clients[0].call({'model':model,'max_tokens':4096,
                      'messages':[{'role':'user','content':'Synthetic fixture'}],
                      'tools':[{'name':'mcp__phpretro__execute','input_schema':{'type':'object'}}]})
                    first=len(sessions)==1
                    events=[{'type':'system','subtype':'init','session_id':stream.sid,'model':model,
                             'tools':['mcp__phpretro__execute'],'skills':[],'slash_commands':[],'plugins':[]},
                            {'type':'assistant','session_id':stream.sid,'message':message}]
                    if first:events.append({'type':'user','session_id':stream.sid,'message':{'content':[
                      {'type':'tool_result','tool_use_id':'fixture_call','content':'fixture','is_error':False}]}})
                    events.append({'type':'result','session_id':stream.sid,
                      'subtype':'error_max_turns' if first else 'success','is_error':first,
                      'num_turns':2 if first else 1,'usage':message['usage'],'result':'Synthetic complete'})
                    for event in events:stream.accept(event);update(event)
                    return 0
                secrets={'a6api_api_key':'synthetic-primary','portdan':{'deepseek':'synthetic-fallback'}}
                with patch.object(runner.runtime_policy,'fingerprint',return_value='source'), \
                     patch.object(runner.admission,'bootstrap_ready',return_value=bootstrap), \
                     patch.object(runner.runtime_policy,'ready',return_value=True), \
                     patch.object(runner.runtime_policy,'verified_providers',return_value=['a6api','portdan']), \
                     patch.object(runner.gateway,'credentials',return_value=secrets), \
                     patch.object(runner.gateway,'Gateway',side_effect=client),patch.object(runner,'invoke',side_effect=native), \
                     patch.object(runner.sandbox,'Sandbox') as sandboxed,patch.object(runner.signal,'signal'), \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(runner.main(path),1 if transport_unknown else 0)
                    if transport_unknown:sandboxed.return_value.export.assert_not_called()
                    else:sandboxed.return_value.export.assert_called_once()
                row=json.loads(usage.read_text())
                self.assertFalse(row['usage_complete']);self.assertEqual(row['conservative_tokens'],128192)
                self.assertEqual(row['usage_conflict_calls'],1 if transport_unknown else 2)
                self.assertEqual(len(sessions),1 if transport_unknown else 2)
                self.assertEqual(len(set(sessions)),1)
                self.assertEqual(row['total_tokens'],0)
    def test_all_supplied_cache_representations_must_agree(self):
        raw={'prompt_tokens':35,'completion_tokens':4,'total_tokens':39,'prompt_tokens_details':{'cached_tokens':7},
             'prompt_cache_hit_tokens':7,'prompt_cache_miss_tokens':28}
        self.assertEqual(gateway.usage(raw,'chat')['input_tokens'],28)
        for changes in ({'prompt_cache_hit_tokens':True},{'prompt_cache_miss_tokens':'28'},
            {'prompt_cache_hit_tokens':6,'prompt_cache_miss_tokens':29},
            {'prompt_tokens_details':{'cached_tokens':True}},{'prompt_cache_miss_tokens':27}):
            with self.subTest(changes=changes),self.assertRaises(integrity.IntegrityError):gateway.usage({**raw,**changes},'chat')
        for absent in ('prompt_cache_hit_tokens','prompt_cache_miss_tokens'):
            row={k:v for k,v in raw.items() if k!=absent}
            with self.assertRaises(integrity.IntegrityError):gateway.usage(row,'chat')
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
        self.assertEqual(client.context.data['provider_transport_errors'],[{'provider':'a6api','status_code':429,'request':1}])
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

    def test_deepseek_tool_continuation_omits_tool_choice_and_keeps_reasoning(self):
        body={'messages':[{'role':'assistant','content':[{'type':'tool_use','id':'call_1',
            'name':'mcp__phpretro__execute','input':{'command':'echo fixture'}}]},
            {'role':'user','content':[{'type':'tool_result','tool_use_id':'call_1','content':'fixture'}]}],
            'tools':[{'name':'mcp__phpretro__execute','input_schema':{'type':'object'}}]}
        payload=gateway.chat_request(body,'deepseek-v4.1-flash',{'call_1':'synthetic reasoning'})
        self.assertNotIn('tool_choice',payload)
        self.assertEqual(payload['messages'][0]['reasoning_content'],'synthetic reasoning')
        self.assertEqual(payload['messages'][0]['content'],'')
        self.assertEqual(payload['messages'][1]['tool_call_id'],'call_1')
        self.assertEqual(payload['tools'][0]['function']['name'],'mcp__phpretro__execute')
        self.assertEqual(gateway.chat_request(body,'gpt-6.1-sol',{})['tool_choice'],'auto')

    def test_reviewed_bootstrap_can_measure_expired_primary_without_admitting_fallback(self):
        for model in ('gpt-6.1-sol','gpt-6-luna','deepseek-v4.1-flash'):
            with self.subTest(model=model):
                self.check_runner_routes(model,bootstrap=True,expected=['a6api'])

    def test_ordinary_jobs_cannot_use_bootstrap_to_bypass_expired_routes(self):
        self.check_runner_routes('gpt-6-luna',bootstrap=False,expected=[])

    def test_explicit_fallback_acceptance_uses_only_selected_private_route(self):
        self.check_runner_routes('deepseek-v4.1-flash',bootstrap=True,expected=['portdan'],provider='portdan')

    def test_ordinary_runner_cannot_select_unverified_fallback(self):
        self.check_runner_routes('deepseek-v4.1-flash',bootstrap=False,expected=[],provider='portdan',denied=True)

    def check_runner_routes(self,model,bootstrap,expected,provider=None,denied=False):
        rid=str(uuid.uuid4());path=self.root/(rid+'.json');usage=self.root/(rid+'.usage.json')
        path.write_text(json.dumps({'run_id':rid,'status':'running','role':'builder','model':model,
            'profile':'claude-bootstrap' if bootstrap else 'Synthetic','unit':'' if bootstrap else 'Synthetic',
            'usage_path':str(usage),'prepared_at':time.time(),'timeout':30,'cwd':str(self.root),**({'bootstrap_provider':provider} if provider else {})}))
        secrets={'a6api_api_key':'synthetic-primary','portdan':{'openai':'synthetic-unverified','deepseek':'synthetic-unverified'}}
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
            self.assertEqual(runner.main(path),75 if denied else 1)
            if denied:
                admitted.assert_not_called();self.assertEqual(captured,[])
                self.assertEqual(json.loads(usage.read_text())['api_calls'],0)
                return
            if bootstrap:admitted.assert_not_called()
            else:admitted.assert_called_once_with(model)
        self.assertEqual(captured[0][0],expected)
        if bootstrap:self.assertIn('synthetic-unverified' if provider=='portdan' else 'synthetic-primary',captured[0][1])
        actual=json.loads(usage.read_text())
        self.assertEqual(actual['api_calls'],0)
        self.assertEqual(actual['conservative_tokens'],0)

class ResponseDiagnosticTests(unittest.TestCase):
    def test_model_diagnostics_retain_only_configured_labels_even_on_mismatch(self):
        models={'deepseek-v4.1-flash':{'automatic':True,'reported_model_aliases':['cb/deepseek-v4.1-flash']},
                'gpt-6.1-sol':{'automatic':True},'retired-model':{'automatic':False}}
        with patch.object(gateway.runtime_policy,'load',return_value={'models':models}):
            row=gateway.response_observation({'model':'cb/deepseek-v4.1-flash'},'deepseek-v4.1-flash')
            self.assertEqual(row['reported_model'],'cb/deepseek-v4.1-flash')
            self.assertTrue(row['identity_valid'])
            row=gateway.response_observation({'model':'gpt-6.1-sol'},'deepseek-v4.1-flash')
            self.assertEqual(row['reported_model'],'gpt-6.1-sol')
            self.assertFalse(row['identity_valid'])
            for unknown in ('private credential','gpt-6.1-sol-private-secret','retired-model',42,None):
                row=gateway.response_observation({'model':unknown},'deepseek-v4.1-flash')
                self.assertIsNone(row['reported_model'])
                self.assertFalse(row['identity_valid'])
                self.assertEqual(row['reported_model_status'],'missing' if unknown is None else 'unrecognized')
                self.assertNotIn('private',json.dumps(row))

    def test_protocol_and_identity_failures_are_not_budget_waits_or_arbitrary_text(self):
        for message in ('Provider model identity mismatch','Cache hit/miss counters disagree'):
            label=gateway.guard_label(integrity.IntegrityError(message))
            self.assertEqual(label,message)
            self.assertNotIn(label,gateway.BUDGET_GUARDS)
        self.assertIn(gateway.guard_label(integrity.IntegrityError('Remaining original token hold cannot cover request')),gateway.BUDGET_GUARDS)
        self.assertEqual(gateway.guard_label(integrity.IntegrityError('private payload')), 'Provider protocol validation failed')
        self.assertIsNone(gateway.guard_label(ValueError('private payload')))

    def test_request_diagnostics_keep_only_counts_and_shape(self):
        payload={'messages':[{'role':'assistant','content':'private content',
            'reasoning_content':'private reasoning','tool_calls':[{'id':'private ID'}]},
            {'role':'tool','content':'private output','tool_call_id':'private ID'}],
            'tools':[{'function':{'name':'private name'}}]}
        row=gateway.request_observation(payload,'chat')
        self.assertEqual(row,{'api_mode':'chat','tool_choice_present':False,'tools':1,
            'messages':2,'assistant_tool_messages':1,'assistant_tool_reasoning_messages':1,
            'assistant_tool_null_content':0,'tool_results':1})
        self.assertNotIn('private',json.dumps(row))

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

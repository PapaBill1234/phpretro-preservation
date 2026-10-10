import copy,json,os,sys,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import harness  # Force all controller paths to the disposable test tree.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrity,request_accounting,worker
from claude_code import policy,protocol,command,runner,tool_bridge,native_sessions

MODEL='claude-sonnet-5-5'
def init(sid,tools=()):return {'type':'system','subtype':'init','session_id':sid,'model':MODEL,'tools':list(tools),'skills':[],'slash_commands':[],'plugins':[]}
def assistant(sid,identity='msg_1',usage=None):
    return {'type':'assistant','session_id':sid,'message':{'id':identity,'model':MODEL,'content':[{'type':'text','text':'ok'}],
      'usage':usage or {'input_tokens':23,'cache_creation_input_tokens':5,'cache_read_input_tokens':7,'output_tokens':0}}}
def result(sid,subtype='success',turns=1):
    return {'type':'result','session_id':sid,'subtype':subtype,'is_error':subtype!='success','num_turns':turns,'result':'ok',
      'usage':{'input_tokens':23,'cache_creation_input_tokens':5,'cache_read_input_tokens':7,'output_tokens':4}}

class ClaudeProtocolTests(unittest.TestCase):
    def make(self):
        sid=str(uuid.uuid4());s=protocol.Stream(sid,MODEL);s.accept(init(sid));return sid,s
    def test_final_delta_completes_partial_assistant_counters(self):
        sid,s=self.make();s.accept(assistant(sid));s.accept(result(sid));row=s.usage(1004096)
        self.assertTrue(row['usage_complete']);self.assertEqual(row['total_tokens'],39)
        self.assertEqual(row['input_tokens'],23);self.assertEqual(request_accounting.bounded_tokens(row,39),39)
    def test_max_turns_tool_counter_is_not_a_second_inference(self):
        sid,s=self.make();s.accept(assistant(sid));s.accept(result(sid,'error_max_turns',2))
        self.assertTrue(s.usage(1004096)['usage_complete']);self.assertEqual(s.outcome(),'continue')
    def test_missing_final_charged_as_unknown(self):
        sid,s=self.make();s.accept(assistant(sid));row=s.usage(1004096)
        self.assertFalse(row['usage_complete']);self.assertEqual(row['unknown_api_calls'],1)
        self.assertEqual(row['conservative_tokens'],1004096)
        self.assertEqual(request_accounting.bounded_tokens(row,row['total_tokens']),1004096)
    def test_missing_initialization_cannot_complete_usage(self):
        sid=str(uuid.uuid4());s=protocol.Stream(sid,MODEL);s.accept(assistant(sid));s.accept(result(sid))
        self.assertFalse(s.usage(1004096)['usage_complete'])
    def test_model_tool_session_plugin_or_skill_mismatch_is_denied(self):
        for changes in ({'model':'other'},{'tools':['Bash']},{'session_id':str(uuid.uuid4())},
                        {'plugins':[{'name':'attacker','path':'/tmp'}]},{'skills':['host']},{'slash_commands':['host']}):
            sid=str(uuid.uuid4());s=protocol.Stream(sid,MODEL)
            with self.assertRaises(integrity.IntegrityError):s.accept({**init(sid),**changes})
    def test_builtin_metadata_does_not_enable_tools(self):
        sid=str(uuid.uuid4());s=protocol.Stream(sid,MODEL)
        s.accept({**init(sid),'plugins':[{'name':'cc-plugin-agents-md','path':'builtin'}]})
        self.assertTrue(s.initialized);self.assertEqual(s.tools,set())
    def test_malformed_or_decreased_counters_fail(self):
        for value in (None,-1,True,'5',float('nan')):
            sid,s=self.make();event=assistant(sid);event['message']['usage']['input_tokens']=value
            with self.assertRaises(integrity.IntegrityError):s.accept(event)
        sid,s=self.make();s.accept(assistant(sid));event=assistant(sid);event['message']['usage']['input_tokens']=1
        with self.assertRaises(integrity.IntegrityError):s.accept(event)
    def test_multiple_calls_cannot_hide_inside_one_turn(self):
        sid,s=self.make();s.accept(assistant(sid));s.accept(assistant(sid,'msg_2'));s.accept(result(sid))
        with self.assertRaises(integrity.IntegrityError):s.usage(1004096)
    def test_invalid_final_counters_are_not_complete(self):
        sid,s=self.make();s.accept(assistant(sid));event=result(sid);event['usage']['cache_read_input_tokens']=8
        s.accept(event);self.assertFalse(s.usage(1004096)['usage_complete'])
    def test_invalid_bound_or_unknown_complete_rejected(self):
        sid,s=self.make();row=s.usage(1004096)
        for changes in ({'request_token_ceiling':64096},{'usage_complete':True},{'conservative_tokens':0},{'api_calls':0}):
            with self.assertRaises(integrity.IntegrityError):request_accounting.bounded_tokens({**row,**changes},0)
    def test_resume_per_invocation_cost_is_not_double_charged(self):
        total=runner.zero(str(uuid.uuid4()),MODEL,1004096)
        rates={'input':2,'output':10,'cache_read':.1,'cache_write':4}
        for _ in range(2):
            sid,s=self.make();s.accept(assistant(sid));s.accept(result(sid));runner.combine(total,s.usage(1004096),rates)
        self.assertEqual(total['api_calls'],2);self.assertEqual(total['total_tokens'],78)
        self.assertAlmostEqual(total['estimated_cost_usd'],.0002134)

class ClaudeAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((Path(__file__).parents[1]/'claude_code/policy.json').read_text())
        self.legacy={'models':{'legacy':{'automatic':True,'output':.88}}}
        self.state={'day':'2026-10-10','tokens_today':0}
    def hold(self,**kwargs):
        return policy.cash_reservation(self.data,'builder',kwargs.get('allowance',3000000),kwargs.get('rows',[]),
          self.state,kwargs.get('reservations',{}),self.legacy,kwargs.get('bill',{}))
    def test_original_cap_and_retained_route_prices(self):
        self.state['tokens_today']=1000000
        self.assertAlmostEqual(self.hold(),1.35)
        self.assertEqual(self.data['estimated_daily_cost_ceiling'],5)
    def test_f61_remaining_allowance_cannot_be_reset_by_migration(self):
        self.assertEqual(self.hold(allowance=4499),4499*.45/1e6)  # Admission is not permission to requeue F61.
    def test_no_new_cash_budget_or_overlapping_holds(self):
        self.assertAlmostEqual(self.hold(),1.35)
        with self.assertRaises(integrity.IntegrityError):self.hold(reservations={'x':{'reserved_cost_estimate':4}})
    def test_portdan_cash_exemption_keeps_token_charge(self):
        self.state['tokens_today']=1000000
        row={'ts_end':'2026-10-10T00:00:00Z','provider':'custom:portdan','charged_tokens':1000000,'usage_complete':False}
        self.assertAlmostEqual(self.hold(rows=[row]),1.35)
    def test_same_a6api_bill_and_native_receipts_not_duplicated(self):
        rows=[{'ts_end':'2026-10-10T00:00:00Z','runtime':'claude-code','charged_tokens':20,'cost_estimate':.1,'usage_complete':True},
              {'ts_end':'2026-10-10T00:00:00Z','provider':'custom:a6api','charged_tokens':20,'cost_estimate':.2,'usage_complete':True}]
        self.assertAlmostEqual(self.hold(rows=rows,bill={'fresh':True,'day':self.state['day'],'account_day_billed_usd':.4,'account_balance_usd':2}),1.35)
    def test_unknown_claude_usage_must_have_conservative_quote(self):
        row={'ts_end':'2026-10-10T00:00:00Z','runtime':'claude-code','charged_tokens':1004096,'usage_complete':False}
        with self.assertRaises(integrity.IntegrityError):self.hold(rows=[row])
    def test_stale_day_bill_and_invalid_cash_hold_cannot_admit(self):
        row={'ts_end':'2026-10-10T00:00:00Z','provider':'custom:a6api','charged_tokens':10,'usage_complete':False}
        with self.assertRaises(integrity.IntegrityError):self.hold(rows=[row],bill={'fresh':True,'day':'2026-10-09','account_day_billed_usd':0})
        for value in (-1,True,float('nan'),float('inf'),'0'):
            with self.assertRaises(integrity.IntegrityError):self.hold(reservations={'bad':{'reserved_cost_estimate':value}})
    def test_manual_bootstrap_requires_owned_stop_review_and_exact_source(self):
        with tempfile.TemporaryDirectory() as folder:
            ops=Path(folder);(ops/'state').mkdir();stop=ops/'STOP';stop.write_text('Migration')
            pause={'owner':'codex-claude-code-runtime-migration','previous_stop':False,'stop_mtime_ns':stop.stat().st_mtime_ns}
            values={'maintenance-pause.json':pause,'claude-code-activation.json':{'installed':True,'enabled':False,'source_head':'head'},
              'claude-code-source-review.json':{'head':'head','verdict':'pass','independent':True},
              'claude-code-validation.json':{'implementation_sha256':'source','validated_at':__import__('time').time(),
               'vulnerability_snapshot_at':__import__('time').time(),'image_id':'image','checks':{k:True for k in ('foundation','ops','frontend','isolation','lifecycle','resources')}}}
            for name,value in values.items():(ops/'state'/name).write_text(json.dumps(value))
            with patch.object(policy,'authenticated',return_value=True),patch.object(policy,'version_matches',return_value=True),patch.object(policy.subprocess,'check_output',return_value='image'):
                self.assertTrue(policy.bootstrap_ready(self.data,ops,'source'))
                self.assertFalse(policy.bootstrap_ready(self.data,ops,'changed'))
                (ops/'state/maintenance-pause.json').write_text(json.dumps({**pause,'stop_mtime_ns':0}))
                self.assertFalse(policy.bootstrap_ready(self.data,ops,'source'))
    def test_command_and_environment_do_not_grant_host_tools(self):
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'not-a-real-secret','PORTDAN_API_KEY':'fixture'},clear=False):
            env=command.environment('/home/operator')
        self.assertNotIn('ANTHROPIC_API_KEY',env);self.assertNotIn('PORTDAN_API_KEY',env)
        self.assertEqual(env['CLAUDE_CONFIG_DIR'],'/home/operator/.claude')
        self.assertEqual(env['CLAUDE_CODE_MAX_RETRIES'],'0');self.assertEqual(env['CLAUDE_CODE_MCP_ALLOWLIST_ENV'],'1')
        args=command.command(self.data,'id','mcp.json','System',builder=False)
        self.assertIn('--safe-mode',args);self.assertEqual(args[args.index('--tools')+1],'')
        self.assertNotIn('--dangerously-skip-permissions',args)
    def test_worker_retains_claude_partial_usage_and_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            sid,s=ClaudeProtocolTests().make();row=s.usage(1004096);path=Path(folder)/'usage.json';path.write_text(json.dumps(row))
            actual=worker.usage_snapshot(path,Path(folder)/'none.db','id','claude-code')
            self.assertFalse(actual['usage_complete']);self.assertEqual(actual['runtime'],'claude-code')
            self.assertEqual(actual['conservative_tokens'],1004096)
    def test_reviewer_tool_call_denied(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'receipt.json';path.write_text(json.dumps({'role':'reviewer','runtime':'claude-code','status':'running'}))
            with self.assertRaises(ValueError):tool_bridge.answer({'method':'tools/call','params':{'name':'execute','arguments':{'command':'echo forbidden'}}},path)

class ClaudeNativeHistoryTests(unittest.TestCase):
    def test_metadata_is_partial_deduplicated_and_project_scoped(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder);root=home/'.claude/projects/project';root.mkdir(parents=True)
            sid=str(uuid.uuid4());event={'sessionId':sid,'cwd':str(home/'phpretro-preservation'),'type':'assistant','timestamp':'2026-10-10T08:00:00Z','message':assistant(sid)['message']}
            event['message']['content']=[{'type':'text','text':'private conversation must never appear'}]
            file=root/(sid+'.jsonl');file.write_text(json.dumps(event)+'\n'+json.dumps(event))
            rows=native_sessions.collect(home,set());self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['tokens'],35);self.assertFalse(rows[0]['complete'])
            self.assertNotIn('private conversation',json.dumps(rows));self.assertEqual(native_sessions.collect(home,{sid}),[])
            event['cwd']=str(home/'hotel-drogon');file.write_text(json.dumps(event))
            self.assertEqual(native_sessions.collect(home,set()),[])

class ClaudeReviewIndependenceTests(unittest.TestCase):
    def test_separate_sessions_cannot_replace_independent_model_family(self):
        import orchestrator as controller
        unit={'id':'Synthetic','model':'gpt-6-luna'}
        with patch.object(controller,'RUNTIME','claude-code'):
            self.assertFalse(controller.independent_review(unit,'gpt-6.1-sol',{'run_id':str(uuid.uuid4())},'review'))
            self.assertTrue(controller.independent_review(unit,'deepseek-v4.1-flash',{},'review'))
            unit['review_model']='deepseek-v4.1-flash'
            self.assertFalse(controller.independent_review(unit,'deepseek-v4.1-flash',{},'review2'))
    def test_symlink_transcript_is_not_followed(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder);root=home/'.claude/projects/project';root.mkdir(parents=True)
            file=home/'private';file.write_text('{}')
            (root/(str(uuid.uuid4())+'.jsonl')).symlink_to(file)
            self.assertEqual(native_sessions.collect(home,set()),[])

if __name__=='__main__':unittest.main()

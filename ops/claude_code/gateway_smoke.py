#!/usr/bin/env python3
"""Real pinned CLI through the real adapter and synthetic OpenAI upstream.

No external provider calls. Exercises both APIs, resume, cache normalization,
provider identity, fallback holds and credential-free MCP children.
"""
import json,subprocess,sys,tempfile,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrity,request_accounting
from claude_code import command,gateway,protocol,runner

class Evidence:
    def add(self,*args,**kwargs):pass
    def request(self,*args):pass

def case(data,model,builder=False,failure=None):
    with tempfile.TemporaryDirectory(prefix='phpretro-gateway-smoke-') as folder:
        root=Path(folder);(root/'CLAUDE.md').write_text('HOST_CONTEXT_SENTINEL');(root/'AGENTS.md').write_text('HOST_CONTEXT_SENTINEL');sid=str(uuid.uuid4());calls=[];writes=[];settings=data['models'][model]
        total=runner.zero(sid,model,64096);total.update(usage_schema=gateway.SCHEMA,unknown_request_ceilings=[])
        manifest={'_receipt_path':str(root/'receipt.json'),'role':'builder' if builder else 'reviewer',
          'prepared_at':time.time(),'timeout':100,'reserved_tokens':300000,'reserved_cost_estimate':1}
        def fake(endpoint,key,body,timeout):
            assert key in ('synthetic-primary','synthetic-fallback')
            assert 'HOST_CONTEXT_SENTINEL' not in json.dumps(body)
            calls.append({'provider':'a6api' if 'a6api' in endpoint else 'portdan','api':'responses' if endpoint.endswith('/responses') else 'chat','body':body})
            if failure=='fallback' and len(calls)==1:raise gateway.ProviderError(429)
            tool=builder and len(calls)==1
            reported='wrong-model' if failure=='identity' else 'cb/gpt-6-luna' if model=='gpt-6-luna' else model
            if settings['api_mode']=='responses':
                items=[{'type':'function_call','call_id':'call_fixture','name':'mcp__phpretro__execute','arguments':'{"command":"echo fixture"}'}] if tool else [{'type':'message','content':[{'type':'output_text','text':'fixture complete'}]}]
                return {'status':'completed','model':reported,'output':items,'usage':{'input_tokens':35,'output_tokens':4,'total_tokens':39,'input_tokens_details':{'cached_tokens':7},'output_tokens_details':{'reasoning_tokens':0}}}
            message={'content':'fixture complete'}
            if tool:message={'content':None,'reasoning_content':'retained synthetic reasoning','tool_calls':[{'id':'call_fixture','function':{'name':'mcp__phpretro__execute','arguments':'{"command":"echo fixture"}'}}]}
            return {'model':reported,'choices':[{'finish_reason':'tool_calls' if tool else 'stop','message':message}],
              'usage':{'prompt_tokens':35,'completion_tokens':4,'total_tokens':39,'prompt_cache_hit_tokens':7,'prompt_cache_miss_tokens':28,'completion_tokens_details':{'reasoning_tokens':0}}}
        client=gateway.Gateway(data,manifest,model,total,lambda:writes.append(dict(total)),Evidence(),Evidence(),
          {'a6api_api_key':'synthetic-primary','portdan':{'openai':'synthetic-fallback','deepseek':'synthetic-fallback'}},invoke=fake,routes=['a6api','portdan'])
        try:
            mcp=root/'mcp.json';child=root/'child-env.json'
            (root/'mcp.py').write_text('''import json,os,sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({'provider_secret':any(k in os.environ for k in ('ANTHROPIC_AUTH_TOKEN','ANTHROPIC_API_KEY','A6API_API_KEY','PORTDAN_API_KEY'))}))
for line in sys.stdin:
 r=json.loads(line);m=r.get('method');i=r.get('id')
 if i is None:continue
 value=({'protocolVersion':r['params']['protocolVersion'],'capabilities':{'tools':{}},'serverInfo':{'name':'fixture','version':'1'}} if m=='initialize' else {'tools':[{'name':'execute','description':'fixture','inputSchema':{'type':'object','properties':{'command':{'type':'string'}},'required':['command']}}]} if m=='tools/list' else {'content':[{'type':'text','text':'fixture tool success'}]} if m=='tools/call' else {})
 print(json.dumps({'jsonrpc':'2.0','id':i,'result':value}),flush=True)
''')
            mcp.write_text(json.dumps({'mcpServers':{'phpretro':{'command':sys.executable,'args':[str(root/'mcp.py'),str(child)]}} if builder else {}}))
            for step in range(2 if builder else 1):
                client.arm();stream=protocol.Stream(sid,model,['mcp__phpretro__execute'] if builder else [])
                env=command.environment(root);env.update(client.environment(),CLAUDE_CONFIG_DIR=str(root/'config'))
                result=subprocess.run(command.command(data,sid,mcp,'Fixture system',model=model,builder=builder,resume=step>0),
                  input='Fixture task' if not step else 'Continue',env=env,cwd=root,capture_output=True,text=True,timeout=40)
                for line in result.stdout.splitlines():stream.accept(json.loads(line))
                if failure=='identity':
                    assert client.error=='IntegrityError' and total['unknown_api_calls']==1
                    assert len(calls)==1 and not total['usage_complete'];break
                native=stream.usage(64096)
                assert client.last and native['usage_complete'],(result.returncode,stream.error,client.error)
                assert native['total_tokens']==39 and native['input_tokens']==28 and native['cache_read_tokens']==7
                assert stream.outcome()==('continue' if builder and step==0 else 'success')
            assert request_accounting.bounded_tokens(total,total['total_tokens'])==total['conservative_tokens']
            assert any(w['unknown_api_calls']>0 for w in writes),'No durable pretransport hold'
            if builder:
                assert json.loads(child.read_text())['provider_secret'] is False
                assert len(calls)==2
                if settings['api_mode']=='chat':
                    assert any(m.get('reasoning_content')=='retained synthetic reasoning' for m in calls[1]['body']['messages'])
                else:assert any(i.get('type')=='function_call_output' for i in calls[1]['body']['input'])
            if failure=='fallback':
                assert [c['provider'] for c in calls]==['a6api','portdan']
                assert total['unknown_api_calls']==1 and total['conservative_tokens']==64096+39
                assert not total['usage_complete'] and total['provider']=='mixed:a6api-portdan'
            return {'model':model,'builder':builder,'case':failure or 'normal','passed':True,'requests':len(calls)}
        finally:client.close()

def main():
    data=json.loads(Path(__file__).with_name('policy.json').read_text());checks=[]
    for model in ('gpt-6.1-sol','gpt-6-luna','deepseek-v4.1-flash'):
        for builder in (False,True):
            try:checks.append(case(data,model,builder))
            except Exception as exc:checks.append({'model':model,'builder':builder,'passed':False,'error_type':type(exc).__name__,'detail':str(exc)[:120]})
    for failure in ('fallback','identity'):
        try:checks.append(case(data,'gpt-6.1-sol',failure=failure))
        except Exception as exc:checks.append({'case':failure,'passed':False,'error_type':type(exc).__name__,'detail':str(exc)[:120]})
    passed=all(c['passed'] for c in checks);print(json.dumps({'passed':passed,'checks':checks}));return 0 if passed else 1
if __name__=='__main__':raise SystemExit(main())

#!/usr/bin/env python3
"""Real pinned CLI through the real adapter and synthetic OpenAI upstream.

No external provider calls. Exercises both APIs, resume, cache normalization,
provider identity, fallback holds and credential-free MCP children.
"""
import json,subprocess,sys,tempfile,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrity,request_accounting,context_usage,worker,sandbox,runtime_policy
from claude_code import command,gateway,protocol,runner,observations

class Evidence:
    def add(self,*args,**kwargs):pass
    def request(self,*args):pass

def case(data,model,builder=False,failure=None):
    with tempfile.TemporaryDirectory(prefix='phpretro-gateway-smoke-') as folder:
        root=Path(folder);(root/'CLAUDE.md').write_text('HOST_CONTEXT_SENTINEL');(root/'AGENTS.md').write_text('HOST_CONTEXT_SENTINEL');sid=str(uuid.uuid4());calls=[];writes=[];settings=data['models'][model]
        context=context_usage.Recorder(root/'native.context.json',['execute'] if builder else [])
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
            # Match the actual DeepSeek protocol contract, including the native
            # CLI's resumed tool message, rather than accepting every payload.
            assert 'tool_choice' not in body
            if builder and not tool:
                assistant=[m for m in body['messages'] if m.get('tool_calls')]
                assert len(assistant)==1 and assistant[0]['content'] is not None
                assert assistant[0]['reasoning_content']=='retained synthetic reasoning'
                results=[m for m in body['messages'] if m.get('role')=='tool']
                assert len(results)==1 and results[0]['tool_call_id']==assistant[0]['tool_calls'][0]['id']
            message={'content':'fixture complete'}
            if tool:message={'content':None,'reasoning_content':'retained synthetic reasoning','tool_calls':[{'id':'call_fixture','function':{'name':'mcp__phpretro__execute','arguments':'{"command":"echo fixture"}'}}]}
            return {'model':reported,'choices':[{'finish_reason':'tool_calls' if tool else 'stop','message':message}],
              'usage':{'prompt_tokens':35,'completion_tokens':4,'total_tokens':39,'prompt_cache_hit_tokens':7,'prompt_cache_miss_tokens':28,'completion_tokens_details':{'reasoning_tokens':0}}}
        client=gateway.Gateway(data,manifest,model,total,lambda:writes.append(dict(total)),Evidence(),context,
          {'a6api_api_key':'synthetic-primary','portdan':{'openai':'synthetic-fallback','deepseek':'synthetic-fallback'}},invoke=fake,routes=['a6api','portdan'])
        box=None
        try:
            mcp=root/'mcp.json';child=root/'child-env.json'
            if builder:
                # The deployed MCP implementation must negotiate with the real
                # pinned CLI. A mock that echoes any requested protocol version
                # hid an unsupported initialize revision in the live bridge.
                repo=root/'repo';repo.mkdir();(repo/'README.md').write_text('Synthetic bridge fixture')
                subprocess.run(['git','init','--quiet',str(repo)],check=True)
                subprocess.run(['git','-C',str(repo),'add','README.md'],check=True)
                subprocess.run(['git','-C',str(repo),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--quiet','-m','fixture'],check=True)
                subprocess.run(['git','-C',str(repo),'update-ref','refs/remotes/origin/main','HEAD'],check=True)
                rid=str(uuid.uuid4());receipt=root/'mcp-receipt.json'
                integrity.atomic_json(receipt,{'run_id':rid,'runtime':'claude-code','role':'builder','status':'running',
                    'cwd':str(repo),'prepared_at':time.time(),'timeout':100})
                box=sandbox.Sandbox(rid,repo);box.prepare()
            (root/'mcp.py').write_text('''import json,os,sys,runpy
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({'provider_secret':any(k in os.environ for k in ('ANTHROPIC_AUTH_TOKEN','ANTHROPIC_API_KEY','A6API_API_KEY','PORTDAN_API_KEY'))}))
sys.argv=[sys.argv[2],sys.argv[3]]
runpy.run_path(sys.argv[0],run_name='__main__')
''')
            bridge={'command':sys.executable,'args':[str(root/'mcp.py'),str(child),str(Path(__file__).with_name('tool_bridge.py')),str(receipt)] if builder else [],
                'env':{'PHPRETRO_RUNTIME':'claude-code','PHPRETRO_RUNTIME_POLICY':str(runtime_policy.POLICY),'PHPRETRO_OPS':str(runtime_policy.OPS)}}
            mcp.write_text(json.dumps({'mcpServers':{'phpretro':bridge} if builder else {}}))
            for step in range(2 if builder else 1):
                client.arm();stream=protocol.Stream(sid,model,['mcp__phpretro__execute'] if builder else [])
                env=command.environment(root);env.update(client.environment(),CLAUDE_CONFIG_DIR=str(root/'config'))
                result=subprocess.run(command.command(data,sid,mcp,'Fixture system',model=model,builder=builder,resume=step>0),
                  input='Fixture task' if not step else 'Continue',env=env,cwd=root,capture_output=True,text=True,timeout=40)
                for line in result.stdout.splitlines():
                    event=json.loads(line);stream.accept(event)
                    if event.get('type')=='assistant':
                        for part in event.get('message',{}).get('content',[]):
                            if part.get('type')=='tool_use':context.tool(part.get('input',{}).get('command',''))
                    elif event.get('type')=='user':
                        for part in event.get('message',{}).get('content',[]):
                            if part.get('type')=='tool_result':context.data['tool_errors']+=int(part.get('is_error') is True)
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
                assert context.data['tool_errors']==0 and context.data['tool_calls']==1
                if settings['api_mode']=='chat':
                    assert any(m.get('reasoning_content')=='retained synthetic reasoning' for m in calls[1]['body']['messages'])
                    returned=[m['content'] for m in calls[1]['body']['messages'] if m.get('role')=='tool']
                else:
                    returned=[i['output'] for i in calls[1]['body']['input'] if i.get('type')=='function_call_output']
                assert len(returned)==1 and json.loads(returned[0])=={'rc':0,'output':'fixture\n'}, 'Real sandbox output was not retained on native resume'
            if builder:
                # Only disposable synthetic receipt files. These exercise real
                # native tool events and the real durable-worker projection.
                context.finish(False);receipts=root/'state/receipts';receipts.mkdir(parents=True)
                rid=str(uuid.uuid4());receipt=receipts/(rid+'.json');usage=receipt.with_suffix('.usage.json')
                integrity.atomic_json(usage,total)
                integrity.atomic_json(receipt.with_suffix('.context.json'),context.data)
                record={'run_id':rid,'runtime':'claude-code','model':model,'prepared_at':manifest['prepared_at'],
                  'status':'complete','rc':0,'reserved_tokens':manifest['reserved_tokens'],
                  'usage':worker.usage_snapshot(usage,root/'absent.db','',runtime='claude-code')}
                integrity.atomic_json(receipt,record)
                observations.record(receipt,'synthetic-adapter-source',total,context.data)
                record['completed_at']=time.time();integrity.atomic_json(receipt,record)
                proof=observations.recent(root,'synthetic-adapter-source',data['models'])
                assert proof['a6api'][model]['run_id']==rid
                assert 'portdan' not in proof
            if failure=='fallback':
                assert [c['provider'] for c in calls]==['a6api','portdan']
                assert total['unknown_api_calls']==1 and total['conservative_tokens']==64096+39
                assert not total['usage_complete'] and total['provider']=='mixed:a6api-portdan'
            return {'model':model,'builder':builder,'case':failure or 'normal','passed':True,'requests':len(calls)}
        finally:
            client.close()
            if box:box.close();sandbox.assert_absent(box.rid)

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

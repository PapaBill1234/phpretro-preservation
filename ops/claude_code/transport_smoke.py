#!/usr/bin/env python3
"""Real pinned CLI + loopback fake Anthropic transport. No provider credentials.

This verifies CLI behavior, not a real account/provider capability observation.
"""
import http.server,json,os,subprocess,sys,tempfile,threading,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from claude_code import command,protocol

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
        server=self.server;server.calls.append({'max_tokens':body.get('max_tokens'),'tools':[t['name'] for t in body.get('tools',[])],
          'model':body.get('model'),'messages':len(body.get('messages',[])),
          'host_memory_leaked':'HOST_CONTEXT_SENTINEL' in json.dumps(body)})
        if server.mode=='error':
            self.send_response(429);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(b'{"type":"error","error":{"type":"rate_limit_error","message":"fixture"}}');return
        tool=server.mode=='tool' and len(server.calls)==1
        usage={'input_tokens':23,'cache_creation_input_tokens':5,'cache_read_input_tokens':7,'output_tokens':0}
        content={'type':'tool_use','id':'tool_1','name':'mcp__phpretro__execute','input':{'command':'echo fixture'}} if tool else {'type':'text','text':'fixture completed'}
        msg={'id':'msg_'+str(len(server.calls)),'type':'message','role':'assistant','model':'wrong-model' if server.mode=='identity' else body['model'],
             'content':[],'stop_reason':None,'stop_sequence':None,'usage':usage}
        events=[('message_start',{'type':'message_start','message':msg}),
          ('content_block_start',{'type':'content_block_start','index':0,'content_block':{**content,'input':{}} if tool else {'type':'text','text':''}}),
          ('content_block_delta',{'type':'content_block_delta','index':0,'delta':{'type':'input_json_delta','partial_json':json.dumps(content['input'])} if tool else {'type':'text_delta','text':'fixture completed'}}),
          ('content_block_stop',{'type':'content_block_stop','index':0}),
          ('message_delta',{'type':'message_delta','delta':{'stop_reason':'tool_use' if tool else 'end_turn','stop_sequence':None},'usage':{'output_tokens':4}}),
          ('message_stop',{'type':'message_stop'})]
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        for kind,event in events:
            self.wfile.write(('event: '+kind+'\ndata: '+json.dumps(event)+'\n\n').encode());self.wfile.flush()

def case(data,mode,builder=False):
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);server.calls=[];server.mode=mode
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix='phpretro-native-transport-') as folder:
            root=Path(folder);sid=str(uuid.uuid4());mcp=root/'mcp.json'
            env=command.environment(root);env.update(ANTHROPIC_API_KEY='fixture-not-a-credential',
              ANTHROPIC_BASE_URL='http://127.0.0.1:'+str(server.server_port),CLAUDE_CONFIG_DIR=str(root/'config'))
            (root/'CLAUDE.md').write_text('HOST_CONTEXT_SENTINEL')
            (root/'AGENTS.md').write_text('HOST_CONTEXT_SENTINEL')
            (root/'.claude').mkdir();(root/'.claude/settings.json').write_text(json.dumps({'hooks':{'SessionStart':[{'hooks':[{'type':'command','command':'touch '+str(root/'hook-fired')}]}]}}))
            (root/'mcp.py').write_text('''import json,os,sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({'has_api_key':'ANTHROPIC_API_KEY' in os.environ}))
for line in sys.stdin:
 r=json.loads(line);m=r.get('method');i=r.get('id')
 if i is None:continue
 value=({'protocolVersion':r['params']['protocolVersion'],'capabilities':{'tools':{}},'serverInfo':{'name':'fixture','version':'1'}} if m=='initialize' else {'tools':[{'name':'execute','description':'fixture','inputSchema':{'type':'object','properties':{'command':{'type':'string'}},'required':['command']}}]} if m=='tools/list' else {'content':[{'type':'text','text':'fixture tool success'}]} if m=='tools/call' else {})
 print(json.dumps({'jsonrpc':'2.0','id':i,'result':value}),flush=True)
''')
            mcp.write_text(json.dumps({'mcpServers':{'phpretro':{'command':sys.executable,'args':[str(root/'mcp.py'),str(root/'child-env.json')]}} if builder else {}}))
            streams=[];results=[]
            for step in range(2 if builder else 1):
                args=command.command(data,sid,mcp,'Fixture system',resume=step>0,builder=builder)
                # --bare uses the fixture key, never the operator's subscription.
                r=subprocess.run(args+['--bare'],input='Complete fixture' if step==0 else 'Continue',
                  capture_output=True,text=True,cwd=root,env=env,timeout=40)
                stream=protocol.Stream(sid,data['model_roles']['builder' if builder else 'reviewer'],['mcp__phpretro__execute'] if builder else [])
                for line in r.stdout.splitlines():
                    event=json.loads(line)
                    stream.accept(event)
                streams.append(stream);results.append(r.returncode)
            if mode=='identity':
                # The mismatched assistant is rejected while decoding above.
                raise AssertionError('Identity mismatch was not rejected')
            if mode=='error':
                assert len(server.calls)==1,'Automatic paid retry occurred'
                assert not streams[0].usage(1004096)['usage_complete']
                assert streams[0].error=='rate_limit'
            else:
                assert len(server.calls)==len(streams),'Hidden inference call detected'
                assert all(s.usage(1004096)['total_tokens']==39 and s.usage(1004096)['usage_complete'] for s in streams)
                assert all(c['max_tokens']==4096 and c['model']=='claude-sonnet-5-5' and not c['host_memory_leaked'] for c in server.calls)
                assert not (root/'hook-fired').exists()
                if builder:
                    assert streams[0].outcome()=='continue' and streams[1].outcome()=='success'
                    assert streams[0].tool_results,'Tool execution did not complete before resume'
                    assert server.calls[1]['messages']>server.calls[0]['messages']
                    assert json.loads((root/'child-env.json').read_text())['has_api_key'] is False
                else:assert streams[0].outcome()=='success' and server.calls[0]['tools']==[]
            return {'mode':mode,'builder':builder,'passed':True,'requests':len(server.calls)}
    finally:server.shutdown();server.server_close()

def main():
    data=json.loads(Path(__file__).with_name('policy.json').read_text());checks=[]
    for mode,builder in (('text',False),('tool',True),('error',False),('identity',False)):
        try:checks.append(case(data,mode,builder))
        except protocol.control.IntegrityError:
            checks.append({'mode':mode,'builder':builder,'passed':mode=='identity','rejected':True})
        except Exception as exc:checks.append({'mode':mode,'builder':builder,'passed':False,'error_type':type(exc).__name__})
    passed=all(c['passed'] for c in checks)
    print(json.dumps({'schema':'phpretro.claude-transport.v1','passed':passed,'checks':checks}))
    return 0 if passed else 1
if __name__=='__main__':raise SystemExit(main())

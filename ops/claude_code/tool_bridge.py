#!/usr/bin/env python3
"""The sole Claude builder tool: execute inside the owned credential-free sandbox."""
import json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrity as control,sandbox

def answer(request,path):
    method=request.get('method');params=request.get('params',{})
    if method=='initialize':
        version=params.get('protocolVersion')
        if version not in ('2024-11-05','2025-03-26','2025-06-18'):raise ValueError('Unsupported MCP version')
        return {'protocolVersion':version,'capabilities':{'tools':{}},'serverInfo':{'name':'phpretro','version':'1.0.0'}}
    if method=='tools/list':return {'tools':[{'name':'execute','description':'Execute a command in the isolated PHPRetro checkout. No host, credentials or network access.',
      'inputSchema':{'type':'object','properties':{'command':{'type':'string','maxLength':20000},'timeout':{'type':'integer','minimum':1,'maximum':300}},'required':['command'],'additionalProperties':False}}]}
    if method=='ping':return {}
    if method!='tools/call':raise ValueError('Unsupported MCP method')
    receipt=json.loads(path.read_text())
    if receipt.get('runtime')!='claude-code' or receipt.get('role')!='builder' or receipt.get('status')!='running':raise ValueError('Tool role is not admitted')
    if path.with_suffix('.cancel.json').exists():raise ValueError('Run is cancelled')
    if params.get('name')!='execute':raise ValueError('Unapproved tool')
    args=params.get('arguments',{})
    if not isinstance(args,dict) or set(args)-{'command','timeout'} or not isinstance(args.get('command'),str):raise ValueError('Invalid tool input')
    timeout=args.get('timeout',300)
    if type(timeout) is not int or not 1<=timeout<=300:raise ValueError('Invalid tool timeout')
    # The trusted worker persists its original launch time; tool calls cannot extend it.
    started=receipt.get('started_at',receipt.get('prepared_at'))
    if type(started) not in (int,float):raise ValueError('Missing worker deadline')
    remaining=int(started+receipt['timeout']-time.time())
    if remaining<=0:raise ValueError('Worker deadline expired')
    rid=receipt['run_id'];sandbox.container_name(rid)
    if sandbox.inspect(rid) is None:raise ValueError('Sandbox is absent')
    box=sandbox.Sandbox(rid,receipt['cwd'])
    rc,output=box.execute(args['command'],timeout=min(timeout,remaining))
    return {'content':[{'type':'text','text':json.dumps({'rc':rc,'output':output[-12000:]})}],'isError':rc!=0}

def main(path):
    os.umask(0o077)
    for line in sys.stdin:
        request = None
        if len(line)>65536:return 1
        try:
            request=json.loads(line)
            if not isinstance(request,dict):raise ValueError()
            if 'id' not in request:continue
            result=answer(request,path)
            response={'jsonrpc':'2.0','id':request['id'],'result':result}
        except Exception:
            # Never serialize exceptions, Docker metadata, process environment or secrets.
            response={'jsonrpc':'2.0','id':request.get('id') if isinstance(request,dict) else None,'error':{'code':-32602,'message':'PHPRetro tool request denied'}}
        print(json.dumps(response),flush=True)
    return 0

if __name__=='__main__':sys.exit(main(Path(sys.argv[1])))

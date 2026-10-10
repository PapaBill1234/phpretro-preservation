"""Receipt-scoped Anthropic facade for the existing OpenAI-format providers.

No public listener, database, prompt logs or provider credentials in subprocesses.
The CLI gets an ephemeral loopback capability, and every physical upstream call
is durably reserved before transport. Unsupported content fails before transport.
"""
import http.server,json,secrets,stat,threading,time,urllib.error,urllib.request,uuid
from pathlib import Path
import integrity as control,request_accounting as bounds,runtime_policy
import provider_routing as routing

SCHEMA='phpretro.claude-gateway-usage.v2'

def credentials(path):
    path=Path(path);info=path.stat()
    import os
    if path.is_symlink() or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o600:
        raise control.IntegrityError('Private provider credential ownership/mode invalid')
    value=json.loads(path.read_text())
    if not isinstance(value,dict):raise control.IntegrityError('Invalid provider credential source')
    return value

def text(parts):
    if isinstance(parts,str):return parts
    if not isinstance(parts,list):raise control.IntegrityError('Unsupported content')
    if any(not isinstance(p,dict) or p.get('type')!='text' or not isinstance(p.get('text'),str) for p in parts):
        raise control.IntegrityError('Unsupported non-text content')
    return '\n'.join(p['text'] for p in parts)

def chat_request(body,model,reasoning):
    messages=[]
    if body.get('system'):messages.append({'role':'system','content':text(body['system'])})
    for message in body['messages']:
        role=message.get('role');content=message.get('content')
        if role not in ('assistant','user'):raise control.IntegrityError('Unsupported message role')
        if isinstance(content,str):content=[{'type':'text','text':content}]
        if not isinstance(content,list):raise control.IntegrityError('Invalid message content')
        chunks=[];calls=[];results=[]
        for part in content:
            if not isinstance(part,dict):raise control.IntegrityError('Invalid content block')
            kind=part.get('type')
            if kind=='text':chunks.append(text([part]))
            elif kind=='tool_use' and role=='assistant':
                if not isinstance(part.get('id'),str) or not isinstance(part.get('name'),str) or not isinstance(part.get('input'),dict):
                    raise control.IntegrityError('Invalid tool call')
                calls.append({'id':part['id'],'type':'function','function':{'name':part['name'],'arguments':json.dumps(part['input'])}})
            elif kind=='tool_result' and role=='user':
                if not isinstance(part.get('tool_use_id'),str):raise control.IntegrityError('Invalid tool result')
                value=text(part.get('content',[]))
                results.append({'role':'tool','tool_call_id':part['tool_use_id'],'content':('Tool failed: ' if part.get('is_error') else '')+value})
            else:raise control.IntegrityError('Unsupported content block')
        if chunks or calls:
            row={'role':role,'content':'\n'.join(chunks)}
            if calls:
                row['tool_calls']=calls
                remembered={reasoning[c['id']] for c in calls if c['id'] in reasoning}
                if len(remembered)>1:raise control.IntegrityError('Conflicting retained reasoning')
                if remembered:row['reasoning_content']=remembered.pop()
            messages.append(row)
        messages.extend(results)
    tools=[]
    for tool in body.get('tools',[]):
        if tool.get('name')!='mcp__phpretro__execute' or not isinstance(tool.get('input_schema'),dict):
            raise control.IntegrityError('Unapproved gateway tool')
        tools.append({'type':'function','function':{'name':tool['name'],'description':tool.get('description',''),'parameters':tool['input_schema']}})
    request={'model':model,'messages':messages,'max_tokens':bounds.MAX_OUTPUT,'stream':False}
    if tools:request['tools']=tools;request['tool_choice']='auto'
    return request

def responses_request(chat,retained):
    inputs=[]
    for row in chat['messages']:
        if row['role']=='tool':inputs.append({'type':'function_call_output','call_id':row['tool_call_id'],'output':row['content']})
        else:
            if row['content']:inputs.append({'role':row['role'],'content':row['content']})
            calls=row.get('tool_calls',[])
            seen=set()
            for call in calls:
                for item in retained.get(call['id'],[]):
                    identity=item.get('id')
                    if identity not in seen:inputs.append(item);seen.add(identity)
                inputs.append({'type':'function_call','call_id':call['id'],'name':call['function']['name'],'arguments':call['function']['arguments']})
    result={'model':chat['model'],'input':inputs,'max_output_tokens':bounds.MAX_OUTPUT,
      'store':False,'stream':False,'reasoning':{'effort':'low'},'include':['reasoning.encrypted_content']}
    if chat.get('tools'):
        result['tools']=[{'type':'function',**t['function']} for t in chat['tools']]
        result['tool_choice']='auto'
    return result

def usage(raw,mode):
    """Numeric inclusive OpenAI counters -> exclusive Anthropic wire counters.

    Absent cache-write accounting remains unknown unless the provider's usage
    format establishes no separate write category (OpenAI cached_tokens).
    DeepSeek hit+miss must reconcile with the inclusive prompt counter.
    """
    if not isinstance(raw,dict):raise control.IntegrityError('Missing provider usage')
    input_key,output_key=('input_tokens','output_tokens') if mode=='responses' else ('prompt_tokens','completion_tokens')
    prompt=control.nonnegative(raw.get(input_key),'provider input')
    output=control.nonnegative(raw.get(output_key),'provider output')
    details=raw.get('input_tokens_details' if mode=='responses' else 'prompt_tokens_details')
    if isinstance(details,dict) and 'cached_tokens' in details:
        read=control.nonnegative(details['cached_tokens'],'provider cached input');write=0
    elif 'prompt_cache_hit_tokens' in raw and 'prompt_cache_miss_tokens' in raw:
        read=control.nonnegative(raw['prompt_cache_hit_tokens'],'provider cache hit')
        miss=control.nonnegative(raw['prompt_cache_miss_tokens'],'provider cache miss');write=0
        if read+miss!=prompt:raise control.IntegrityError('Cache hit/miss counters disagree')
    else:raise control.IntegrityError('Cache coverage missing')
    if 'cache_creation_input_tokens' in raw:write=control.nonnegative(raw['cache_creation_input_tokens'],'provider cache write')
    if read+write>prompt:raise control.IntegrityError('Cache counters exceed inclusive input')
    if prompt<=0 or output<=0:raise control.IntegrityError('Completed provider response has empty usage')
    total=prompt+output
    if 'total_tokens' in raw and control.nonnegative(raw['total_tokens'],'provider total')!=total:
        raise control.IntegrityError('Provider total disagrees')
    reasoning=raw.get('output_tokens_details' if mode=='responses' else 'completion_tokens_details',{})
    reported=reasoning.get('reasoning_tokens') if isinstance(reasoning,dict) else None
    if reported is not None and control.nonnegative(reported,'provider reasoning')>output:
        raise control.IntegrityError('Reasoning exceeds output')
    return {'input_tokens':prompt-read-write,'output_tokens':output,'cache_read_tokens':read,
      'cache_write_tokens':write,'total_tokens':total,'reasoning_tokens':reported}

def output(raw,mode,model,allowed,chat_reasoning,response_reasoning):
    reported=raw.get('model')
    if not runtime_policy.model_label_matches(model,reported):raise control.IntegrityError('Provider model identity mismatch')
    value=usage(raw.get('usage'),mode);content=[];stop='end_turn'
    if mode=='responses':
        if raw.get('status')!='completed':raise control.IntegrityError('Incomplete provider response')
        items=raw.get('output')
        if not isinstance(items,list):raise control.IntegrityError('Missing response output')
        thought=[x for x in items if isinstance(x,dict) and x.get('type')=='reasoning']
        for item in items:
            kind=item.get('type')
            if kind=='message':
                for part in item.get('content',[]):
                    if part.get('type')!='output_text' or not isinstance(part.get('text'),str):raise control.IntegrityError('Unsupported response output')
                    content.append({'type':'text','text':part['text']})
            elif kind=='function_call':
                content.append(tool_block(item.get('call_id'),item.get('name'),item.get('arguments'),allowed));stop='tool_use'
                response_reasoning[item['call_id']]=thought
            elif kind!='reasoning':raise control.IntegrityError('Unsupported provider output item')
    else:
        choices=raw.get('choices')
        if not isinstance(choices,list) or len(choices)!=1:raise control.IntegrityError('Unexpected provider choices')
        choice=choices[0];message=choice.get('message',{})
        if choice.get('finish_reason') not in ('stop','tool_calls'):raise control.IntegrityError('Truncated provider output')
        if message.get('content'):
            if not isinstance(message['content'],str):raise control.IntegrityError('Unsupported provider text')
            content.append({'type':'text','text':message['content']})
        for call in message.get('tool_calls',[]):
            fn=call.get('function',{})
            content.append(tool_block(call.get('id'),fn.get('name'),fn.get('arguments'),allowed));stop='tool_use'
            if isinstance(message.get('reasoning_content'),str):chat_reasoning[call['id']]=message['reasoning_content']
    if not content:raise control.IntegrityError('Empty provider output')
    wire={'input_tokens':value['input_tokens'],'output_tokens':value['output_tokens'],
      'cache_read_input_tokens':value['cache_read_tokens'],'cache_creation_input_tokens':value['cache_write_tokens']}
    return {'id':'msg_'+uuid.uuid4().hex,'type':'message','role':'assistant','model':model,'content':content,
      'stop_reason':stop,'stop_sequence':None,'usage':wire},value,reported

def tool_block(identity,name,arguments,allowed):
    if name not in allowed or not isinstance(identity,str) or not identity:raise control.IntegrityError('Unexpected provider tool')
    args=json.loads(arguments)
    if not isinstance(args,dict):raise control.IntegrityError('Invalid tool arguments')
    return {'type':'tool_use','id':identity,'name':name,'input':args}

def response_observation(raw,model):
    """Numeric/shape diagnostics only: no content, arguments, keys or error text."""
    if not isinstance(raw,dict):return {'response_object':False}
    result={'response_object':True,'identity_valid':runtime_policy.model_label_matches(model,raw.get('model')),
            'fields':[k for k in ('id','object','model','usage','output','status','error','choices') if k in raw]}
    if raw.get('status') in ('completed','incomplete','failed','cancelled','queued','in_progress'):result['status']=raw['status']
    value=raw.get('usage')
    if isinstance(value,dict):
        counters={}
        for key in ('input_tokens','output_tokens','prompt_tokens','completion_tokens','total_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens','cache_creation_input_tokens'):
            if key in value:counters[key]=value[key] if type(value[key]) in (int,float) and __import__('math').isfinite(value[key]) else 'invalid'
        for key in ('input_tokens_details','prompt_tokens_details','output_tokens_details','completion_tokens_details'):
            if isinstance(value.get(key),dict):
                counters[key]={k:v if type(v) in (int,float) and __import__('math').isfinite(v) else 'invalid'
                  for k,v in value[key].items() if k in ('cached_tokens','reasoning_tokens')}
        result['usage']=counters
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def transport(endpoint,key,body,timeout):
    request=urllib.request.Request(endpoint,data=json.dumps(body).encode(),
      headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.build_opener(NoRedirect).open(request,timeout=timeout) as response:
            data=response.read(16*1024*1024+1)
            if len(data)>16*1024*1024:raise control.IntegrityError('Provider response bound exceeded')
            return json.loads(data)
    except urllib.error.HTTPError as exc:
        error=ProviderError(exc.code);exc.close();raise error from None
    except (TimeoutError,urllib.error.URLError):raise ProviderError(503) from None

class ProviderError(Exception):
    def __init__(self,status):self.status_code=status;super().__init__('Provider request failed')

class Gateway:
    def __init__(self,data,manifest,model,total,checkpoint,journal,context,secret_source,invoke=transport,routes=None):
        self.data=data;self.manifest=manifest;self.model=model;self.total=total;self.checkpoint=checkpoint
        self.journal=journal;self.context=context;self.credentials=secret_source;self.invoke=invoke
        self.routes=routes if routes is not None else runtime_policy.verified_providers(model)
        if not self.routes:raise control.IntegrityError('No admitted model provider route')
        self.guard_spent=0.0;self.quote_spent=0.0;self.unknown_price=False
        self.failed=set();self.recoverable=set();self.providers=set();self.token=secrets.token_urlsafe(32)
        self.reasoning={};self.response_reasoning={};self.lock=threading.Lock();self.armed=False;self.last=None;self.error=None
        self.cancel=Path(manifest['_receipt_path']).with_suffix('.cancel.json')
        self.deadline=manifest['prepared_at']+manifest['timeout']
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.daemon_threads=True;self.server.gateway=self
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def close(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)
    def arm(self):
        with self.lock:self.armed=True;self.last=None;self.error=None
    def environment(self):
        return {'ANTHROPIC_AUTH_TOKEN':self.token,'ANTHROPIC_BASE_URL':'http://127.0.0.1:'+str(self.server.server_port),
          'ANTHROPIC_CUSTOM_MODEL_OPTION':self.model,'ANTHROPIC_MODEL':self.model,
          'ANTHROPIC_DEFAULT_SONNET_MODEL':self.model,'ANTHROPIC_DEFAULT_HAIKU_MODEL':self.model,
          'ANTHROPIC_DEFAULT_OPUS_MODEL':self.model,'CLAUDE_CODE_MAX_CONTEXT_TOKENS':str(bounds.MAX_INPUT),
          'DISABLE_PROMPT_CACHING':'1','CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY':'0'}
    def cancelled(self):
        if self.cancel.exists() or time.time()>=self.deadline:raise InterruptedError('Original deadline/cancellation')
    def wait(self,seconds):
        for _ in range(seconds*10):self.cancelled();time.sleep(.1)

    def call(self,body):
        with self.lock:
            if not self.armed:raise control.IntegrityError('Unadmitted extra CLI request')
            self.armed=False
            if body.get('model')!=self.model or type(body.get('max_tokens')) is not int or not 0<body['max_tokens']<=bounds.MAX_OUTPUT:
                raise control.IntegrityError('CLI model/output bound changed')
            if not isinstance(body.get('messages'),list):raise control.IntegrityError('Missing CLI messages')
            allowed={t.get('name') for t in body.get('tools',[])}
            if allowed and self.manifest['role']!='builder':raise control.IntegrityError('Reviewer requested tools')
            chat=chat_request(body,self.model,self.reasoning);mode=self.data['models'][self.model]['api_mode']
            payload=responses_request(chat,self.response_reasoning) if mode=='responses' else chat
            # UTF-8 byte count deliberately overestimates text/tokenized schema,
            # with 4096 additional tokens for format delimiters. No paid count call.
            input_bound=len(json.dumps(payload,ensure_ascii=False).encode())+4096
            if input_bound>bounds.MAX_INPUT:raise control.IntegrityError('Gateway input bound exceeded')
            def invoke(provider):
                self.cancelled();remaining=self.manifest['reserved_tokens']-self.total['conservative_tokens']
                ceiling=bounds.next_ceiling(max(0,remaining))
                if not ceiling or input_bound+bounds.MAX_OUTPUT>ceiling:
                    raise control.IntegrityError('Remaining original token hold cannot cover request')
                settings=self.data['models'][self.model]
                exempt=provider=='portdan' and self.data['portdan_cost_check']=='user-disabled'
                cash=0 if exempt else ((ceiling-bounds.MAX_OUTPUT)*max(settings[k] for k in ('input','cache_read','cache_write'))+bounds.MAX_OUTPUT*settings['output'])/1e6
                if self.guard_spent+cash>self.manifest['reserved_cost_estimate']+1e-9:
                    raise control.IntegrityError('Remaining original spending hold cannot cover request')
                key=routing.credential(self.credentials,provider,self.model)
                self.providers.add(provider);self.total['provider']='mixed:a6api-portdan' if len(self.providers)>1 else 'custom:'+provider
                self.total['api_calls']+=1;self.total['unknown_api_calls']+=1
                self.total['unknown_request_ceilings'].append(ceiling);self.total['conservative_tokens']+=ceiling
                self.guard_spent+=cash
                priced=provider=='a6api' or self.model=='gpt-6.1-sol'
                quote=((ceiling-bounds.MAX_OUTPUT)*max(settings[k] for k in ('input','cache_read','cache_write'))+bounds.MAX_OUTPUT*settings['output'])/1e6
                if priced:self.quote_spent+=quote
                else:self.unknown_price=True
                if self.unknown_price:self.total.pop('estimated_cost_usd',None);self.total['cost_status']='unknown-price'
                else:self.total['estimated_cost_usd']=self.quote_spent
                self.total['usage_complete']=False;self.checkpoint()
                self.journal.add('provider_request','Gateway request admitted',provider=provider,request=self.total['api_calls'])
                self.context.request(input_bound,input_bound,0)
                endpoint=self.data['providers'][provider]['base_url']+('/responses' if mode=='responses' else '/chat/completions')
                raw=self.invoke(endpoint,key,payload,max(.1,min(120,self.deadline-time.time())))
                observed=self.context.data.setdefault('provider_response_observations',[])
                if len(observed)<16:observed.append(response_observation(raw,self.model));self.context.save()
                message,row,reported=output(raw,mode,self.model,allowed,self.reasoning,self.response_reasoning)
                # Preserve actual observed usage even when it exceeds the estimate.
                if row['total_tokens']>ceiling:
                    self.total['conservative_tokens']+=row['total_tokens']-ceiling;self.checkpoint()
                    raise control.IntegrityError('Provider exceeded bounded request allowance')
                for k in ('input_tokens','output_tokens','cache_read_tokens','cache_write_tokens','total_tokens'):self.total[k]+=row[k]
                self.total['unknown_api_calls']-=1;self.total['unknown_request_ceilings'].pop()
                self.total['completed_api_calls']+=1;self.total['usage_known_calls']+=1
                self.total['conservative_tokens']+=row['total_tokens']-ceiling
                actual_quote=sum(row[k]*settings[p] for k,p in (('input_tokens','input'),('output_tokens','output'),('cache_read_tokens','cache_read'),('cache_write_tokens','cache_write')))/1e6
                self.guard_spent+=(0 if exempt else actual_quote)-cash
                if priced:self.quote_spent+=actual_quote-quote
                if not self.unknown_price:self.total['estimated_cost_usd']=self.quote_spent
                self.total['usage_complete']=self.total['unknown_api_calls']==0
                self.total['cost_status']='unknown-price' if self.unknown_price else 'quoted-estimate'
                if row['output_tokens']>bounds.MAX_OUTPUT or row['input_tokens']+row['cache_read_tokens']+row['cache_write_tokens']>ceiling-bounds.MAX_OUTPUT:
                    self.checkpoint();raise control.IntegrityError('Provider reported usage beyond actual request bounds')
                self.total['reported_model']=reported
                self.last={'usage':row,'provider':provider,'reported_model':reported};self.checkpoint()
                return message
            return routing.call(self.routes,invoke,self.failed,wait=self.wait,recoverable=self.recoverable)

def events(message):
    yield 'message_start',{'type':'message_start','message':{**message,'content':[],'stop_reason':None,'usage':{**message['usage'],'output_tokens':0}}}
    for i,part in enumerate(message['content']):
        tool=part['type']=='tool_use'
        yield 'content_block_start',{'type':'content_block_start','index':i,'content_block':{**part,'input':{}} if tool else {'type':'text','text':''}}
        yield 'content_block_delta',{'type':'content_block_delta','index':i,'delta':{'type':'input_json_delta','partial_json':json.dumps(part['input'])} if tool else {'type':'text_delta','text':part['text']}}
        yield 'content_block_stop',{'type':'content_block_stop','index':i}
    yield 'message_delta',{'type':'message_delta','delta':{'stop_reason':message['stop_reason'],'stop_sequence':None},'usage':{'output_tokens':message['usage']['output_tokens']}}
    yield 'message_stop',{'type':'message_stop'}

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version='HTTP/1.0'
    def log_message(self,*args):pass
    def authorized(self):return secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+self.server.gateway.token)
    def reply(self,status,value):
        data=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_POST(self):
        if not self.authorized():self.reply(401,{'error':{'type':'authentication_error','message':'Loopback credential required'}});return
        g=self.server.gateway
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=2*1024*1024:raise control.IntegrityError('Request body bound')
            body=json.loads(self.rfile.read(length))
            if self.path.split('?')[0]=='/v1/messages/count_tokens':
                self.reply(200,{'input_tokens':len(json.dumps(body,ensure_ascii=False).encode())+4096});return
            if self.path.split('?')[0]!='/v1/messages':self.reply(404,{'error':{'type':'not_found_error','message':'Unsupported endpoint'}});return
            message=g.call(body)
            if body.get('stream') is not True:self.reply(200,message);return
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
            for kind,event in events(message):self.wfile.write(('event: '+kind+'\ndata: '+json.dumps(event)+'\n\n').encode());self.wfile.flush()
        except Exception as exc:
            g.error=type(exc).__name__
            status=exc.status_code if isinstance(exc,ProviderError) else 400
            try:self.reply(status,{'type':'error','error':{'type':'rate_limit_error' if status==429 else 'api_error','message':'Receipt-scoped request failed'}})
            except OSError:pass

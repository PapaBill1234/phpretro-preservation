"""Strict Claude CLI stream evidence. No CLI/network/credential access."""
import math
import integrity as control

SCHEMA='phpretro.claude-cli-usage.v1'
COUNTERS={'input_tokens':'input_tokens','output_tokens':'output_tokens',
          'cache_read_tokens':'cache_read_input_tokens','cache_write_tokens':'cache_creation_input_tokens'}

def counters(raw):
    if not isinstance(raw,dict):raise control.IntegrityError('Claude usage is not an object')
    values={k:control.nonnegative(raw.get(v),v) for k,v in COUNTERS.items()}
    values['total_tokens']=sum(values.values())
    return values

class Stream:
    def __init__(self, session_id, model, tools=()):
        self.sid=session_id;self.model=model;self.tools=set(tools)
        self.initialized=False;self.messages={};self.result=None;self.text=[]
        self.tool_uses={};self.tool_results=[];self.error=None

    def accept(self,event):
        if not isinstance(event,dict):raise control.IntegrityError('Claude event is not an object')
        if event.get('session_id') not in (None,self.sid):raise control.IntegrityError('Claude session changed')
        kind=event.get('type')
        if kind=='system' and event.get('subtype')=='init':
            if self.initialized:raise control.IntegrityError('Duplicate Claude initialization')
            if event.get('model')!=self.model:raise control.IntegrityError('Unexpected Claude model identity')
            tools=event.get('tools')
            if not isinstance(tools,list) or set(tools)!=self.tools:raise control.IntegrityError('Unexpected Claude tools')
            plugins=event.get('plugins',[])
            if not isinstance(plugins,list) or any(not isinstance(p,dict) or p.get('path')!='builtin' or
                p.get('name') not in ('cc-plugin-agents-md','cc-plugin-plugin-authoring') for p in plugins):
                raise control.IntegrityError('Unexpected Claude plugins')
            if event.get('skills') not in (None,[]) or event.get('slash_commands') not in (None,[]):
                raise control.IntegrityError('Unexpected Claude skills or commands')
            self.initialized=True
        elif kind=='assistant':
            message=event.get('message',{})
            if event.get('is_api_error_message') is True and message.get('model')=='<synthetic>':
                self.error=event.get('error') if event.get('error') in ('rate_limit','authentication_failed','billing_error','overloaded','server_error') else 'provider_unavailable'
                return
            if not isinstance(message,dict) or message.get('model')!=self.model:raise control.IntegrityError('Unexpected assistant model')
            identity=message.get('id')
            if not isinstance(identity,str) or not 0<len(identity)<=200:raise control.IntegrityError('Missing Claude message identity')
            usage=counters(message.get('usage'))
            previous=self.messages.get(identity)
            if previous and any(usage[k]<previous[k] for k in COUNTERS):raise control.IntegrityError('Claude message usage decreased')
            self.messages[identity]=usage
            for part in message.get('content',[]):
                if not isinstance(part,dict):raise control.IntegrityError('Invalid Claude content')
                if part.get('type')=='text' and isinstance(part.get('text'),str):self.text.append(part['text'])
                if part.get('type')=='tool_use':
                    if part.get('name') not in self.tools:raise control.IntegrityError('Unapproved Claude tool')
                    self.tool_uses[part.get('id')]=part
        elif kind=='user':
            for part in event.get('message',{}).get('content',[]):
                if isinstance(part,dict) and part.get('type')=='tool_result':self.tool_results.append(part)
        elif kind=='result':
            if self.result is not None:raise control.IntegrityError('Duplicate Claude terminal result')
            self.result=event

    def usage(self, ceiling):
        known={k:sum(row[k] for row in self.messages.values()) for k in (*COUNTERS,'total_tokens')}
        complete=False
        if self.result and self.initialized:
            final=counters(self.result.get('usage'))
            turns=control.nonnegative(self.result.get('num_turns'),'Claude turns')
            if turns>2 or turns==2 and self.result.get('subtype')!='error_max_turns':
                raise control.IntegrityError('One-request CLI contract exceeded')
            # Stream assistant snapshots precede the final message_delta and
            # may report output=0. Input/cache must agree; only the final
            # one-request result supplies the completed output count.
            complete=bool(len(self.messages)==1 and turns in (1,2) and
              all(final[k]==known[k] for k in ('input_tokens','cache_read_tokens','cache_write_tokens')) and
              final['output_tokens']>=known['output_tokens'])
            if complete:known=final
        # A missing or inconsistent final result is never a zero-cost inference.
        if len(self.messages)>1:raise control.IntegrityError('Multiple CLI requests in a one-request invocation')
        conservative=known['total_tokens'] if complete else max(ceiling,known['total_tokens'])
        row={**known,'runtime':'claude-code','usage_schema':SCHEMA,'api_calls':1,
             'completed_api_calls':1 if complete else 0,'unknown_api_calls':0 if complete else 1,
             'usage_known_calls':1 if complete else 0,'usage_complete':complete,
             'conservative_tokens':conservative,'request_token_ceiling':ceiling,
             'input_includes_cache':False,'session_id':self.sid,'provider':'unknown:claude-code',
             'model':self.model,'accounting_source':'claude-cli-stream','cost_status':'api-equivalent-estimate'}
        cost=self.result.get('total_cost_usd') if self.result else None
        if type(cost) in (int,float) and math.isfinite(cost) and cost>=0:row['cli_conversation_cost_usd']=cost
        return row

    def outcome(self):
        if not self.initialized or not self.result:return 'unavailable'
        if self.result.get('subtype')=='error_max_turns':return 'continue'
        if self.result.get('subtype')=='success' and self.result.get('is_error') is False:return 'success'
        return 'unavailable'

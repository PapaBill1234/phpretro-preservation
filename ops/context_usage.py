"""Bounded metadata-only OpenHands resource evidence; never retain conversation text."""
import hashlib, time
import integrity as control

class Recorder:
    def __init__(self,path,enabled_tools=None):
        self.path=path; self.commands=set(); self.failed=False
        self.data={'schema':'phpretro.context-usage.v1','complete':False,
                   'enabled_tools':['execute'] if enabled_tools is None else list(enabled_tools),
                   'tool_calls':0,'tool_errors':0,'repeated_commands':0,'events':0,
                   'requests':[],'requests_truncated':False,'brief_chars':0}
    def save(self):
        self.data['updated_at']=time.time()
        try:control.atomic_json(self.path,self.data)
        except OSError:self.failed=True
    def request(self,total,without_tools,system):
        if len(self.data['requests'])<128:
            self.data['requests'].append({'estimated_context_tokens':max(0,int(total)),
                'estimated_tool_schema_tokens':max(0,int(total)-int(without_tools)),
                'estimated_system_tokens':max(0,int(system))})
        else:self.data['requests_truncated']=True
        self.save()
    def tool(self,command):
        digest=hashlib.sha256(command.encode()).digest()
        self.data['tool_calls']+=1
        self.data['repeated_commands']+=int(digest in self.commands)
        if len(self.commands)<4096:self.commands.add(digest)
        self.save()
    def finish(self,complete):
        self.data['complete']=bool(complete and not self.failed)
        self.save()

def summary(raw):
    """Validate evidence before exposing counts. No commands, paths or text."""
    if not isinstance(raw,dict) or raw.get('schema')!='phpretro.context-usage.v1':raise ValueError()
    keys=('tool_calls','tool_errors','repeated_commands','events','brief_chars')
    if any(type(raw.get(k)) is not int or not 0<=raw[k]<=100000000 for k in keys):raise ValueError()
    rows=raw.get('requests')
    if not isinstance(rows,list) or len(rows)>128:raise ValueError()
    clean=[]
    for r in rows:
        names=('estimated_context_tokens','estimated_tool_schema_tokens','estimated_system_tokens')
        if not isinstance(r,dict) or any(type(r.get(k)) is not int or not 0<=r[k]<=100000000 for k in names):raise ValueError()
        clean.append({k:r[k] for k in names})
    enabled=raw.get('enabled_tools')
    if enabled not in ([],['execute']) or not enabled and raw['tool_calls']:
        raise ValueError()
    complete=raw.get('complete') is True
    return {**{k:raw[k] for k in keys},'complete':complete,'requests':len(rows),
            'first_context_tokens':clean[0]['estimated_context_tokens'] if clean else None,
            'peak_context_tokens':max((r['estimated_context_tokens'] for r in clean),default=None),
            'peak_tool_schema_tokens':max((r['estimated_tool_schema_tokens'] for r in clean),default=None),
            'unused_tools':list(enabled) if complete and clean and raw['tool_calls']==0 else [],
            'usage_status':'complete' if complete and clean and not raw.get('requests_truncated') else 'partial'}

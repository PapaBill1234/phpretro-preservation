"""Read only the dedicated Canvas API; publish metadata, never its agent config."""
import datetime,json,subprocess,time,urllib.parse,urllib.request,uuid,os
from pathlib import Path

_cache=None

def timestamp(value):
    try:return datetime.datetime.fromisoformat(str(value).replace('Z','+00:00')).timestamp()
    except ValueError:return None

def normalize(row):
    try:identity=str(uuid.UUID(row['id']))
    except (ValueError,KeyError,TypeError,AttributeError):return None
    metrics=row.get('metrics') or {}
    if not isinstance(metrics,dict):metrics={}
    usage=metrics.get('accumulated_token_usage') or {}
    if not isinstance(usage,dict):usage={}
    def n(key):
        value=usage.get(key)
        return value if type(value) is int and 0<=value<10**12 else None
    prompt,output=n('prompt_tokens'),n('completion_tokens')
    return {'id':identity,'runtime':'openhands-ui','unit':'Interactive','role':'interactive',
      'model':str(row.get('current_model_id') or metrics.get('model_name') or 'Unknown')[:100],
      'status':row.get('execution_status') if row.get('execution_status') in ('idle','running','paused','waiting_for_confirmation','finished','error','stuck','deleting') else 'unknown',
      'started':timestamp(row.get('created_at')),'ended':timestamp(row.get('updated_at')),
      'input':prompt,'output':output,'tokens':prompt+output if prompt is not None and output is not None else None,
      'cached':n('cache_read_tokens'),'complete':False,'context_complete':False,'context':{},'context_requests':[],
      'unused_tools':[],'skills':{'activated':[str(s)[:100] for s in row.get('activated_knowledge_skills',[])[:100]],
                              'invoked':[str(s)[:100] for s in row.get('invoked_skills',[])[:100]]},
      'journal_available':False,'session_url':'/canvas/','accounting_note':'Canvas metrics; call completeness not asserted. Independent interactive budget.'}

def collect():
    global _cache
    try:
        activation=json.loads((Path(os.environ.get('PHPRETRO_OPS',Path.home()/'phpretro-ops'))/'state/claude-code-activation.json').read_text())
        if activation.get('installed') is True:return {'collected_at':time.time(),'available':False,'retired':True,'sessions':[],'truncated':False}
    except (OSError,ValueError):pass
    if _cache and time.time()-_cache['collected_at']<30:return _cache
    result={'collected_at':time.time(),'available':False,'sessions':[],'truncated':False}
    try:
        key=subprocess.check_output(['docker','exec','phpretro-openhands-ui','cat',
          '/home/openhands/.openhands/agent-canvas/api-key.txt'],text=True,stderr=subprocess.DEVNULL,timeout=3).strip()
        page=None
        for _ in range(5):
            path='/api/conversations/search?limit=100'+('&page_id='+urllib.parse.quote(page) if page else '')
            request=urllib.request.Request('http://127.0.0.1:38082'+path,headers={'X-Session-API-Key':key})
            with urllib.request.urlopen(request,timeout=3) as response:
                raw=response.read(8_000_001)
                if len(raw)>8_000_000:raise ValueError('oversized Canvas metadata')
                data=json.loads(raw)
            for row in data['items']:
                safe=normalize(row)
                if safe:result['sessions'].append(safe)
            page=data.get('next_page_id')
            if not page:break
        result.update(available=True,truncated=bool(page))
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):pass
    _cache=result
    return result

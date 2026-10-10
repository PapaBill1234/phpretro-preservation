"""Bounded read-only Claude transcript metadata for this project only.

No auth/config files. No conversation text published. Transcripts are lower-bound
usage evidence, not complete provider bills; controller session IDs deduplicate.
"""
import json,uuid,time,re
from pathlib import Path
import doctor_sessions as doctor
from claude_code import protocol

def collect(home,exclude):
    root=home/'.claude/projects';allowed=(home/'phpretro-preservation',home/'work',home/'phpretro-claude-code/migration')
    if root.is_symlink():return []
    rows=[];candidates=[]
    for path in root.glob('*/*.jsonl'):
        try:
            if not path.is_symlink() and path.resolve().is_relative_to(root.resolve()) and not path.parent.is_symlink() and path.stat().st_size<=4_000_000:candidates.append((path.stat().st_mtime,path))
        except OSError:continue
    for ended,path in sorted(candidates,reverse=True)[:50]:
        try:
            sid=str(uuid.UUID(path.stem))
            if sid!=path.stem or sid in exclude:continue
            events=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            relevant=[e for e in events if isinstance(e,dict) and e.get('sessionId')==sid and
                isinstance(e.get('cwd'),str) and not any('hotel-drogon' in part.lower() for part in Path(e['cwd']).parts)
                and any(Path(e['cwd']).resolve().is_relative_to(p.resolve()) for p in allowed)]
            if not relevant:continue
            messages={};failed=False;model=None;started=None
            for event in relevant:
                started=started or doctor.timestamp(event.get('timestamp'))
                if event.get('type')!='assistant':continue
                message=event.get('message',{});failed=failed or event.get('isApiErrorMessage') is True or event.get('is_api_error_message') is True
                if not isinstance(message.get('model'),str) or not re.fullmatch(r'claude-[a-zA-Z0-9._-]{1,80}',message['model']):continue
                if not isinstance(message.get('id'),str):continue
                model=message['model'];value=protocol.counters(message.get('usage'))
                previous=messages.get(message['id'])
                if previous and any(value[k]<previous[k] for k in protocol.COUNTERS):continue
                messages[message['id']]=value
            totals={k:sum(u[k] for u in messages.values()) for k in (*protocol.COUNTERS,'total_tokens')}
            rows.append({'id':sid,'native_session_id':sid,'runtime':'claude-code','unit':'Interactive','role':'interactive',
              'model':model or 'Unknown','provider':'anthropic:claude-code','status':'failed' if failed else 'incomplete',
              'rc':None,'started':started or ended,'ended':ended,'tokens':totals['total_tokens'] if messages else None,
              'input':totals['input_tokens'] if messages else None,'output':totals['output_tokens'] if messages else None,
              'cached':totals['cache_read_tokens'] if messages else None,'cache_write':totals['cache_write_tokens'] if messages else None,
              'complete':False,'context_complete':False,'context':{},'context_requests':[],'unused_tools':[],
              'journal_available':False,'skills':{'activated':[],'invoked':[],'coverage':'Native transcript metadata only; full context/inference completeness is unknown.'}})
        except (OSError,ValueError,TypeError,KeyError,protocol.control.IntegrityError):continue
    return rows

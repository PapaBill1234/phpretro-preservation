"""Deterministic model, readiness and immutable measurement helpers.

No provider calls or runtime-state writes. Completion observers write only
their immutable process receipt; the orchestrator remains the only state writer.
"""
from __future__ import annotations
import hashlib,json,re,subprocess,threading,time
from datetime import datetime,timezone
from pathlib import Path

READY_TARGET = 8
RISK_PATHS = ('internal/auth','internal/account','internal/session','internal/security',
              'internal/audit','internal/staff','internal/polaris','internal/cache',
              'internal/storage','internal/persistence','internal/database','internal/server',
              'migrations','schema')
RISK_WORDS = re.compile(r'\b(?:security|auth(?:entication|orization)?|sessions?|passwords?|csrf|ssrf|xss|totp|2fa|persist\w*|durab\w*|transactions?|replay|database|mariadb|redis|secrets?)\b',re.I)

def high_risk(unit, diff=''):
    paths=[str(p).split('*',1)[0].rstrip('/') for p in unit.get('paths',[])]
    return (any(p==r or p.startswith(r+'/') or r.startswith(p+'/') for p in paths for r in RISK_PATHS)
            or any(p.endswith('.sql') for p in paths)
            or bool(RISK_WORDS.search(' '.join([str(unit.get('title','')),*unit.get('acceptance',[])])))
            or any('a/'+r in diff or 'b/'+r in diff for r in RISK_PATHS))

def reasoning(role, unit=None, diff=''):
    if role=='planner': return 'low'
    if role=='reviewer': return 'medium' if high_risk(unit or {},diff) else 'low'
    return 'medium'

def priority(unit):
    ranks={'critical':0,'blocker':0,'security':0,'high':1,'medium':2,'low':3,'minor':3}
    return (ranks.get(str(unit.get('severity','medium')).lower(),2),str(unit.get('id','')))

def overlap(a,b):
    if isinstance(a,str): a=[a]
    if isinstance(b,str): b=[b]
    def stem(p): return re.split(r'[*?\[]',str(p),1)[0].rstrip('/')
    return any(not stem(x) or not stem(y) or stem(x)==stem(y) or stem(x).startswith(stem(y)+'/') or stem(y).startswith(stem(x)+'/') for x in a or [] for y in b or [])

def evidence_ready(unit, repo):
    if not unit.get('paths') or not unit.get('acceptance') or not unit.get('tests'): return False
    fixtures=list(unit.get('fixtures') or [])
    if unit.get('design_doc'): fixtures.append(unit['design_doc'])
    if not fixtures: return False
    for item in fixtures:
        if not isinstance(item,str) or not item or Path(item).is_absolute(): return False
        p=repo/item
        if any(part in ('.','..') or part.startswith('.') or re.search(r'(?i)secret|credential|\.env',part) for part in Path(item).parts): return False
        if p.is_symlink() or not p.resolve().is_relative_to(repo.resolve()) or not p.is_file(): return False
    return True

def ready_buffer(roadmap,repo,unit_cap,now=None):
    now=time.time() if now is None else now
    selected=[];paths=[]
    for u in sorted(roadmap.values(),key=priority):
        if u.get('status')!='todo' or u.get('split_requested') or int(u.get('attempts',0))>=4 or int(u.get('tokens',0))>=unit_cap or float(u.get('provider_retry_at',0))>now: continue
        if any(roadmap.get(d,{}).get('status')!='merged' for d in u.get('depends_on',[])): continue
        if not evidence_ready(u,repo) or overlap(u.get('paths'),paths): continue
        selected.append(u['id']);paths.extend(u.get('paths') or [])
    return selected

def revision(roadmap,target,repo):
    # Builder lifecycle/counters may advance during planning; immutable contract
    # identity/topology and the chosen parent's eligibility must remain exact.
    keys=('id','revision_id','paths','depends_on','acceptance','tests','fixtures','design_doc','title','severity')
    board={uid:{k:u.get(k) for k in keys} for uid,u in sorted(roadmap.items())}
    source={}
    for name in [target.get('design_doc'),*(target.get('fixtures') or [])]:
        if not name: continue
        p=repo/name
        if p.is_symlink() or not p.resolve().is_relative_to(repo.resolve()) or not p.is_file(): raise ValueError('planning source missing/escaping')
        if any(part.startswith('.') or re.search(r'(?i)secret|credential|\.env',part) for part in Path(name).parts): raise ValueError('secret source forbidden')
        source[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    data={'board':board,'parent_status':target.get('status'),'parent_retries':target.get('planner_retries',0),'split_requested':bool(target.get('split_requested')),'source':source}
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()

class Completion:
    """Observe process exit/deadline independently of serial review/merge work."""
    def __init__(self,proc,started,timeout,kill,receipt,clock=time.monotonic,wall=time.time):
        self.proc=proc;self.started=started;self.deadline=started+timeout
        self.clock=clock;self.wall=wall;self.kill=kill;self.receipt=receipt
        self.rc=None;self.ended=None;self.ended_wall=None;self.error=None
        self.thread=threading.Thread(target=self.observe,daemon=True)
    def start(self): self.thread.start();return self
    def observe(self):
        try:
            try: self.rc=self.proc.wait(timeout=max(.01,self.deadline-self.clock()))
            except subprocess.TimeoutExpired:
                self.kill(self.proc);self.rc=124
            self.ended=self.clock();self.ended_wall=self.wall()
            self.receipt(self)
        except Exception as exc: self.error=exc
    def join(self):
        self.thread.join()
        if self.error: raise RuntimeError('completion receipt unavailable') from self.error
        return self.rc

def iso(value): return datetime.fromtimestamp(value,timezone.utc).isoformat()

def metrics(events,start,end):
    """Occupancy from exit receipts only; missing historical data stays unknown."""
    def timestamp(row):
        try: return datetime.fromisoformat(row['ts'].replace('Z','+00:00')).timestamp()
        except (ValueError,TypeError,KeyError): return None
    dispatch={};completed={};merges=[]
    for row in events:
        ts=timestamp(row)
        if ts is None: continue
        rid=row.get('run_id')
        if row.get('kind')=='process_dispatched' and row.get('role')=='builder' and rid: dispatch[rid]=(ts,row.get('unit'))
        if row.get('kind')=='process_completed' and row.get('role')=='builder' and rid: completed[rid]=ts
        if row.get('kind')=='merged' and start<=ts<=end: merges.append((ts,row.get('unit')))
    seconds=sum(max(0,min(completed.get(rid,end),end)-max(ts,start)) for rid,(ts,_) in dispatch.items() if ts<=end)
    durations=[];seen=set()
    for ts,uid in sorted(merges):
        if uid in seen: continue
        starts=[t for t,u in dispatch.values() if u==uid and t<=ts]
        if starts: durations.append((ts-min(starts))/60);seen.add(uid)
    durations.sort()
    median=None if not durations else durations[len(durations)//2] if len(durations)%2 else sum(durations[len(durations)//2-1:len(durations)//2+1])/2
    return {'observed_seconds':max(0,end-start),'average_builders':seconds/(end-start) if dispatch and end>start else None,'median_minutes_per_merged_unit':median,'timed_merged_units':len(durations),'builder_dispatches':len(dispatch),'completed_builders':len(completed),'meaning':'Git delivery timing, not implementation or parity completion'}

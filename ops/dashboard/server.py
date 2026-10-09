#!/usr/bin/env python3
"""PHPRetro monitoring: Python stdlib, loopback HTTP, read-only except STOP."""
import sys
import ast, collections, datetime as dt, http.server, json, math, os, re, secrets, shutil, socket, sqlite3, statistics, subprocess, threading, time
from pathlib import Path
HOME=Path.home(); ROOT=Path(os.environ.get('PHPRETRO_DASHBOARD',HOME/'phpretro-dashboard')); REPO=Path(os.environ.get('PHPRETRO_REPO',HOME/'phpretro-preservation')); OPS=Path(os.environ.get('PHPRETRO_OPS',HOME/'phpretro-ops'))
sys.path.insert(0,str(REPO/'ops'))
import telemetry, dashboard_state, progress, billing
TOKEN=secrets.token_urlsafe(32); CACHE={}; MEM={}; SOURCES={}; LOCK=threading.Lock()

# Addendum telemetry helpers
HDB=ROOT/'history.sqlite3'
def history_db():
    con=sqlite3.connect(HDB,timeout=.2); con.row_factory=sqlite3.Row; con.execute('CREATE TABLE IF NOT EXISTS snapshots(ts REAL PRIMARY KEY, merged INTEGER, total INTEGER, tokens REAL, cost REAL, merges INTEGER, running INTEGER, health TEXT)'); con.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)'); con.execute('CREATE TABLE IF NOT EXISTS history(ts REAL PRIMARY KEY,payload TEXT)'); con.execute('CREATE TABLE IF NOT EXISTS balance_snapshots(ts REAL PRIMARY KEY,balance REAL NOT NULL)'); con.commit(); return con
def save_history(data):
    try:
        con=history_db(); now=time.time(); row=con.execute('SELECT ts FROM snapshots ORDER BY ts DESC LIMIT 1').fetchone(); k=data.get('kpi',{})
        if not row or now-row[0]>=300 or not con.execute('SELECT 1 FROM history LIMIT 1').fetchone(): con.execute('INSERT OR REPLACE INTO snapshots VALUES(?,?,?,?,?,?,?,?)',(now,k.get('merged'),k.get('total'),k.get('tokens_today'),k.get('cost_today'),k.get('merges_7d'),len(data.get('live',[])),data.get('health',{}).get('color'))); con.execute('DELETE FROM snapshots WHERE ts<?',(now-90*86400,)); con.execute('INSERT OR REPLACE INTO history VALUES(?,?)',(now,json.dumps(data))); con.execute('DELETE FROM history WHERE ts<?',(now-90*86400,)); con.commit()
        count=con.execute('SELECT COUNT(*) FROM history').fetchone()[0]; stride=max(1,math.ceil(count/1000)); rows=[{'ts':r[0],**json.loads(r[1])} for r in con.execute('SELECT ts,payload FROM history WHERE rowid % ? = 0 OR ts=(SELECT MAX(ts) FROM history) ORDER BY ts',(stride,))]; bal=con.execute("SELECT value FROM settings WHERE key='balance'").fetchone(); con.close(); return rows,(number(bal[0]) if bal else None)
    except (sqlite3.Error,ValueError,TypeError,OSError): return [],None
def redact(s):
    s=re.sub(r'(?i)authorization\s*:\s*[^\s]+','Authorization: [redacted]',s); s=re.sub(r'\bsk-[A-Za-z0-9_-]{12,}\b','[redacted-key]',s); s=re.sub(r'(?<![A-Za-z0-9])[A-Fa-f0-9]{32,}(?![A-Za-z0-9])','[redacted-hex]',s); return re.sub(r'(?<![A-Za-z0-9])[A-Za-z0-9+/]{40,}={0,2}(?![A-Za-z0-9])','[redacted-base64]',s)
def parity(units):
    root=REPO/'stage3-original-phpretro'; mapping=collections.defaultdict(dict)
    byid={u['id']:u for u in units}
    published=load_json(OPS/'state/progress.json')
    if not isinstance(published,dict): published={}
    assessed={}
    for row in published.get('units',[]) if published.get('available') else []:
        try:
            current=row.get('assessment_current') is True and bool(row.get('evidence')) and all(progress.fingerprint(progress.safe_artifact(REPO,e['path']))==e['fingerprint'] for e in row['evidence'])
            if current: assessed[row['id']]=row.get('classification')
        except (OSError,ValueError,KeyError,TypeError):
            continue
    def route_status(hits):
        if not hits: return 'unmapped'
        classes=[assessed.get(uid) for uid in hits]
        if all(c=='verified' for c in classes): return 'verified'
        if all(c in ('implemented','verified') for c in classes): return 'implemented'
        if 'scaffold' in classes: return 'scaffold'
        if any(byid[x].get('status') in ('building','pr_open','queued') for x in hits): return 'in progress'
        return 'not assessed'
    def cite(text,ids,path,line):
        # Require an exact original PHP filename citation, never a title/stem guess.
        for name in re.findall(r"(?<![\w/])([\w./-]+\.php)\b",text):
            name=name.replace('stage3-original-phpretro/','').lstrip('/')
            if name in route_files:
                for uid in ids:
                    if uid in byid: mapping[name][uid]=str(path)+':'+str(line)
    try: route_files={str(p.relative_to(root)) for p in root.rglob('*.php') if not any(x in p.relative_to(root).parts[:-1] for x in ('includes','templates','classes','lib'))}
    except OSError: route_files=set()
    for u in units:
        cite(' '.join(str(u.get(k,'')) for k in ('title','acceptance','fixtures','fidelity_notes'))+' '+(u.get('unit_doc') or ''),[u['id']],'units.yaml / docs/units/'+u['id']+'.md',1)
    for directory in ('docs/roadmap','docs/evidence'):
        for p in sorted((REPO/directory).glob('*.md'))[:200]:
            text=read(p,131072)
            file_ids=re.findall(r'\bF\d+[a-z]*\b',p.stem)
            for n,line in enumerate(text.splitlines(),1):
                ids=re.findall(r'^\|\s*(F\d+[a-z]*)\b',line) or (file_ids if len(file_ids)==1 else [])
                cite(line,ids,p.relative_to(REPO),n)
    # Test evidence citations are attributable only through a unit's named test paths.
    for u in units:
        for rel in u.get('paths',[]) if isinstance(u.get('paths'),list) else []:
            path=REPO/rel
            candidates=[path] if path.is_file() and ('test' in path.name) else list(path.glob('*test*'))[:100] if path.is_dir() else []
            for p in candidates:
                if p.is_file(): cite(read(p,65536),[u['id']],p.relative_to(REPO),1)
    routes=[]
    for name in sorted(route_files):
        hits=mapping[name]; states=[byid[x].get('status') for x in hits]
        status=route_status(hits)
        routes.append({'route':'/'+name,'units':list(hits),'citations':hits,'status':status})
    # Retain literal/rewrite route patterns from the original .htaccess as original evidence.
    for n,line in enumerate(read(root/'.htaccess',65536).replace(chr(92)+'r'+chr(92)+'n',chr(10)).splitlines(),1):
        m=re.match(r'\s*RewriteRule\s+(\S+)\s+(\S+)',line)
        if not m: continue
        target=m[2].split('?')[0].removeprefix('./').lstrip('/'); hits=mapping.get(target,{})
        states=[byid[x].get('status') for x in hits]
        routes.append({'route':'rewrite: '+m[1],'target':target,'units':list(hits),'citations':{**hits,'original':'.htaccess:'+str(n)},'status':route_status(hits)})
    implemented=sum(x['status'] in ('implemented','verified') for x in routes)
    verified=sum(x['status']=='verified' for x in routes)
    return {'routes':routes,'implemented_percent':round(100*implemented/len(routes),1) if routes else None,'verified_percent':round(100*verified/len(routes),1) if routes else None,'note':'Exact PHP citations identify scope only. Implementation requires current reviewed source assessments for every mapped unit; merge records do not prove product behavior. Verification additionally requires recorded acceptance comparison.'}

def number(x):
    try:
        v=float(x); return v if math.isfinite(v) else 0
    except (ValueError,TypeError): return 0

def stamp(s):
    try: return dt.datetime.fromisoformat(str(s).replace('Z','+00:00')).timestamp()
    except (ValueError,TypeError): return None

def day(epoch): return dt.datetime.fromtimestamp(epoch,dt.timezone.utc).date().isoformat()
def source(p):
    try: return str(p.relative_to(HOME))
    except ValueError: return str(p)

def read(p,limit=262144,tail=False):
    k=source(p); now=time.time()
    try:
        stat=p.stat()
        with p.open('rb') as f:
            if tail: f.seek(max(0,stat.st_size-limit))
            elif stat.st_size>limit: raise ValueError('too large')
            value=f.read(limit).decode('utf-8','replace')
        SOURCES[k]={'modified':stat.st_mtime,'sampled':now,'status':'ok'}; return value
    except (OSError,ValueError): SOURCES[k]={'sampled':now,'status':'n/a'}; return ''

def load_json(p):
    text=read(p)
    if not text: return {}
    try: return json.loads(text)
    except (ValueError,TypeError): SOURCES[source(p)]['status']='malformed'; return {}

def jsonl(p,limit=2097152):
    try:
        size=p.stat().st_size
        with p.open('rb') as f: f.seek(max(0,size-limit)); raw=f.read(limit)
        lines=raw.decode('utf-8','replace').splitlines()
        if size>limit and lines: lines=lines[1:]
        rows=[]
        for line in lines:
            try:
                value=json.loads(line)
                if isinstance(value,dict): rows.append(value)
            except (ValueError,TypeError): continue
        SOURCES[source(p)]={'modified':p.stat().st_mtime,'sampled':time.time(),'status':'ok' if rows else 'n/a'}
        return rows
    except OSError:
        SOURCES[source(p)]={'sampled':time.time(),'status':'n/a'}; return []

def price_table(text):
    result={}; model=None
    for line in text.splitlines():
        m=re.match(r'^  ([^:#]+):\s*$',line)
        if m: model=m[1].strip(); result[model]={}; continue
        m=re.match(r'^    (input|output|cache):\s*(null|[0-9.eE+-]+)\s*$',line)
        if model and m: result[model][m[1]]=None if m[2]=='null' else float(m[2])
    return result

def run_cost(run,prices):
    return dashboard_state.run_cost(run,prices)

def recover_usage(run_rows, units, prices, directory):
    """Recover only attributable files not already represented in structured telemetry."""
    known_sessions={str(x.get('usage',{}).get('session_id')) for x in run_rows if isinstance(x.get('usage'),dict) and x['usage'].get('session_id')}
    known_attempts={(str(x.get('unit')),str(x.get('role')),int(number(x.get('attempt')))) for x in run_rows}
    ids=sorted((u['id'] for u in units),key=len,reverse=True); recovered=[]
    for p in sorted(directory.glob('*.usage.json')):
        uid=next((uid for uid in ids if p.name.startswith(uid+'-')),None)
        if not uid: continue
        suffix=p.name[len(uid)+1:]; match=re.fullmatch(r'attempt(\d+)\.usage\.json',suffix)
        role='builder' if match else 'reviewer' if re.fullmatch(r'review\d*\.usage\.json',suffix) else 'planner' if suffix=='planner.usage.json' else None
        if role is None: continue
        attempt=int(match[1]) if match else None
        x=load_json(p)
        if not isinstance(x,dict) or not x: continue
        session=str(x.get('session_id') or '')
        if session and session in known_sessions: continue
        if match and (uid,role,attempt) in known_attempts: continue
        if not session and any(str(r.get('unit'))==uid and r.get('role')==role for r in run_rows): continue
        tokens=number(x.get('total_tokens'))
        if not tokens: tokens=sum(number(x.get(k)) for k in ('input_tokens','output_tokens','cache_read_tokens','cache_write_tokens'))
        if not tokens: continue
        epoch=p.stat().st_mtime
        run={**x,'cached_tokens':x.get('cache_read_tokens')}
        recovered.append({'day':day(epoch),'role':role,'model':str(x.get('model') or 'unknown'),'tokens':tokens,'cost':run_cost(run,prices),'file':p.name,'unit':uid,'completed_at':epoch,'started_at':None,'attempt':attempt,'failed':x.get('failed'),'interrupted':x.get('interrupted'),'outcome':None,'time_source':'usage file modification time'})
        if session: known_sessions.add(session)
        if match: known_attempts.add((uid,role,attempt))
    return recovered

def exact_pr_unit(pr, units):
    match=re.match(r'^unit\(([^)]+)\):',pr.get('title','')) or re.match(r'^([A-Za-z]+\d+[a-z]*):',pr.get('title',''))
    return match[1] if match and match[1] in {u['id'] for u in units} else None

def coverage_records(quality):
    return {uid:[float(v) for v in row.get('coverages',[]) if isinstance(v,(int,float)) and not isinstance(v,bool) and 0<=v<=100] for uid,row in quality.items() if isinstance(row,dict)}

def optimizer_metrics(jev, state, tt):
    costs=[j.get('cost_usd',j.get('cost')) for j in jev]
    changes=[j.get('changed_decision',j.get('changed')) for j in jev]
    enabled=state.get('enabled',{})
    parts=', '.join(str(k)+(': enabled' if v else ': disabled') for k,v in enabled.items() if isinstance(v,bool)) if isinstance(enabled,dict) else ''
    observed=tt.get('units') or []
    active=sum(x.get('marker_active') is True for x in observed if isinstance(x,dict))
    return {'jev_count':len(jev) if jev else state.get('calls'),
            'jev_spend':sum(costs) if costs and all(isinstance(v,(int,float)) and not isinstance(v,bool) for v in costs) else state.get('spend'),
            'jev_changed':sum(v is True for v in changes) if changes and all(isinstance(v,bool) for v in changes) else state.get('changed'),
            'jev_parts':parts or None,
            'token_terminator':('recorded '+str(tt.get('status','unknown'))+'; marker active on '+str(active)+'/'+str(len(observed))+' sampled units') if tt else None,
            'savings_guard':('recorded '+str(tt.get('status','unknown'))+'; '+('savings '+str(tt['saving_pct'])+'%' if tt.get('saving_pct') is not None else 'no measured savings yet')+'; revert '+str(bool(tt.get('revert'))).lower()) if tt else None}

def command(args,ttl=60):
    k=tuple(args); now=time.time()
    if k in MEM and now-MEM[k][0]<ttl: return MEM[k][1]
    try:
        p=subprocess.run(args,cwd=REPO,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'},capture_output=True,text=True,timeout=4)
        v=p.stdout.strip() if p.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired): v=None
    MEM[k]=(now,v); SOURCES['command:'+args[0]+':'+ ' '.join(args[1:3])]={'sampled':now,'status':'ok' if v is not None else 'n/a'}; return v

def scalar(s):
    s=s.strip()
    if s.startswith('[') and s.endswith(']'):
        try: return ast.literal_eval(s)
        except (ValueError,SyntaxError):
            parts=[]; buf=''; quote=None; escaped=False
            for ch in s[1:-1]:
                if escaped: buf+=ch; escaped=False; continue
                if ch=='\\' and quote: buf+=ch; escaped=True; continue
                if quote:
                    buf+=ch
                    if ch==quote: quote=None
                elif ch in ('"',"'"): quote=ch; buf+=ch
                elif ch==',': parts.append(scalar(buf)); buf=''
                else: buf+=ch
            if buf.strip(): parts.append(scalar(buf))
            return parts
    if s.startswith(('"',"'")):
        try: return ast.literal_eval(s)
        except (ValueError,SyntaxError): return s.strip('"\'')
    if s in ('true','false'): return s=='true'
    if re.fullmatch(r'-?\d+',s): return int(s)
    return s

def units_yaml(text):
    out=[]; unit=None
    for line in text.splitlines():
        match=re.match(r'^\s+- id:\s*(.+)$',line)
        if match:
            uid=str(scalar(match[1]))
            unit={'id':uid} if re.fullmatch(r'[A-Za-z0-9_-]+',uid) else None
            if unit is not None: out.append(unit)
            continue
        match=re.match(r'^\s+([\w-]+):\s*(.*)$',line)
        if match and unit is not None: unit[match[1]]=scalar(match[2])
    return out

def files(pattern,limit):
    values=[]
    try:
        for p in (OPS/'logs').glob(pattern):
            if not p.is_file(): continue
            try: values.append((p.stat().st_mtime,p))
            except OSError: pass
    except OSError: pass
    return [p for _,p in sorted(values,reverse=True)[:limit]]

def db_sessions(path):
    con=None; key='sqlite:'+source(path); now=time.time()
    if key in MEM and now-MEM[key][0]<15: return MEM[key][1]
    rows=[]
    try:
        con=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=.15); con.row_factory=sqlite3.Row
        deadline=time.monotonic()+.3
        con.set_progress_handler(lambda: int(time.monotonic()>deadline),1000); con.execute('PRAGMA query_only=ON')
        rows=[dict(r) for r in con.execute('SELECT model,started_at,ended_at,input_tokens,output_tokens,cache_read_tokens,cache_write_tokens,reasoning_tokens,cwd,last_activity_at FROM sessions ORDER BY started_at DESC LIMIT 150')]
        SOURCES[key]={'sampled':now,'status':'ok'}
    except sqlite3.Error: SOURCES[key]={'sampled':now,'status':'n/a'}
    finally:
        if con is not None: con.close()
    MEM[key]=(now,rows); return rows

def builder_process(argv, uid, cwd):
    """Identify the headless builder role, including Hermes' Python launcher."""
    if not argv: return None
    exe=Path(argv[0]).name
    python=bool(re.fullmatch(r'python(?:\d+(?:\.\d+)*)?',exe))
    launcher=exe=='hermes'; cli_start=1
    if python:
        if len(argv)>1 and Path(argv[1]).name=='hermes': launcher=True; cli_start=2
        elif '-c' in argv[:4]:
            i=argv.index('-c')
            launcher=i+1<len(argv) and 'from hermes_cli.main import main' in argv[i+1]; cli_start=i+2
        elif '-m' in argv[:4]:
            i=argv.index('-m'); launcher=i+1<len(argv) and argv[i+1]=='hermes_cli.main'; cli_start=i+2
    if not launcher: return None
    cli=argv[cli_start:]
    def option(flag):
        try:
            i=cli.index(flag); return cli[i+1] if i+1<len(cli) else None
        except ValueError: return None
    usage=option('--usage-file'); skill=option('-s')
    if skill!='unit-builder' or not usage: return None
    match=re.fullmatch(re.escape(uid)+r'-attempt(\d+)\.usage\.json',Path(usage).name)
    if not match or option('--in')!=str(cwd): return None
    return {'model':option('-m'),'attempt':int(match[1])}

def published_parity_sources():
    """Display published artifacts as evidence; do not invent their schema or counts."""
    result=[]
    for label,paths in (
        ('Route map',(REPO/'docs/route-map.md',OPS/'state/route-map.json')),
        ('Parity status',(REPO/'docs/parity-status.md',OPS/'state/parity-status.json')),
    ):
        available=[]
        for path in paths:
            if path.is_file() and not path.is_symlink():
                raw=read(path,65536)
                text=redact(raw)
                text=re.sub(r'(?i)\b(?:bearer\s+|sk-)[A-Za-z0-9._-]+','[redacted]',text)
                available.append({'file':source(path),'text':text or 'Artifact exists but could not be read within the dashboard limit.'})
        result.append({'label':label,'available':bool(available),'documents':available,'message':'' if available else 'Not published yet.'})
    return result

def builders(units,sessions,proc_root=Path('/proc')):
    result=[]; now=time.time()
    try:
        boot=now-number((proc_root/'uptime').read_text().split()[0]); hz=os.sysconf('SC_CLK_TCK')
        for path in proc_root.iterdir():
            if not path.name.isdigit(): continue
            try:
                cwd=Path(os.readlink(path/'cwd'))
                if cwd.parent!=HOME/'work' or cwd.name not in units: continue
                with (path/'cmdline').open('rb') as f: argv=f.read(2097152).decode('utf-8','replace').rstrip('\0').split('\0')
                observed=builder_process(argv,cwd.name,cwd)
                if observed is None: continue
                stat=(path/'stat').read_text().rsplit(')',1)[1].split(); start=boot+number(stat[19])/hz
                matches=[s for s in sessions if s.get('cwd')==str(cwd) and abs(number(s.get('started_at'))-start)<120]
                session=max(matches,key=lambda s:number(s.get('started_at')),default={}); unit=units[cwd.name]
                tokens=sum(number(session.get(k)) for k in ('input_tokens','output_tokens','cache_read_tokens','cache_write_tokens')) if session else None
                result.append({'id':cwd.name,'title':unit.get('title'),'model':session.get('model') or observed['model'] or unit.get('model'),'age':max(0,now-start),'attempts':observed['attempt'],'tokens':tokens,'pid':int(path.name),'hint':'Hermes builder process active; last session activity '+(dt.datetime.fromtimestamp(number(session['last_activity_at']),dt.timezone.utc).isoformat() if session.get('last_activity_at') else 'n/a')})
            except (OSError,ValueError,IndexError): continue
        SOURCES['processes']={'sampled':now,'status':'ok'}
    except OSError: SOURCES['processes']={'sampled':now,'status':'n/a'}
    return result

def properties(unit):
    value=command(['systemctl','show',unit,'-p','ActiveState','-p','SubState','-p','LastTriggerUSec','-p','NextElapseUSecRealtime','-p','ExecMainExitTimestamp','-p','Result','-p','Restart'],15)
    return dict(s.split('=',1) for s in (value or '').splitlines() if '=' in s)

def unit_board(units, live, prs, *, processes_available=True, units_available=True):
    """Project observed work for display without changing authoritative unit state."""
    statuses=('design','todo','building','pr_open','merged','parked')
    columns={status:{'items':[], 'count':0, 'available':units_available, 'message':''} for status in statuses}
    by_id={u['id']:u for u in units}
    live_ids={u['id'] for u in live}
    open_unit_ids=set()
    if prs is not None:
        for pr in prs:
            matches=[u for u in units if u.get('pr') is not None and str(u['pr'])==str(pr['number'])]
            match=re.match(r'^unit\(([^)]+)\):',str(pr.get('title') or ''))
            unit=matches[0] if len(matches)==1 else by_id.get(match[1]) if not matches and match else None
            if unit: open_unit_ids.add(unit['id'])
            columns['pr_open']['items'].append({
                'key':'pr:'+str(pr['number']), 'kind':'pr', 'number':pr['number'],
                'unit_id':unit['id'] if unit else None, 'title':pr.get('title'),
                'pr_url':pr.get('url'), 'status':'pr_open',
                'recorded_status':unit.get('status') if unit else None,
                'board_source':'GitHub open PR' if unit else 'GitHub open PR · not linked to a unit',
            })
    for unit in units:
        uid=unit['id']; recorded=str(unit.get('status') or '')
        lane='building' if uid in live_ids else 'parked' if recorded.startswith('parked') else 'pr_open' if recorded=='queued' else recorded
        # A matched active PR supersedes design/todo for display only.
        if uid in open_unit_ids and lane in ('design','todo','pr_open'):
            continue
        if lane=='pr_open' and prs is not None:
            continue  # GitHub is authoritative when its read succeeded.
        if lane not in columns: continue
        source='Live OpenHands worker receipt' if uid in live_ids else 'Recorded unit status'
        if lane=='building' and uid not in live_ids:
            source='Recorded as building; '+('no live builder observed' if processes_available else 'process detection unavailable')
        if lane=='pr_open': source='Recorded PR state; GitHub data unavailable'
        columns[lane]['items'].append({**unit,'key':'unit:'+uid,'kind':'unit','status':lane,'recorded_status':recorded,'board_source':source})
    for observed in live:
        if observed['id'] not in by_id:
            columns['building']['items'].append({**observed,'key':'unit:'+observed['id'],'kind':'unit','status':'building','board_source':'Live OpenHands worker receipt'})
    columns['building']['available']=processes_available
    columns['pr_open']['available']=prs is not None
    empty={'design':'No units in design.','todo':'No units waiting to build.','building':'No active builds.','pr_open':'No open pull requests.','merged':'No merged units.','parked':'No parked units.'}
    for status,column in columns.items():
        column['count']=len(column['items']) if column['available'] else None
        column['message']=empty[status] if column['available'] and not column['items'] else ''
        if not column['available']:
            column['message']='GitHub PR data unavailable; showing any recorded PR state.' if status=='pr_open' else 'Builder process detection unavailable; showing any recorded build state.' if status=='building' else 'Unit records unavailable.'
    return {'columns':columns}

def snapshot():
    now=time.time(); today=day(now); state=load_json(OPS/'state/units.state.json')
    if not isinstance(state,dict): state={}
    defs={u['id']:u for u in units_yaml(read(REPO/'units.yaml'))}
    for u in units_yaml(read(OPS/'state/units.live.yaml')): defs.setdefault(u['id'],{}).update(u)
    units=list(defs.values()); state_events=state.get('events',[]); state_events=state_events if isinstance(state_events,list) else []
    events=[{'ts':str(e.get('ts','')),'msg':str(e.get('msg',''))} for e in state_events if isinstance(e,dict)]
    log=read(OPS/'logs/orchestrator.log',1048576,True)
    journal=command(['journalctl','-u','phpretro-orchestrator.service','-n','100','--no-pager','-o','short-iso'],30)
    for line in log.splitlines():
        m=re.match(r'\[([^]]+)\]\s*(.*)',line)
        if m: events.append({'ts':m[1],'msg':m[2]})
    events=sorted({(e['ts'],e['msg']):e for e in events}.values(),key=lambda e:stamp(e['ts']) or 0)
    # Structured append-only telemetry is authoritative; STATE/log text remains fallback only.
    run_rows=list(telemetry.read_runs(OPS/'state/runs.jsonl'))
    event_rows=jsonl(OPS/'state/events.jsonl')
    if run_rows:
        usage=[]
    structured_events=[]
    for e in event_rows:
        kind=str(e.get('kind') or 'event'); unit=str(e.get('unit') or '')
        reason=str(e.get('reason') or kind)
        structured_events.append({'ts':str(e.get('ts') or ''),'msg':(unit+': '+kind+' '+reason).strip(),**e})
    if structured_events: events=sorted(structured_events,key=lambda e:stamp(e.get('ts')) or 0)
    merges={}; pr_to_unit={str(int(number(u.get('pr')))):u['id'] for u in units if u.get('status')=='merged' and number(u.get('pr'))}
    gitlog=command(['git','log','origin/main','--first-parent','-n','2000','--format=%cI|%s'],60) or ''
    baseline=None
    for line in gitlog.splitlines():
        when,_,subject=line.partition('|'); m=re.search(r'Merge pull request #(\d+)',subject)
        uid=pr_to_unit.get(m[1]) if m else None
        if uid and stamp(when): merges[uid]={'id':uid,'ts':when,'pr':int(m[1])}
        if m and m[1]=='58' and 'ops/autonomy' in subject: baseline={'ts':when,'label':'Pipeline introduced (PR #58)'}
    for e in events:
        m=re.search(r'\b([A-Za-z]+\d+[a-z]*): MERGED PR #(\d+)',e['msg'])
        if m and m[1] not in merges: merges[m[1]]={'id':m[1],'ts':e['ts'],'pr':int(m[2])}
        if e.get('kind')=='merged' and e.get('unit') and stamp(e.get('ts')):
            merges[str(e['unit'])]={'id':str(e['unit']),'ts':e['ts'],'pr':int(number(e.get('pr'))) or None,'tokens':number(e.get('tokens')) or None}
    usage=[]; per_unit=collections.Counter()
    prices_text=read(OPS/'state/prices.yaml',65536)
    prices=price_table(prices_text)
    if run_rows:
        for x in run_rows:
            try:
                started=stamp(x.get('ts_start')); ended=stamp(x.get('ts_end')) or started or now
                tokens=telemetry.run_total(x)
                uid=str(x.get('unit') or '')
                per_unit[uid]+=tokens
                usage.append({'day':day(ended or now),'role':str(x.get('role') or 'builder'),'model':str(x.get('model') or 'n/a'),'tokens':tokens,'cost':run_cost(x,prices),'file':'runs.jsonl','unit':uid,'completed_at':ended,'started_at':started,'attempt':int(number(x.get('attempt'))) if x.get('attempt') is not None else None,'failed':str(x.get('outcome') or '') in ('failed','gate_failed','timeout','timed_out','no_change','no-change'),'interrupted':str(x.get('outcome') or '') in ('timeout','timed_out','interrupted'),'outcome':x.get('outcome')})
            except (ValueError,TypeError): continue
    recovered=[] # Historical sidecars are incomplete; controller ledger is authoritative.
    usage.extend(recovered)
    for x in recovered: per_unit[x['unit']]+=x['tokens']
    quality_doc=load_json(OPS/'state/quality.json'); quality_doc=quality_doc if isinstance(quality_doc,dict) else {}
    coverages=coverage_records(quality_doc)
    merged_pr_raw=command(['gh','pr','list','--repo','PapaBill1234/phpretro-preservation','--state','merged','--limit','200','--json','number,title,url,mergedAt'],300)
    try: merged_prs=json.loads(merged_pr_raw) if merged_pr_raw else []
    except ValueError: merged_prs=[]
    if not isinstance(merged_prs,list): merged_prs=[]
    pr_matches=collections.defaultdict(list)
    for pr in merged_prs:
        uid=exact_pr_unit(pr,units)
        if uid:
            pr_matches[uid].append(pr)
            if defs[uid].get('status')=='merged' and uid not in merges and stamp(pr.get('mergedAt')): merges[uid]={'id':uid,'ts':pr['mergedAt'],'pr':pr['number']}
    for u in units:
        uid=u['id']; u['accounted_tokens']=per_unit.get(uid) or number(u.get('tokens')) or None
        u['pr_url']=f'https://github.com/PapaBill1234/phpretro-preservation/pull/{int(number(u.get("pr")))}' if number(u.get('pr')) else None
        u['pr_links']=[{'number':p['number'],'url':p['url']} for p in pr_matches.get(uid,[])]
        if not u['pr_url'] and len(u['pr_links'])==1: u['pr_url']=u['pr_links'][0]['url']
        # Unit docs are only expected after the builder unit-doc rule was introduced.
        u['unit_doc_expected']=any(x.get('unit')==uid and (stamp(x.get('ts_start')) or 0)>= (stamp('2026-10-05T17:31:09Z') or 0) for x in run_rows)
        u['unit_doc']=read(REPO/'docs/units'/f'{uid}.md',32768) or None
        u['unit_doc_status']='available' if u['unit_doc'] else 'missing' if u['unit_doc_expected'] else 'not created yet' if u.get('status') in ('design','todo') else 'no historical document recorded'
        u['coverage']=coverages.get(uid,[])
        u['coverage_updated']=quality_doc.get(uid,{}).get('updated')
    for uid,m in merges.items(): m['tokens']=defs.get(uid,{}).get('accounted_tokens')
    merge_list=sorted(merges.values(),key=lambda m:stamp(m['ts']) or 0); daily=collections.Counter(day(stamp(m['ts'])) for m in merge_list if stamp(m['ts']))
    merged=[u for u in units if u.get('status')=='merged']; remaining=sum(u.get('status') not in ('merged','promoted','parked-final') for u in units)
    seven=sum((stamp(m['ts']) or 0)>=now-7*86400 for m in merge_list)
    tokens_merged=[u['accounted_tokens'] for u in merged if u.get('accounted_tokens')]
    live=dashboard_state.live_workers(OPS,defs,now)
    planning_queue=dashboard_state.planning_queue(OPS)
    svc=properties('phpretro-orchestrator.service'); timer=properties('phpretro-orchestrator.timer'); stop=(OPS/'STOP').exists()
    heartbeat=max([stamp(e['ts']) or 0 for e in events]+[0]); state_md=read(OPS/'state/STATE.md')
    caps=re.search(r'merged_today:\s*\d+/(\d+)\s+tokens_today:\s*\d+/(\d+)',state_md)
    merge_cap=int(caps[1]) if caps else None; token_cap=int(caps[2]) if caps else None
    today_runs=[x for x in usage if x['day']==today]
    mt=sum(1 for e in events if e.get('kind')=='merged' and day(stamp(e.get('ts')) or 0)==today) if event_rows else (state.get('merged_today') if state.get('day')==today else 0 if state.get('day') else None)
    tt=state.get('tokens_today') if state.get('day')==today and state.get('accounting_version',0)>=2 else sum(x['tokens'] for x in today_runs) if run_rows else (state.get('tokens_today') if state.get('day')==today else 0 if state.get('day') else None)
    gates=[]; nightly=[]
    for p in files('*.check.log',150):
        text=read(p,16384,True); result='pass' if 'CHECK PASSED' in text or 'scripts/check.sh PASSED' in text else 'fail' if 'CHECK FAILED' in text else 'n/a'
        match=re.search(r'head:\s*([0-9a-f]{12,40})',text)
        try: modified=p.stat().st_mtime
        except OSError: modified=None
        g={'file':p.name,'result':result,'modified':modified,'head':match[1] if match else None}; gates.append(g)
    for p in files('*night*',30)+files('*integration*',30):
        text=read(p,8192,True); result='pass' if 'CHECK PASSED' in text else 'fail' if 'CHECK FAILED' in text else 'n/a'
        nightly.append({'file':p.name,'result':result})
    relevant=[e for e in events if re.search(r'\bmerged\b|park|escalat|timeout|timed out|killed|stopped|failover|disabl|fail|guard',e['msg'],re.I)]
    attention=[{'title':u['id'],'detail':str(u.get('reason') or u.get('feedback') or 'Parked; no reason recorded')} for u in units if str(u.get('status')).startswith('parked') or u.get('reason')]
    attention.extend({'title':e['ts'],'detail':e['msg']} for e in relevant[-20:] if re.search(r'fail|disabl|timeout|killed|stopped|guard',e['msg'],re.I))
    prs_raw=command(['gh','pr','list','--repo','PapaBill1234/phpretro-preservation','--state','open','--limit','100','--json','number,title,url,updatedAt,statusCheckRollup,headRefOid'],90)
    try: prs=json.loads(prs_raw) if prs_raw else None
    except ValueError: prs=None
    if not isinstance(prs,list): prs=None
    for pr in prs or []:
        unit=next((u for u in units if number(u.get('pr'))==pr.get('number')),None) or defs.get(exact_pr_unit(pr,units))
        gate=next((g for g in gates if unit and g['file']==unit['id']+'-merge.check.log' and g['head']==pr.get('headRefOid')),None)
        pr['local_gate']=gate['result'] if gate else 'n/a: no exact-head gate record'
        pr['attempt_gate']=next((g['result'] for g in gates if unit and g['file'].startswith(unit['id']+'-attempt')),'n/a')
        if (stamp(pr.get('updatedAt')) or now)<now-86400: attention.append({'title':'Stuck PR #'+str(pr['number']),'detail':'No update in 24 hours'})
    actions=read(OPS/'state/ACTIONS_NOTE.md',32768,True); prices=read(OPS/'state/PRICES.md',32768)
    jev_text=read(OPS/'state/jev.jsonl',65536,True); jev=[]
    for line in jev_text.splitlines():
        try:
            j=json.loads(line)
            if isinstance(j,dict): jev.append(j)
        except ValueError: pass
    jev_state=load_json(OPS/'state/jev.json'); tt_state=load_json(OPS/'state/tt.json')
    optimizer=optimizer_metrics(jev,jev_state if isinstance(jev_state,dict) else {},tt_state if isinstance(tt_state,dict) else {})
    after=load_json(OPS/'state/protection-after.json'); after=after if isinstance(after,dict) else {}
    guards={'Actions required (recorded snapshot)':bool((after.get('required_status_checks') or {}).get('contexts')) if after else None,'force pushes blocked (recorded)':not (after.get('allow_force_pushes') or {}).get('enabled') if after else None,'deletions blocked (recorded)':not (after.get('allow_deletions') or {}).get('enabled') if after else None}
    if after and guards['Actions required (recorded snapshot)'] is False: attention.append({'title':'Actions requirement removed','detail':'Recorded branch-protection snapshot has no required Actions contexts. Local scripts/check.sh remains authoritative.'})
    merge_lock=None
    try:
        st=(OPS/'locks/merge.lock').stat(); needle=f'{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}'
        with Path('/proc/locks').open() as f: merge_lock=any(needle in line for line in f)
        SOURCES['merge lock']={'sampled':now,'status':'ok'}
    except OSError: SOURCES['merge lock']={'sampled':now,'status':'n/a'}
    nightly_doc=load_json(OPS/'state/nightly.json')
    nightly_history=jsonl(OPS/'state/nightly-history.jsonl')
    nightly_runs=[]
    for row in nightly_history:
        nightly_runs.append({'name':row.get('name'),'started':row.get('started'),'finished':row.get('finished'),'pass':row.get('ok'),'age':max(0,now-(stamp(row.get('finished')) or now)),'detail':row.get('detail'),'conditions':row.get('conditions') or []})
    for name,row in (nightly_doc.items() if isinstance(nightly_doc,dict) else []):
        if not isinstance(row,dict): continue
        detail=row.get('details') if isinstance(row.get('details'),dict) else {}
        nightly.append({'file':name,'result':'pass' if row.get('pass') is True else 'fail' if row.get('pass') is False else 'n/a','ts':row.get('ts'),'age':max(0,now-(stamp(row.get('ts')) or now))})
    nightly_runs=sorted(nightly_runs,key=lambda x:stamp(x.get('finished')) or 0,reverse=True)[:14]
    disk=shutil.disk_usage(HOME); reasons=[]; color='green'; last_merge=max([stamp(m['ts']) or 0 for m in merge_list]+[0])
    if stop: reasons.append('Coding intentionally paused'); color='amber'
    if not stop and heartbeat and now-heartbeat>600: reasons.append('Orchestrator heartbeat older than 10 minutes'); color='red'
    if not stop and svc.get('ActiveState') in ('failed','inactive') and timer.get('ActiveState')!='active': reasons.append('Orchestrator down'); color='red'
    if not stop and last_merge and now-last_merge>86400: reasons.append('No observed merge in 24 hours'); color='red'
    current_nightly={name:row.get('pass') for name,row in nightly_doc.items() if isinstance(row,dict)} if isinstance(nightly_doc,dict) else {}
    if current_nightly.get('integration') is False or current_nightly.get('selfcheck') is False: reasons.append('Nightly check failing'); color='red'
    if not reasons:
        if (merge_cap and number(mt)/merge_cap>=.8) or (token_cap and number(tt)/token_cap>=.8): reasons.append('Daily cap above 80%'); color='amber'
        elif not live: reasons.append('Idle: no active builder process'); color='amber'
        elif sum(str(u.get('status')).startswith('parked') for u in units)>max(3,len(units)*.15): reasons.append('Many units parked'); color='amber'
        else: reasons.append('Merging normally' if last_merge else 'Merge history n/a'); color='green' if last_merge else 'amber'
    today_usage=[u for u in usage if u['day']==today]
    priced_today=[u for u in today_usage if u['cost'] is not None]
    priced_all=[u for u in usage if u['cost'] is not None]
    cost_today=sum(u['cost'] for u in priced_today) if priced_today else None
    cost_total=sum(u['cost'] for u in priced_all) if priced_all else None
    cost_coverage={'priced_runs':len(priced_all),'total_runs':len(usage),'complete':bool(usage) and len(priced_all)==len(usage),'unknown_models':sorted({u['model'] for u in usage if u['cost'] is None})}
    audit_match=re.search(r'audit findings open:\s*(\d+)',state_md,re.I)
    audit=int(audit_match[1]) if audit_match else None
    guessed_match=re.search(r'guessed fidelity:\s*(\d+)',state_md,re.I)
    guessed_count=int(guessed_match[1]) if guessed_match else sum(bool(re.search(r'fidelity:\s*guessed',u.get('unit_doc') or '',re.I)) for u in units)
    parity_data=parity(units)
    parity_data['published_sources']=published_parity_sources()
    model_rows={}; attempt_usage=[x for x in usage if x.get('attempt') is not None and x.get('role')=='builder']
    for model in ['luna','deepseek','sol']:
        model_rows[model]={'model':model,'attempts':0,'units':set(),'first':0,'first_success':0,'tokens':0,'times':[],'escalations_in':0,'escalations_out':0}
    for x in attempt_usage:
        model=x['model']; label='luna' if 'luna' in model.lower() else 'deepseek' if 'deepseek' in model.lower() else 'sol' if 'sol' in model.lower() else model
        z=model_rows.setdefault(label,{'model':label,'attempts':0,'units':set(),'first':0,'first_success':0,'tokens':0,'times':[],'escalations_in':0,'escalations_out':0}); z['attempts']+=1; z['tokens']+=x['tokens']
        if defs.get(x['unit'],{}).get('status')=='merged': z['units'].add(x['unit'])
        if x['attempt']==1:
            z['first']+=1
            if defs.get(x['unit'],{}).get('status')=='merged' and number(defs.get(x['unit'],{}).get('attempts'))==1: z['first_success']+=1
    dispatches={}; durations={}; transitions=collections.Counter(); previous={}
    def family(model): return 'luna' if 'luna' in model.lower() else 'deepseek' if 'deepseek' in model.lower() else 'sol' if 'sol' in model.lower() else model
    for e in events:
        m=re.search(r'(\w+): dispatch attempt (\d+) on (\S+)',e['msg'])
        if m:
            uid,attempt,model=m[1],int(m[2]),family(m[3]); dispatches[(uid,attempt)]=model
            if uid in previous and previous[uid]!=model: transitions[(previous[uid],model)]+=1
            previous[uid]=model
        m=re.search(r'(\w+): builder finished rc=(-?\d+) in (\d+)s',e['msg'])
        if m:
            candidates=[a for uid,a in dispatches if uid==m[1]]
            if candidates: durations[(m[1],max(candidates))]=int(m[3])
    if event_rows:
        by_unit=collections.defaultdict(list)
        for e in event_rows:
            if e.get('kind')=='dispatched' and e.get('unit') and e.get('model'):
                by_unit[str(e['unit'])].append((stamp(e.get('ts')) or 0,family(str(e['model'])),int(number(e.get('attempt')))))
        transitions=collections.Counter()
        for seq in by_unit.values():
            seq.sort()
            for before,after in zip(seq,seq[1:]):
                if before[1]!=after[1]: transitions[(before[1],after[1])]+=1
    for x in attempt_usage:
        label=family(x['model']); seconds=max(0,x['completed_at']-x['started_at']) if x.get('started_at') and x.get('completed_at') else durations.get((x['unit'],x['attempt']))
        if seconds is not None: model_rows[label]['times'].append(seconds)
    for z in model_rows.values():
        z['merged_units']=len(z.pop('units')); z['average_tokens']=z['tokens']/z['attempts'] if z['attempts'] else None; z['first_attempt_success_rate']=100*z['first_success']/z['first'] if z['first'] else None; z['average_time']=statistics.mean(z['times']) if z['times'] else None; z['escalations_in']=sum(v for (src,dst),v in transitions.items() if dst==z['model']); z['escalations_out']=sum(v for (src,dst),v in transitions.items() if src==z['model']); z.pop('times'); z['note']='Observed builder usage only; first-attempt success requires merged state and attempts=1. Escalations are observed model transitions; absent historical telemetry is excluded.'
    for b in live: b['tail']=None; b['tail_reason']='Withheld: arbitrary environment secret values cannot be guaranteed redacted without reading the forbidden .env file.'
    measured=[x for x in usage if x['cost'] is not None]; complete_cost=bool(usage) and len(measured)==len(usage)
    spend24=sum(x['cost'] for x in measured if x['completed_at']>=now-86400) if any(x['completed_at']>=now-86400 for x in measured) else None
    spend7=sum(x['cost'] for x in measured if x['completed_at']>=now-7*86400)/7 if any(x['completed_at']>=now-7*86400 for x in measured) else None
    attempt_history=load_json(OPS/'state/history.json'); attempt_history=attempt_history if isinstance(attempt_history,dict) else {}
    for x in attempt_usage:
        h=attempt_history.get(x['unit'],{}); h=h if isinstance(h,dict) else {}
        if number(h.get('attempt'))==x['attempt'] and h.get('outcome') in ('no-change','timeout','check-fail','recovered-fail'): x['failed']=True
    gate_outcomes={}
    per_unit_events=collections.defaultdict(list)
    for e in event_rows:
        if e.get('unit'): per_unit_events[str(e['unit'])].append(e)
    for x in attempt_usage:
        seq=sorted(per_unit_events.get(x['unit'],[]),key=lambda e:stamp(e.get('ts')) or 0)
        dispatch=next((i for i,e in enumerate(seq) if e.get('kind')=='dispatched' and int(number(e.get('attempt')))==x['attempt']),None)
        outcome=None
        if dispatch is not None:
            start=stamp(seq[dispatch].get('ts')) or 0
            end=next((stamp(e.get('ts')) for e in seq[dispatch+1:] if e.get('kind')=='dispatched' and (stamp(e.get('ts')) or 0)>start),float('inf'))
            attempt_gates=[e for e in seq[dispatch+1:] if e.get('kind') in ('gate_pass','gate_fail') and start <= (stamp(e.get('ts')) or 0) < end]
            if attempt_gates: outcome=attempt_gates[-1].get('kind')
        gate_outcomes[(x['unit'],x['attempt'])]=outcome
        x['gate_outcome']=outcome
    merged_tokens=sum(x['tokens'] for x in attempt_usage if x.get('gate_outcome')=='gate_pass' and defs.get(x['unit'],{}).get('status')=='merged')
    failed_tokens=sum(x['tokens'] for x in attempt_usage if x.get('gate_outcome')=='gate_fail' or x.get('failed') or x.get('interrupted'))
    all_attempt_tokens=sum(x['tokens'] for x in attempt_usage)
    waste={'merged_tokens':merged_tokens,'failed_tokens':failed_tokens,'unclassified_tokens':max(0,all_attempt_tokens-merged_tokens-failed_tokens),'merged_share':merged_tokens/all_attempt_tokens*100 if all_attempt_tokens else None,'failed_share':failed_tokens/all_attempt_tokens*100 if all_attempt_tokens else None,'note':'Attempt usage only; merged association does not prove each attempt succeeded. No-change/timeout/gate-fail latest attempt records included; other outcomes remain unclassified.'}
    lead=[]
    for m in merge_list:
        starts=[stamp(e.get('ts')) for e in event_rows if e.get('unit')==m['id'] and e.get('kind')=='dispatched' and stamp(e.get('ts')) and stamp(e.get('ts'))<=stamp(m['ts'])]
        if starts: lead.append(stamp(m['ts'])-min(starts))
    lead.sort(); fix_units=[u for u in units if re.search(r'\bfix\b|rework',str(u.get('title','')),re.I)]
    rework={'rate':len(fix_units)/len(merged) if merged else None,'count':len(fix_units),'note':'Explicit fix/rework titles only; other retries are not new fix units.'}
    history_rows,balance=save_history({'kpi':{'merged':len(merged),'total':len(units),'tokens_today':tt,'cost_today':cost_today,'cost_total':cost_total,'merges_7d':seven},'counts':dict(collections.Counter(u.get('status','n/a') for u in units)),'running':[b['id'] for b in live],'live':live,'health':{'color':color,'reason':'; '.join(reasons)},'waste':waste,'rework':rework})
    runway={'balance':balance,'average_24h':None,'average_7d_daily':None,'days_24h':None,'days_7d':None,'unit':'Gateway price units (uncalibrated)','calibration':None,'assumptions':'Runway awaits provider price-unit and complete-usage calibration.'}
    merged24=sum((stamp(m['ts']) or 0)>=now-86400 for m in merge_list)
    parks24=sum((stamp(e['ts']) or 0)>=now-86400 and bool(re.search(r'park',e['msg'],re.I)) for e in events)
    next_units=[u for u in units if u.get('status')=='todo' and all(defs.get(x,{}).get('status')=='merged' for x in u.get('depends_on',[]))]
    summary='Since yesterday: '+str(merged24)+' merged, '+str(parks24)+' park events, about '+(format(spend24,'.4f')+' uncalibrated gateway units' if spend24 is not None else 'unknown cost')+' estimated; next expected: '+(', '.join(u['id'] for u in next_units[:3]) if next_units else 'n/a (no eligible todo unit observed)')+'.'
    failed_units=sorted({str(e.get('unit')) for e in event_rows if e.get('kind')=='gate_fail' and e.get('unit')}) if event_rows else sorted(set(g['file'].split('-')[0] for g in gates if g['result']=='fail'))
    board=unit_board(units,live,prs,processes_available=SOURCES.get('processes',{}).get('status')=='ok',units_available=any(SOURCES.get(source(path),{}).get('status')=='ok' for path in (REPO/'units.yaml',OPS/'state/units.live.yaml')))
    return {'builder_activity':dashboard_state.builder_activity(OPS,defs,run_rows,event_rows,live,stop,now),'provider_billing':billing.summary(OPS),'portdan_cost_check':'user-disabled','planning_queue':planning_queue,'cost_label':'Gateway estimate (price units uncalibrated)','unit_board':board,'updated':now,'stop':stop,'health':{'color':color,'reason':'; '.join(reasons)},'kpi':{'merged':len(merged),'total':len(units),'merged_today':mt,'merge_cap':merge_cap,'tokens_today':tt,'token_cap':token_cap,'cost_today':cost_today,'cost_total':cost_total,'cost_coverage':cost_coverage,'median_tokens':statistics.median(tokens_merged) if tokens_merged else None,'median_sample':len(tokens_merged),'merges_7d':seven,'completion_estimate':None},'live':live,'units':units,'charts':{'merges':merge_list,'daily':dict(sorted(daily.items())),'usage':usage,'baseline':baseline,'note':'Controller ledger, including rotations and final outcomes; token charges include conservative estimates. Costs use the recorded controller estimate, with cache read/write included. Gateway price units remain uncalibrated.'},'attention':attention,'pipeline':{'service':svc,'timer':timer,'heartbeat':heartbeat or None,'merge_lock':merge_lock,'prs':prs,'disk_used':disk.used,'disk_total':disk.total,'nightly':nightly,'nightly_runs':nightly_runs,'nightly_status':next((x for x in nightly if x.get('file')=='integration'),None),'gates':gates,'guards':guards,'actions_note':None,'journal':None},'quality':{'coverage':{uid:values for uid,values in coverages.items() if values},'coverage_note':'Recorded per-check percentages; not overall project coverage.','guessed_count':guessed_count,'audit_open':audit,'failed_units':failed_units},'optimizers':{**optimizer,'ladder_escalations':sum(e.get('kind')=='escalated' for e in event_rows) if event_rows else sum(bool(re.search(r'escalat',e['msg'],re.I)) for e in relevant),'ladder_attempts':dict(collections.Counter(str(int(number(u.get('attempts')))) for u in units if number(u.get('attempts')))),'timeouts':sum(e.get('kind') in ('timeout','timed_out') for e in event_rows) if event_rows else sum(bool(re.search(r'timeout|timed out|killed|stopped at',e['msg'],re.I)) for e in relevant)},'events':list(reversed(relevant[-50:])),'summary':summary,'waste':waste,'history':history_rows,'parity':parity_data,'models':list(model_rows.values()),'runway':runway,'rework':rework,'lead_time':{'median':statistics.median(lead) if lead else None,'p90':lead[max(0,math.ceil(len(lead)*.9)-1)] if lead else None,'sample':len(lead)},'sources':dict(SOURCES),'limitations':['Estimated costs are not account deductions. Incomplete usage and missing prices remain unknown; reservations and outcome rows are excluded from paid-run counts. Calibration requires complete priced runs in its snapshot window.','Coverage is per recorded check, not global coverage. Optimizer states are recorded snapshots; savings require sufficient measured samples.','Historical merge dates are incomplete for legacy units without recorded PRs.','Live workers require matching PID, process start identity and durable OpenHands receipt; no conversation content is exposed.']}

def get_state():
    with LOCK:
        if time.monotonic()-CACHE.get('at',-10)>4:
            try: CACHE['data']=snapshot()
            except Exception as e: CACHE['data']={'updated':time.time(),'error':'Snapshot unavailable: '+type(e).__name__,'health':{'color':'amber','reason':'Incomplete source; retrying'},'sources':dict(SOURCES)}
            CACHE['at']=time.monotonic()
        return CACHE['data']

class Handler(http.server.BaseHTTPRequestHandler):
    def setup(self):
        super().setup(); self.connection.settimeout(10)
    def log_message(self,*args): pass
    def send(self,status,data,kind='application/json'):
        body=json.dumps(data,allow_nan=False).encode() if kind=='application/json' else data
        self.send_response(status); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','no-referrer'); self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path=='/api/state': self.send(200,get_state())
        elif self.path=='/': self.send(200,(ROOT/'index.html').read_bytes().replace(b'__TOKEN__',TOKEN.encode()),'text/html; charset=utf-8')
        else: self.send(404,{'error':'not found'})
    def do_POST(self):
        host=self.headers.get('Host',''); origin=self.headers.get('Origin','')
        if self.path not in ('/api/stop','/api/balance') or not re.fullmatch(r'(127\.0\.0\.1|localhost):'+str(self.server.server_port),host) or origin!='http://'+host or not secrets.compare_digest(self.headers.get('X-Dashboard-Token',''),TOKEN): self.send(403,{'error':'forbidden'}); return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size<1 or size>256: raise ValueError()
            data=json.loads(self.rfile.read(size))
            if self.path=='/api/balance':
                if not isinstance(data,dict) or isinstance(data.get('balance'),bool): raise ValueError()
                value=float(data.get('balance'))
                if not math.isfinite(value) or value<0: raise ValueError()
                with history_db() as con:
                    con.execute("INSERT OR REPLACE INTO settings VALUES('balance',?)",(str(value),))
                    con.execute('INSERT INTO balance_snapshots VALUES(?,?)',(time.time(),value))
                with LOCK: CACHE['at']=-10
                self.send(200,{'balance':value}); return
            if not isinstance(data,dict) or type(data.get('stop')) is not bool: raise ValueError()
            if data['stop']:
                try:
                    fd=os.open(OPS/'STOP',os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600); os.close(fd)
                except FileExistsError: pass
            else: (OPS/'STOP').unlink(missing_ok=True)
            with LOCK: CACHE['at']=-10
            self.send(200,{'stop':(OPS/'STOP').exists()})
        except (ValueError,TypeError): self.send(400,{'error':'invalid body'})
        except (OSError,sqlite3.Error): self.send(503,{'error':'Write operation unavailable'})
    def do_PUT(self): self.send(405,{'error':'method not allowed'})
    do_DELETE=do_PUT

if __name__=='__main__':
    os.umask(0o077); portfile=ROOT/'port'
    if portfile.exists():
        port=int(portfile.read_text().strip())
        if not 20000<=port<=60000: raise ValueError('invalid saved port')
        server=http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler)
    else:
        for _ in range(100):
            port=20000+secrets.randbelow(40001)
            try: server=http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler); break
            except OSError: continue
        else: raise RuntimeError('no free port')
        portfile.write_text(str(port)+'\n')
    server.daemon_threads=True
    def sampler():
        while True:
            get_state()
            try:
                with history_db() as con: last=con.execute('SELECT MAX(ts) FROM history').fetchone()[0]
                delay=max(5,300-(time.time()-(last or time.time())))
            except sqlite3.Error: delay=60
            time.sleep(delay)
    threading.Thread(target=sampler,daemon=True).start()
    print(f'Dashboard http://127.0.0.1:{port}',flush=True); server.serve_forever()

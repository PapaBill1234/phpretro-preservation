#!/usr/bin/env python3
"""Desktop windows follow existing redacted native runs; never start inference."""
import argparse,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import runtime_policy,session_journal,worker

def read(path,limit=3*1024*1024):
    try:
        if path.is_symlink() or path.stat().st_size>limit:return {}
        value=json.loads(path.read_text());return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}

def identity(value):
    return isinstance(value,str) and bool(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',value))

def active_builders(ops):
    paths=sorted((ops/'state/receipts').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:256]
    rows=[]
    for path in paths:
        if not identity(path.stem):continue
        row=read(path,256*1024)
        if (row.get('run_id')==path.stem and row.get('runtime')=='claude-code' and
            row.get('role')=='builder' and row.get('status')=='running' and
            worker.alive(row.get('worker_pid'),row.get('worker_identity'))):rows.append(row)
    return rows[:2]

def environments():
    # XFCE can have several RDP desktops. Read only their DISPLAY/auth-path
    # fields, keep them local, and never expose the process environment.
    result=subprocess.run(['pgrep','-u',str(os.getuid()),'-x','xfce4-session'],capture_output=True,text=True,timeout=5)
    seen=set();rows=[];home=Path.home()
    for pid in result.stdout.split()[:16]:
        if not pid.isdigit():continue
        try:
            content=(Path('/proc')/pid/'environ').read_bytes()[:65536]
            selected={}
            for item in content.split(b'\0'):
                key,separator,value=item.partition(b'=')
                if separator and key in (b'DISPLAY',b'XAUTHORITY'):selected[key.decode()]=value.decode()
            display=selected.get('DISPLAY','')
            if not re.fullmatch(r':[0-9]{1,3}(?:\.[0-9]{1,2})?',display) or display in seen:continue
            auth=Path(selected.get('XAUTHORITY',str(home/'.Xauthority')))
            if not auth.resolve().is_relative_to(home.resolve()) or not auth.is_file():continue
            seen.add(display)
            env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL')}
            env.update(HOME=str(home),DISPLAY=display,XAUTHORITY=str(auth),PHPRETRO_OPS=str(runtime_policy.OPS),
                       XDG_RUNTIME_DIR='/run/user/'+str(os.getuid()),DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/'+str(os.getuid())+'/bus')
            rows.append((pid,env))
        except (OSError,UnicodeError,ValueError):continue
    return rows

def safe_text(value):
    value=session_journal.redact(value)
    return ''.join(c for c in value if c in '\n\t' or ord(c)>=32 and ord(c)!=127)[:4000]

def view(ops,rid,linger=120):
    if not identity(rid):raise ValueError('Invalid native run identity')
    path=ops/'state/receipts'/(rid+'.json');row=read(path,256*1024)
    if row.get('runtime')!='claude-code' or row.get('run_id')!=rid or row.get('role')!='builder':raise ValueError('Claude builder receipt required')
    print('Claude Code | '+safe_text(row.get('unit') or 'Provider acceptance')+' | '+safe_text(row.get('model','')))
    print('Existing native run: '+rid+'\nLive assistant and Docker tool activity.\n',flush=True)
    cursor=0;ended=None
    while True:
        journal=read(path.with_suffix('.session.json'))
        events=journal.get('events',[]) if journal.get('schema')==session_journal.SCHEMA else []
        if not isinstance(events,list):events=[]
        for event in events[cursor:512]:
            if isinstance(event,dict) and event.get('kind') in session_journal.KINDS:
                print('['+event['kind']+'] '+safe_text(event.get('text','')),flush=True)
        cursor=min(len(events),512);current=read(path,256*1024)
        if current.get('status')=='complete':
            if ended is None:
                ended=time.monotonic();print('\nRun ended, exit '+str(current.get('rc'))+'. Saved in Doctor sessions.',flush=True)
            if time.monotonic()-ended>=linger:return
        time.sleep(1)

def watch(ops):
    terminal=shutil.which('xfce4-terminal')
    if not terminal:raise RuntimeError('XFCE terminal is not installed')
    launched=set()
    while True:
        rows=active_builders(ops)
        if rows:
            for pid,env in environments():
                for row in rows:
                    key=(row['run_id'],pid)
                    if key in launched:continue
                    title='Claude Code | '+safe_text(row.get('unit') or 'Acceptance')+' | '+safe_text(row.get('model',''))
                    args=[terminal,'--disable-server','--title',title,'--geometry=112x32','--execute',
                          sys.executable,str(Path(__file__).resolve()),'--view',row['run_id']]
                    subprocess.Popen(args,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
                    launched.add(key)
            if len(launched)>1024:launched={key for key in launched if key[0] in {r['run_id'] for r in rows}}
        time.sleep(2)

if __name__=='__main__':
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--watch',action='store_true');group.add_argument('--view');args=parser.parse_args()
    if args.watch:watch(runtime_policy.OPS)
    else:view(runtime_policy.OPS,args.view)

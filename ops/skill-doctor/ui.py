#!/usr/bin/env python3
"""Run upstream UI on loopback; retain its bootstrap token only in a private file."""
import json,os,re,subprocess
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrity as control
base=Path.home()/'phpretro-skill-doctor'
os.umask(0o077)
session=base/'ui-session'
session.unlink(missing_ok=True)
env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':str(base/'audit-home'),'NO_COLOR':'1'}
repo=Path(__file__).resolve().parents[2]
image=json.loads((repo/'ops/openhands/policy.json').read_text())['image']
command=['docker','run','--rm','--init','--name','phpretro-skill-doctor-ui','--user',f'{os.getuid()}:{os.getgid()}',
         '--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=600m','--pids-limit=64',
         '--publish','127.0.0.1:38123:38124','--tmpfs','/tmp:rw,nosuid,size=128m',
         '--mount',f'type=bind,src={base},dst={base}', '--mount',f'type=bind,src={repo},dst={repo}',
         '--env',f'HOME={base}/audit-home']
for name in ('sessions','archived_sessions'):
    source=Path.home()/'phpretro-codex/private'/name
    if source.is_dir():command+=['--mount',f'type=bind,src={source},dst={base}/audit-home/.codex/{name},readonly']
command += [image,'node',str(repo/'ops/skill-doctor/container.js'),str(repo)]
process=subprocess.Popen(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
try:
    for line in process.stdout:
        found=re.search(r'http://127\.0\.0\.1:38123/session/([A-Za-z0-9_-]{43})',line)
        if found:control.atomic_text(session,found.group(1))
    raise SystemExit(process.wait())
finally:session.unlink(missing_ok=True)

"""Explicit manual Deep Scan acceptance, never invoked by a timer."""
import http.client,json,os,re,time
from pathlib import Path
base=Path('/home/ubuntu/phpretro-skill-doctor')
port=int(os.environ.get('DOCTOR_TEST_PORT','38123'))
token=(base/'ui-session').read_text().strip() if port==38123 else re.findall(r'/session/([A-Za-z0-9_-]{43})',(base/'preview-private.log').read_text())[-1]
headers={'Cookie':'skill_doctor_session='+token,'Content-Type':'application/json','Origin':'http://127.0.0.1:'+str(port)}
def request(method,path,body=None):
    c=http.client.HTTPConnection('127.0.0.1',port,timeout=300)
    c.request(method,path,json.dumps(body) if body else None,headers);r=c.getresponse();return c,r
c,r=request('POST','/api/scans',{'projectDir':str(base/'agents'),'platform':'openhands','scope':'all','tokenizer':'approx',
 'discoverMcpTools':False,'useAiAudit':True,'analyzeConflicts':True,'conflictStrategy':'embedding'})
assert r.status==202; scan=json.loads(r.read())['scanId'];c.close()
c,r=request('GET','/api/scans/'+scan+'/events');data=r.read(4_000_000);c.close()
events=[]
for line in data.decode().splitlines():
    if line.startswith('data: '):
        try:events.append(json.loads(line[6:]))
        except ValueError:pass
complete=b'event: complete\n' in data
errors=b'event: error\n' in data
snapshots=[json.loads(block.split('data: ',1)[1].strip()) for block in data.decode().split('\n\n') if block.startswith('event: complete\n')]
warnings=[w.get('code') for w in snapshots[-1].get('warnings',[])] if snapshots else []
print(json.dumps({'complete':complete,'error':errors,'bytes':len(data),'warning_codes':warnings}))
assert complete and not errors,'Deep Scan did not complete'
assert not any(w in ('ai-audit-failed','embedding-failed','ai-not-configured') for w in warnings),'Deep Scan analysis stage failed'

"""Isolated loopback UI acceptance. Synthetic Claude rows never enter live history."""
import http.client,http.server,importlib.util,json,os,subprocess,sys,tarfile,tempfile,threading,time
from pathlib import Path
os.umask(0o077);os.environ['PHPRETRO_RUNTIME']='claude-code'
root=Path.home()/'phpretro-claude-code/migration';sys.path.insert(0,str(root/'ops'))
import doctor_sessions,doctor_canvas,runtime_optimization,runtime_policy
from claude_code import status,supervisor
spec=importlib.util.spec_from_file_location('candidate_gateway',root/'ops/dashboard/gateway.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
manifest=json.loads((Path.home()/'phpretro-claude-code/doctor-build-home/phpretro-skill-doctor/extension-manifest.json').read_text());source=Path(manifest['package']).parent
original=doctor_sessions.sessions
def report(**kwargs):
    value=original(**kwargs);row=dict(value['sessions'][0]);row.update(id='cccccccc-cccc-4ccc-8ccc-cccccccccccc',runtime='claude-code',unit='Synthetic UI acceptance',role='builder',model='claude-sonnet-5-5',provider='anthropic:claude-code',status='failed',rc=1,started=time.time(),ended=time.time(),tokens=39,input=23,output=4,cached=7,cache_write=5,complete=True,context_complete=False,context={},context_requests=[],unused_tools=[],journal_available=False,resources=[],native_session_id='dddddddd-dddd-4ddd-8ddd-dddddddddddd')
    value['sessions'].insert(0,row);value['issues'].insert(0,{'id':'runtime:synthetic-failure','runtime':'claude-code','session_id':row['id'],'kind':'context','severity':'med','title':'Synthetic native agent failure','summary':'Browser acceptance fixture only','resourceNames':['Claude Code'],'resourceIds':[],'evidence':[{'label':'Session','value':row['id']}],'recommendation':'Review the retained session','detectionMethod':'Synthetic fixture'})
    return value
doctor_sessions.sessions=report
with tempfile.TemporaryDirectory(prefix='claude-ui-',dir=Path.home()/'phpretro-claude-code') as folder:
    private=Path(folder);home=private/'home';project=home/'phpretro-skill-doctor/claude-agents';(project/'.claude/skills/fixture-builder').mkdir(parents=True)
    (project/'.claude/skills/fixture-builder/SKILL.md').write_text('---\nname: fixture-builder\ndescription: Synthetic browser acceptance audit fixture\n---\nRead-only fixture, not agent-injected context.\n')
    ui=private/'ui';ui.mkdir()
    with tarfile.open(manifest['package']) as archive:
        for member in archive.getmembers():
            prefix='package/dist/ui/'
            if not member.name.startswith(prefix) or not member.isfile():continue
            target=ui/member.name[len(prefix):];assert target.resolve().is_relative_to(ui.resolve()) and member.size<32000000
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.extractfile(member).read())
    helper=source/'acceptance-server.ts';helper.write_text("import {startUiServer} from './src/ui-server/startUiServer';const handle=await startUiServer({projectDir:process.argv[4],homeDir:process.argv[3],port:0,uiDir:process.argv[2]});console.log(JSON.stringify({url:handle.url,port:handle.port}));for(const signal of ['SIGTERM','SIGINT'])process.on(signal,()=>{void handle.close().then(()=>process.exit());});")
    environment={**os.environ,'PHPRETRO_REPO':str(root),'PHPRETRO_DOCTOR_READ_PROJECTS':json.dumps([str(project),'/home/ubuntu/phpretro-skill-doctor/claude-agents','/home/ubuntu/phpretro-codex/work'])}
    upstream=subprocess.Popen([str(source/'node_modules/.bin/tsx'),str(helper),str(ui),str(home),str(project)],cwd=source,env=environment,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
    try:
        info=json.loads(upstream.stdout.readline());token=info['url'].split('/session/')[1];port=info['port']
        class Fixture(g.Handler):
            def authenticated(self):return True
            def do_GET(self):
                if self.path=='/candidate-dashboard':self.send(200,(root/'ops/dashboard/index.html').read_bytes(),'text/html; charset=utf-8');return
                if self.path=='/api/state':
                    actual_port=int((Path.home()/'phpretro-dashboard/port').read_text())
                    connection=http.client.HTTPConnection('127.0.0.1',actual_port,timeout=30);connection.request('GET','/api/state');data=json.loads(connection.getresponse().read());connection.close()
                    for key in ('token','dashboard_token','csrf_token'):data.pop(key,None)
                    data.update(claude_runtime=status.public_summary(runtime_policy.OPS),subscription_supervisor=supervisor.public_summary(runtime_policy.OPS))
                    self.send(200,data);return
                if self.path.endswith('/api/runtime-sessions'):self.send(200,report(canvas={'sessions':[],'available':False,'retired':True}));return
                super().do_GET()
            def do_POST(self):
                if self.path.endswith('/api/runtime-optimization'):
                    try:self.send(200,runtime_optimization.dispatch(self.body(),home=private,report=report(canvas={'sessions':[],'available':False,'retired':True})))
                    except (ValueError,TypeError,KeyError):self.send(400,{'error':'Invalid or stale preview'})
                    return
                super().do_POST()
            def proxy(self):
                _,path,_=g.backend_route(self.path);n=int(self.headers.get('Content-Length','0'));body=self.rfile.read(n) if n else None
                headers={'Host':'127.0.0.1:'+str(port),'Cookie':'skill_doctor_session='+token}
                if self.command!='GET':headers.update(Origin='http://127.0.0.1:'+str(port),**{'Content-Type':'application/json'})
                con=http.client.HTTPConnection('127.0.0.1',port,timeout=120);con.request(self.command,path,body,headers);response=con.getresponse();data=response.read();kind=response.getheader('Content-Type','application/json')
                if kind.startswith(('text/html','text/javascript')):data=g.skill_doctor_asset(data,b'/agent-doctor')
                if path.startswith('/api/bootstrap') and response.status==200:data=json.dumps(g.doctor_bootstrap(json.loads(data),True,home=home)).encode()
                self.send(response.status,data,kind);con.close()
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Fixture);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            rc=subprocess.run(['node',str(Path.home()/'phpretro-claude-code/claude-ui-browser.cjs'),str(server.server_port)],timeout=240).returncode
            coverage=json.loads((Path.home()/'phpretro-claude-code/ui-browser/coverage.json').read_text())
            coverage['implementation_sha256']=runtime_policy.fingerprint();coverage['package_sha256']=manifest['sha256'];coverage['passed']=rc==0 and all(c['pass'] for c in coverage['checks'])
            (Path.home()/'phpretro-claude-code/doctor-browser-evidence.json').write_text(json.dumps(coverage))
            raise SystemExit(rc)
        finally:server.shutdown();server.server_close()
    finally:upstream.terminate();upstream.wait(timeout=10);helper.unlink(missing_ok=True)

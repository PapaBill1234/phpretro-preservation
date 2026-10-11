#!/usr/bin/env python3
"""Human-driven Sol terminal with the existing gateway and durable controller ledger.

Headless workers keep their pinned contract. Interactive sessions have explicit
native tools, original daily guards, and a cumulative conversation allowance.
"""
import argparse,fcntl,json,os,re,signal,subprocess,sys,time,uuid
from pathlib import Path
if __name__=='__main__':os.environ.setdefault('PHPRETRO_RUNTIME','claude-code')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrity as control,runtime_policy,worker,context_usage,session_journal
from claude_code import gateway,runner,usage_policy

MODEL='gpt-6.1-sol'
TOOLS=('Bash','Read','Glob','Grep','Edit','Write','Skill')
CONVERSATION_CAP=300000
SESSION_SECONDS=1800
BASE=Path.home()/'phpretro-claude-code'
PROJECT=Path.home()/'work/claude-project'
RAW=Path.home()/'.local/share/claude/versions/2.1.287'
SYSTEM="""You are Sol 6.1 assisting the human with PHPRetro on Ubuntu through A6API.
Read this project's CLAUDE.md and AGENTS.md. The project checkout is independent
from the installed runtime. Never read credentials, auth files or private provider
payloads, change pipeline budgets/charges/STOP, publish, or contact other people.
Native /doctor is available. Include the project-wide phpretro-doctor report when
checking this project's sessions, builders, reviewers or supervisor. Missing
history/context/counters remain unknown. Deep/embedding scans are manual only.
"""

def identity(value):
    if str(uuid.UUID(value))!=value:raise ValueError('Canonical native UUID required')
    return value

def native_command(home,sid,resume=False,prompt=None):
    mcp=home/'empty-mcp.json';control.atomic_json(mcp,{'mcpServers':{}})
    args=[str(RAW),'--restricted','--tools',','.join(TOOLS),'--strict-mcp-config',
      '--mcp-config',str(mcp),'--setting-sources','','--settings',
      json.dumps({'disableAllHooks':True,'disableBundledSkills':False}),
      '--allowedTools','Read,Glob,Grep,Bash(phpretro-doctor),Bash(claude doctor),Bash(claude --version)',
      '--no-chrome','--effort','high','--model',MODEL,
      '--resume' if resume else '--session-id',sid,'--system-prompt',SYSTEM]
    if prompt is not None:args.append(prompt)
    return args

def environment(home,client):
    env=runner.command.environment(home)
    for k in ('CLAUDE_CODE_DISABLE_CLAUDE_MDS','CLAUDE_CODE_DISABLE_POLICY_SKILLS'):
        env.pop(k,None)
    env.update(client.environment())
    env['PHPRETRO_OPS']=str(runtime_policy.OPS)
    env['PHPRETRO_PROJECT_HOME']=str(Path.home())
    env['PATH']=str(Path.home()/'.local/bin')+':'+env.get('PATH','/usr/bin:/bin')
    return env

def initialize(home,project):
    config=home/'.claude';config.mkdir(mode=0o700,parents=True,exist_ok=True)
    p=config/'.claude.json'
    if not p.exists():
        control.atomic_json(p,{'hasCompletedOnboarding':True,'theme':'dark',
          'projects':{str(project):{'hasTrustDialogAccepted':True}}})
    return config

def prior_usage(ops,sid):
    total=0;found=False
    for p in (ops/'state/receipts').glob('*.json'):
        if p.name.count('.')!=1:continue
        if p.is_symlink() or p.stat().st_size>1024*1024:continue
        rec=json.loads(p.read_text())
        if rec.get('profile')!='claude-interactive' or rec.get('native_session_id')!=sid:continue
        found=True
        if rec.get('status')!='complete':raise control.IntegrityError('Existing conversation receipt must settle first')
        usage=rec.get('usage',{})
        import request_accounting
        charge=request_accounting.bounded_tokens(usage,usage.get('total_tokens',0))
        if charge is None:raise control.IntegrityError('Conversation usage is unknown')
        total+=charge
    return found,total

class InteractiveGateway(gateway.Gateway):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.halted=False;self.seen_tools=set()
    def call(self,body):
        # Serialize the whole multi-turn wrapper; the underlying lock retains the
        # one-request financial admission/physical-attempt durability contract.
        with self.interactive_lock:
            if self.halted or runtime_policy.OPS.joinpath('STOP').exists():
                raise control.IntegrityError('Interactive session stopped')
            if any(t.get('name') not in TOOLS for t in body.get('tools',[])):
                raise control.IntegrityError('Unexpected interactive tool')
            try:
                native=identity(json.loads(body.get('metadata',{}).get('user_id','{}')).get('session_id'))
            except (ValueError,TypeError,AttributeError):
                self.halted=True;raise control.IntegrityError('Native session identity missing')
            if native!=self.total['session_id']:
                self.halted=True;raise control.IntegrityError('Native session changed; exit and launch the managed conversation')
            self.cancelled()
            for message in body.get('messages',[]):
                parts=message.get('content',[])
                if not isinstance(parts,list):continue
                for part in parts:
                    if part.get('type')=='tool_result' and part.get('tool_use_id') not in self.seen_tools:
                        self.seen_tools.add(part.get('tool_use_id'))
                        self.context.data['tool_errors']+=int(part.get('is_error') is True)
                        self.journal.add('tool',json.dumps(part.get('content','')),rc=1 if part.get('is_error') else 0)
            self.arm()
            try:
                response=super().call(body)
                for part in response.get('content',[]):
                    if part.get('type')=='text':self.journal.add('assistant',part.get('text',''))
                    if part.get('type')=='tool_use':
                        self.context.tool(part['name']+' '+json.dumps(part.get('input',{})))
                        self.journal.add('tool',part['name']+' '+json.dumps(part.get('input',{})))
                if not usage_policy.continuation_allowed(self.data,self.total):self.halted=True
                self.context.save();return response
            except Exception:
                self.halted=True;raise


def transcript_observations(home,sid,context,journal=None):
    """Actual invocation markers only, never infer loaded skills from files."""
    invoked=set();observed=set(context.data.get('native_event_ids',[]));root=home/'.claude/projects'
    for p in root.glob('*/'+sid+'.jsonl'):
        if p.is_symlink() or p.parent.is_symlink() or p.stat().st_size>8_000_000:continue
        for line in p.read_text().splitlines():
            try:event=json.loads(line)
            except ValueError:continue
            if journal and event.get('type')=='user' and isinstance(event.get('uuid'),str) and event['uuid'] not in observed:
                content=event.get('message',{}).get('content',[])
                chunks=[p.get('text','') for p in content if isinstance(p,dict) and p.get('type')=='text'] if isinstance(content,list) else [content] if isinstance(content,str) else []
                journal.add('brief','\n'.join(chunks));observed.add(event['uuid'])
            message=event.get('message',{});parts=message.get('content',[]) if isinstance(message,dict) else []
            if isinstance(parts,str):parts=[{'type':'text','text':parts}]
            for part in parts if isinstance(parts,list) else []:
                if not isinstance(part,dict):continue
                if part.get('type')=='tool_use' and part.get('name')=='Skill':
                    name=part.get('input',{}).get('skill','')
                    if isinstance(name,str) and re.fullmatch(r'[a-zA-Z0-9:_-]{1,80}',name):invoked.add(name)
                text=part.get('text','')
                if isinstance(text,str):
                    invoked.update(re.findall(r'<command-name>/([a-zA-Z0-9:_-]{1,80})</command-name>',text))
    context.data['native_event_ids']=sorted(observed)[:512]
    context.data['native_interactive']={'slash_commands_enabled':True,'tools':list(TOOLS),'invoked':sorted(invoked)}
    context.save()


def settle(path,rec,total,rc):
    import orchestrator
    rec.update(status='complete',rc=rc,usage=total,completed_at=time.time())
    rec.pop('command',None);control.atomic_json(path,rec)
    control.atomic_json(path.with_suffix('.sandbox.json'),{'run_id':rec['run_id'],'drained':True})
    with (runtime_policy.OPS/'locks/orchestrator.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        used=orchestrator.accounted_usage(total)
        if used['accounted_tokens']>rec['reserved_tokens']:raise control.IntegrityError('Interactive reservation exceeded')
        orchestrator.log_model_run('interactive',MODEL,'',None,rc,
          'success' if rc==0 else 'interrupted',used,'claude-interactive',
          ts_start=rec['ts_start'],ts_end=orchestrator.now(),run_id=rec['run_id'],charged_tokens=used['accounted_tokens'])
        orchestrator.write_json(orchestrator.STATE_JSON,orchestrator.load_state())  # Canonical durable settlement; no unit reset.


def launch(sid=None,prompt=None,print_mode=False,output_format="text"):
    import threading,orchestrator
    if not print_mode and not sys.stdin.isatty():raise control.IntegrityError('Use an Ubuntu terminal or ssh -t')
    if not PROJECT.is_dir():raise control.IntegrityError('Project terminal checkout is not installed')
    if sid:identity(sid)
    requested_resume=sid is not None
    sid=sid or str(uuid.uuid4());home=BASE/'terminal-home'/sid
    home.mkdir(mode=0o700,parents=True,exist_ok=True);initialize(home,PROJECT)
    with (runtime_policy.OPS/'locks/orchestrator.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if not runtime_policy.ready(MODEL):raise control.IntegrityError('Reviewed Sol runtime admission is not ready')
        state=orchestrator.load_state()
        if state.get('reservations'):raise control.IntegrityError('Wait for the existing paid worker to finish')
        resume,used=prior_usage(runtime_policy.OPS,sid)
        if requested_resume and not resume:raise control.IntegrityError('Unknown managed conversation; do not adopt another session')
        limit=min(CONVERSATION_CAP-used,orchestrator.PER_UNIT_TOKEN_CAP)
        if limit<=runner.admission.request_ceiling(runtime_policy.load()):raise control.IntegrityError('Conversation allowance exhausted; prior charges retained')
        rid=orchestrator.admit_paid(state,None,'interactive',limit=limit)
        rec=dict(state['reservations'][rid]);path=runtime_policy.OPS/'state/receipts'/(rid+'.json')
        usage=runtime_policy.OPS/'logs'/(rid+'.usage.json')
        rec.update(runtime='claude-code',profile='claude-interactive',model=MODEL,native_session_id=sid,
          status='running',profile_home=str(home),cwd=str(PROJECT),usage_path=str(usage),
          prepared_at=time.time(),timeout=SESSION_SECONDS,grace=10,
          worker_pid=os.getpid(),worker_identity=worker.process_identity(os.getpid()))
        control.atomic_json(path,rec)
    lease=worker.claim(path)
    if lease is None:raise control.IntegrityError('Interactive receipt already owned')
    policy=runtime_policy.load();ceiling=runner.admission.request_ceiling(policy)
    total=runner.zero(sid,MODEL,ceiling)
    total.update(usage_schema=gateway.SCHEMA,unknown_request_ceilings=[],provider='unlaunched:gateway',cost_status='quoted-estimate')
    def checkpoint():control.atomic_json(usage,total)
    context=context_usage.Recorder(path.with_suffix('.context.json'),list(TOOLS))
    journal=session_journal.Journal(path.with_suffix('.session.json'))
    client=None;child=None;rc=1;foreground=os.tcgetpgrp(sys.stdin.fileno()) if not print_mode else None
    previous=signal.signal(signal.SIGTTOU,signal.SIG_IGN)
    prior_term=signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(InterruptedError()))
    try:
        secrets=gateway.credentials(policy['providers_file'])
        # Native tools stay on the human's separate checkout; inference secrets
        # stay exclusively in this parent and never enter the native CLI env.
        client=InteractiveGateway(policy,{**rec,'_receipt_path':str(path)},MODEL,total,checkpoint,journal,context,secrets)
        client.interactive_lock=threading.Lock()
        import provider_routing
        journal.secrets=tuple(provider_routing.credential(secrets,p,MODEL) for p in client.routes)+(client.token,)
        checkpoint();print('PHPRetro Sol 6.1 | A6API first | /doctor available | native session '+sid,file=sys.stderr if print_mode else sys.stdout,flush=True)
        args=native_command(home,sid,resume,prompt)
        if print_mode:args+=['-p','--output-format',output_format]+(['--verbose'] if output_format=='stream-json' else [])
        child=subprocess.Popen(args,env=environment(home,client),cwd=PROJECT,process_group=0)
        control.atomic_json(worker.child_path(path),{'run_id':rid,'child_pid':child.pid,'child_identity':worker.process_identity(child.pid)})
        if not print_mode:os.tcsetpgrp(sys.stdin.fileno(),child.pid)
        while child.poll() is None:
            transcript_observations(home,sid,context,journal)
            if time.time()>=client.deadline or client.halted or (runtime_policy.OPS/'STOP').exists():
                worker.cancel_launch(path,rec);worker.stop(child,10);break
            time.sleep(.5)
        rc=child.wait(timeout=10)
    finally:
        if child:worker.stop(child,10)
        if not print_mode:os.tcsetpgrp(sys.stdin.fileno(),foreground)
        signal.signal(signal.SIGTTOU,previous)
        signal.signal(signal.SIGTERM,prior_term)
        if client:
            client.halted=True
            client.close()
            with client.interactive_lock:checkpoint()  # All physical requests drained before settlement.
        else:checkpoint()
        transcript_observations(home,sid,context,journal);context.finish(False)
        journal.add('result','Terminal closed',rc=rc);journal.finish(rc==0)
        try:settle(path,rec,total,rc)
        finally:lease.close()
    print('Saved in Doctor. Resume with: claude --resume '+sid,file=sys.stderr if print_mode else sys.stdout,flush=True)
    return rc


def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    # Exact pinned worker and installation subcommands are not reconfigured.
    if any(a in ('--version','-v','--help','-h') for a in argv) or argv and argv[0] in ('doctor','auth','update','install','uninstall','plugin','mcp'):
        os.execv(str(RAW),[str(RAW),*argv])
    if any(a in ('-p','--print') for a in argv) and '--disable-slash-commands' in argv and re.fullmatch(r'http://127\.0\.0\.1:[0-9]+',os.environ.get('ANTHROPIC_BASE_URL','')) and os.environ.get('ANTHROPIC_AUTH_TOKEN'):
        os.execv(str(RAW),[str(RAW),*argv])
    parser=argparse.ArgumentParser(description='PHPRetro Sol 6.1 terminal, A6API first, native /doctor')
    parser.add_argument('-p','--print',dest='print_mode',action='store_true');parser.add_argument('--output-format',choices=['text','json','stream-json'],default='text')
    parser.add_argument('--resume','-r',type=identity);parser.add_argument('prompt',nargs='?')
    args=parser.parse_args(argv)
    os.environ['PHPRETRO_RUNTIME']='claude-code'
    os.environ['PHPRETRO_REPO']=str(Path(__file__).resolve().parents[2])
    try:return launch(args.resume,args.prompt,args.print_mode,args.output_format)
    except (control.IntegrityError,orchestrator_error(),BlockingIOError,ValueError,InterruptedError,KeyboardInterrupt):
        print('PHPRetro terminal admission failed. Existing state, receipts and charges retained.',file=sys.stderr);return 75

def orchestrator_error():
    import orchestrator
    return orchestrator.BudgetDenied

if __name__=='__main__':raise SystemExit(main())

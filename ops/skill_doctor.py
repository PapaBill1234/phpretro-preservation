#!/usr/bin/env python3
"""Private, read-only Skill Doctor reports. Never mutate agent configuration."""
import argparse, json, math, os, subprocess, time
from pathlib import Path
import integrity as control
import context_usage

HOME=Path.home()
BASE=HOME/'phpretro-skill-doctor'
CLI=BASE/'runtime/node_modules/.bin/skill-doctor'
OPS=HOME/'phpretro-ops'
REPO=Path(__file__).resolve().parent.parent
STATE=OPS/'state/skill-doctor.json'
VERSION='0.7.0'

def number(value):
    return type(value) is int and 0<=value<=100000000

def cost(path, label):
    env={k:os.environ[k] for k in ('PATH','LANG') if k in os.environ}
    env.update(HOME=str(BASE/'audit-home'),NO_COLOR='1')
    args=[str(CLI),'cost',str(path),'--platform','codex','--scope','project',
          '--source','skill','--tokenizer','approx','--json']
    result=subprocess.run(args,env=env,capture_output=True,text=True,timeout=60,check=True)
    if len(result.stdout)>2*1024*1024:raise ValueError('oversized audit')
    raw=json.loads(result.stdout)
    control.atomic_json(BASE/'reports'/(label+'.json'),raw)
    summary=raw['summary']
    tokens=summary['totalEstimatedTokens']
    assert number(tokens)
    items=raw.get('items',[])
    return {'id':label,'estimated_tokens':tokens,'items':len(items),
            'tokenizer':'approx','usage_evidence':'unknown'}

def collect():
    os.umask(0o077)
    for path in (BASE,BASE/'reports',BASE/'audit-home',BASE/'snapshots'):
        path.mkdir(parents=True,mode=0o700,exist_ok=True)
    env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'HOME':str(BASE/'audit-home')}
    assert subprocess.check_output([str(CLI),'--version'],env=env,text=True,timeout=10).strip()==VERSION
    state=json.loads((OPS/'state/units.state.json').read_text())
    if state.get('reservations'):return # Avoid mixing active runs with settled snapshots.
    audits=[cost(REPO,'project'),cost(HOME/'phpretro-codex/work','supervisor')]
    latest={}
    agent_latest={}
    for path in (OPS/'state/receipts').glob('*.json'):
        if path.name.count('.')!=1 or path.stat().st_size>1024*1024:continue
        row=json.loads(path.read_text())
        role=row.get('role')
        if row.get('runtime')!='openhands' or row.get('status')!='complete' or role not in ('builder','reviewer'):continue
        if row.get('completed_at',0)>latest.get(role,{}).get('completed_at',0):latest[role]=row
        model=row.get('model')
        if model in ('gpt-6-luna','gpt-6.1-sol','deepseek-v4.1-flash'):
            key=role+'-'+model
            if row.get('completed_at',0)>agent_latest.get(key,{}).get('completed_at',0):agent_latest[key]=row
    # Audit workshop is separate from the real runtime's enabled skills.
    workshop=BASE/'agents'
    for key,row in agent_latest.items():
        prompt=Path(row['prompt_path']).resolve()
        if not prompt.is_relative_to(OPS.resolve()) or not prompt.is_file() or prompt.stat().st_size>1024*1024:continue
        target=workshop/'.agents/skills'/key
        target.mkdir(mode=0o700,parents=True,exist_ok=True)
        control.atomic_text(target/'SKILL.md','---\nname: '+key+'\ndescription: Retained OpenHands role brief for audit only\n---\n\n'+prompt.read_text())
    workshop.mkdir(mode=0o700,exist_ok=True)
    control.atomic_text(workshop/'AGENTS.md','This workshop contains audit snapshots of completed OpenHands builder and reviewer briefs, grouped by role and model. They are not Codex-injected skills. Run Deep Scan manually. Treat findings as proposals; preserve required safeguards. Actual tool-use metadata is shown on the PHPRetro Builders page.\n')
    for role,row in latest.items():
        prompt=Path(row['prompt_path']).resolve()
        if not prompt.is_relative_to(OPS.resolve()) or not prompt.is_file() or prompt.stat().st_size>1024*1024:continue
        view=BASE/'snapshots'/role
        view.mkdir(mode=0o700,exist_ok=True)
        control.atomic_text(view/'AGENTS.md',prompt.read_text())
        item=cost(view,'openhands-'+role)
        item.update(basis='retained-role-brief',source_completed_at=row['completed_at'])
        receipt_id=row.get('run_id','')
        if isinstance(receipt_id,str) and len(receipt_id)==36 and all(c in '0123456789abcdef-' for c in receipt_id):
            history=OPS/'state/receipts'/(receipt_id+'.context.json')
            try:
                if history.stat().st_size>65536:raise ValueError()
                item['history']=context_usage.summary(json.loads(history.read_text()))
            except (OSError,ValueError,TypeError):pass
        audits.append(item)
    control.atomic_json(STATE,{'schema':'phpretro.skill-doctor.v1','checked_at':time.time(),
                              'version':VERSION,'mode':'report-only','audits':audits})

def public_summary(ops=OPS):
    try:
        path=ops/'state/skill-doctor.json'
        if path.stat().st_size>65536:raise ValueError()
        data=json.loads(path.read_text())
        if not isinstance(data,dict) or not isinstance(data.get('audits'),list):raise ValueError()
        if data['schema']!='phpretro.skill-doctor.v1' or type(data['checked_at']) not in (int,float) or not math.isfinite(data['checked_at']):raise ValueError()
        audits=[]
        for item in data['audits'][:10]:
            if not isinstance(item,dict):continue
            if item.get('id') not in ('project','supervisor','openhands-builder','openhands-reviewer'):continue
            if not number(item.get('estimated_tokens')) or not number(item.get('items')):continue
            safe={k:item[k] for k in ('id','estimated_tokens','items')}
            history=item.get('history')
            if isinstance(history,dict):
                keys=('tool_calls','tool_errors','repeated_commands','events','brief_chars','requests')
                if all(number(history.get(k)) for k in keys):
                    safe['history']={k:history[k] for k in keys}
                    safe['history']['usage_status']='complete' if history.get('usage_status')=='complete' else 'partial'
                    safe['history']['unused_tools']=['execute'] if history.get('unused_tools')==['execute'] else []
                    for key in ('first_context_tokens','peak_context_tokens','peak_tool_schema_tokens'):
                        safe['history'][key]=history.get(key) if number(history.get(key)) else None
            audits.append(safe)
        return {'available':True,'checked_at':data['checked_at'],'mode':'report-only',
                'version':VERSION,'tokenizer':'approx','audits':audits}
    except (OSError,ValueError,KeyError,TypeError):return {'available':False,'mode':'report-only'}

if __name__=='__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    collect()
    print(json.dumps(public_summary()))

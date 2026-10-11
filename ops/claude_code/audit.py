"""Read-only Claude role brief snapshots; never copies native credentials/config."""
import json
from pathlib import Path
import session_journal

def collect(home,ops,base,cost):
    latest={};workshop=base/'claude-agents';workshop.mkdir(parents=True,mode=0o700,exist_ok=True)
    for path in (ops/'state/receipts').glob('*.json'):
        if path.name.count('.')!=1 or path.is_symlink() or path.stat().st_size>1024*1024:continue
        row=json.loads(path.read_text())
        if row.get('runtime')!='claude-code' or row.get('role') not in ('builder','reviewer'):continue
        key=row['role']+'-'+str(row.get('model','unknown'))
        if not all(c.isalnum() or c in '-_.' for c in key):continue
        if row.get('prepared_at',0)>latest.get(key,{}).get('prepared_at',0):latest[key]=row
    for key,row in latest.items():
        prompt=Path(row.get('prompt_path','')).resolve()
        if not prompt.is_relative_to(ops.resolve()) or not prompt.is_file() or prompt.stat().st_size>1024*1024:continue
        target=workshop/'.claude/skills'/key;target.mkdir(parents=True,mode=0o700,exist_ok=True)
        (target/'SKILL.md').write_text('---\nname: '+key+'\ndescription: Native Claude role brief retained for audit only\n---\n\n'
          'Audit snapshot, not automatically injected. Actual native CLI session: '+str(row.get('usage',{}).get('session_id','unknown'))+'\n\n'+session_journal.redact(prompt.read_text()))
    return cost(workshop,'claude-agents','claude')

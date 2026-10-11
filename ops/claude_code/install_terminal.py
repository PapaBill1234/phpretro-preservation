#!/usr/bin/env python3
"""Install the human terminal entry point after normal reviewed runtime installation."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
os.environ.setdefault('PHPRETRO_RUNTIME','claude-code')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrity as control,runtime_policy
from claude_code import interactive

GUIDANCE="""# PHPRetro human terminal

Read AGENTS.md. This is a separate human checkout of the project, not the live
installed runtime or an autonomous builder checkout. Preserve others' work.

You are using A6API Sol 6.1 via the private receipt-scoped gateway. Native /doctor
and /doctor prompt-audit work here. For project-wide session/agent diagnostics,
run `phpretro-doctor` first and include its recorded builder, reviewer, supervisor
and interactive evidence. The dashboard has detailed timelines and manual scans.
Do not treat configuration files as proof of injected context or invent savings.
Never read secrets, auth/environment files or private provider payloads. Never
change pipeline STOP, caps, receipts/charges, review approval or auto-enable Deep
Scan/embeddings/optimization controls. Do not publish or message others.
"""

def snapshot(path,backup,index):
    if path.is_symlink():return {'path':str(path),'kind':'symlink','target':os.readlink(path)}
    if not path.exists():return {'path':str(path),'kind':'absent'}
    if not path.is_file() or path.stat().st_size>2_000_000:raise control.IntegrityError('Bounded launcher file required')
    blob=backup/(str(index)+'.bin');blob.write_bytes(path.read_bytes());blob.chmod(0o600)
    return {'path':str(path),'kind':'file','blob':str(blob),'mode':path.stat().st_mode & 0o777}

def restore(records):
    for rec in reversed(records):
        path=Path(rec['path'])
        if path.is_symlink() or path.is_file():path.unlink()
        if rec['kind']=='symlink':path.symlink_to(rec['target'])
        elif rec['kind']=='file':
            path.write_bytes(Path(rec['blob']).read_bytes());path.chmod(rec['mode'])

def replace_files(payloads,backup):
    records=[snapshot(path,backup,i) for i,(path,_,_) in enumerate(payloads)]
    control.atomic_json(backup/'previous-files.json',records)
    try:
        for path,text,mode in payloads:
            if path.is_symlink():path.unlink()
            control.atomic_text(path,text);path.chmod(mode)
    except BaseException:
        restore(records);control.atomic_json(backup/'rollback.json',{'restored':True,'at':time.time()});raise


def install():
    os.umask(0o077)
    if not runtime_policy.ready(interactive.MODEL):raise control.IntegrityError('Normal reviewed active runtime required')
    if not interactive.RAW.is_file():raise control.IntegrityError('Pinned native binary missing')
    cli=Path.home()/'.local/bin/claude'
    expected='#!/bin/sh\nexport PHPRETRO_RUNTIME=claude-code\nexec /usr/bin/python3 '+str(Path(__file__).with_name('interactive.py'))+' "$@"\n'
    if cli.is_symlink():
        if cli.resolve()!=interactive.RAW.resolve():raise control.IntegrityError('Unexpected Claude launcher; retain it')
    elif not cli.is_file() or cli.read_text()!=expected:raise control.IntegrityError('Unexpected Claude launcher; retain it')
    source=Path(__file__).resolve().parents[2]
    if interactive.PROJECT.is_symlink() or any(p.is_symlink() for p in interactive.PROJECT.parents):raise control.IntegrityError('Human project symlink is not allowed')
    if not interactive.PROJECT.exists():
        interactive.PROJECT.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        subprocess.run(['git','-C',str(source),'worktree','add','-b','codex/claude-human-terminal',str(interactive.PROJECT),'HEAD'],check=True)
    interactive.validate_project(interactive.PROJECT,source)
    if (interactive.PROJECT/'CLAUDE.md').is_symlink():raise control.IntegrityError('Human instructions symlink is not allowed')
    if (interactive.PROJECT/'CLAUDE.md').exists() and (interactive.PROJECT/'CLAUDE.md').read_text()!=GUIDANCE:
        raise control.IntegrityError('Existing human project instructions differ; retain them')
    backup=interactive.BASE/'terminal-installations'/str(time.time_ns());backup.mkdir(parents=True,mode=0o700)
    report=Path.home()/'.local/bin/phpretro-doctor'
    desktop=Path.home()/'Desktop/Claude-Code-Sol-Chat.desktop'
    desktop.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    manifest={'installed_at':time.time(),'source_head':subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip(),'implementation_sha256':runtime_policy.fingerprint(),'project':str(interactive.PROJECT),'backup':str(backup)}
    replace_files([
      (interactive.PROJECT/'CLAUDE.md',GUIDANCE,0o600),
      (cli,expected,0o755),
      (report,'#!/bin/sh\nexport PHPRETRO_RUNTIME=claude-code\nexec /usr/bin/python3 '+str(Path(__file__).with_name('doctor_report.py'))+' "$@"\n',0o755),
      (desktop,'[Desktop Entry]\nType=Application\nName=Claude Code Sol Chat\nComment=PHPRetro Sol 6.1 via A6API, native doctor and saved sessions\nExec='+str(cli)+'\nIcon=utilities-terminal\nTerminal=true\nCategories=Development;\n',0o755),
      (interactive.BASE/'terminal-installation.json',json.dumps(manifest)+'\n',0o600)],backup)
    print('Ubuntu claude and Claude Code Sol Chat installed. Existing headless commands retain their pinned contract.')

if __name__=='__main__':install()

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
    (interactive.PROJECT/'CLAUDE.md').write_text(GUIDANCE)
    backup=interactive.BASE/'terminal-installations'/str(time.time_ns());backup.mkdir(parents=True,mode=0o700)
    control.atomic_json(backup/'previous-launcher.json',{'path':str(cli),'target':str(cli.resolve()) if cli.is_symlink() else None,'text':None if cli.is_symlink() else cli.read_text()})
    if cli.is_symlink():cli.unlink()
    control.atomic_text(cli,expected);cli.chmod(0o755)
    report=Path.home()/'.local/bin/phpretro-doctor'
    control.atomic_text(report,'#!/bin/sh\nexport PHPRETRO_RUNTIME=claude-code\nexec /usr/bin/python3 '+str(Path(__file__).with_name('doctor_report.py'))+' "$@"\n');report.chmod(0o755)
    desktop=Path.home()/'Desktop/Claude-Code-Sol-Chat.desktop'
    control.atomic_text(desktop,'[Desktop Entry]\nType=Application\nName=Claude Code Sol Chat\nComment=PHPRetro Sol 6.1 via A6API, native doctor and saved sessions\nExec='+str(cli)+'\nIcon=utilities-terminal\nTerminal=true\nCategories=Development;\n');desktop.chmod(0o755)
    control.atomic_json(interactive.BASE/'terminal-installation.json',{'installed_at':time.time(),'source_head':subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip(),'implementation_sha256':runtime_policy.fingerprint(),'project':str(interactive.PROJECT),'backup':str(backup)})
    print('Ubuntu claude and Claude Code Sol Chat installed. Existing headless commands retain their pinned contract.')

if __name__=='__main__':install()

#!/usr/bin/env python3
"""Restore only the owned authorized flow after reviewed Claude cutover."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import integrity as control,runtime_policy,worker
from claude_code import supervisor

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--enable',action='store_true');args=parser.parse_args()
    if not args.enable:parser.error('Explicit --enable required')
    os.umask(0o077);ops=runtime_policy.OPS;stop=ops/'STOP';marker=ops/'state/maintenance-pause.json'
    pause=json.loads(marker.read_text());activation_path=ops/'state/claude-code-activation.json'
    previous=json.loads(activation_path.read_text())
    if (pause.get('owner')!='codex-claude-code-runtime-migration' or not stop.is_file() or
        stop.stat().st_mtime_ns!=pause.get('stop_mtime_ns') or pause.get('previous_stop') is not False):
        raise control.IntegrityError('Owned migration pause changed; preserve intentional STOP')
    if not previous.get('installed'):raise control.IntegrityError('Reviewed paused installation required')
    state=json.loads((ops/'state/units.state.json').read_text())
    if state.get('reservations'):raise control.IntegrityError('Existing reservations must drain')
    active={**previous,'enabled':True,'authorized_by':'user','review_policy':runtime_policy.load()['review_policy'],'enabled_at':time.time()}
    control.atomic_json(activation_path,active)
    try:
        if not runtime_policy.ready(runtime_policy.load()['model_roles']['builder']):
            raise control.IntegrityError('Current auth/provider/source/isolation/browser validation required')
        control.atomic_json(supervisor.ENABLED,{'schema':'phpretro.claude-activation.v1','enabled_at':time.time()})
        # Recheck ownership immediately before clearing a temporary STOP.
        if stop.stat().st_mtime_ns!=pause['stop_mtime_ns']:raise control.IntegrityError('STOP changed during activation')
        stop.unlink()
        subprocess.run(['sudo','-n','systemctl','enable','--now','phpretro-orchestrator.timer'],check=True)
        subprocess.run(['systemctl','--user','enable','--now','phpretro-claude-supervisor.timer'],env=worker.bus_env(),check=True)
        pause.update(resumed_at=time.time(),resumed_runtime='claude-code');control.atomic_json(marker,pause)
    except BaseException:
        if not stop.exists():control.atomic_text(stop,'Claude activation failed; safe pause retained\n')
        control.atomic_json(activation_path,previous);supervisor.ENABLED.unlink(missing_ok=True)
        subprocess.run(['sudo','-n','systemctl','stop','phpretro-orchestrator.timer'],check=False)
        subprocess.run(['systemctl','--user','disable','--now','phpretro-claude-supervisor.timer'],env=worker.bus_env(),check=False)
        raise
    print('Reviewed Claude runtime and thirty-minute supervisor enabled. Historical caps and parked units unchanged.')
if __name__=='__main__':main()

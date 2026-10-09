#!/usr/bin/env python3
"""Explicit operator activation, only after the pipeline is already running."""
import argparse, os, subprocess, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import codex_account as account
import codex_supervisor as supervisor
import integrity, runtime_policy, worker

def main():
    os.umask(0o077)
    ap=argparse.ArgumentParser(); ap.add_argument('--enable',action='store_true'); ap.add_argument('--disable',action='store_true')
    args=ap.parse_args()
    if args.enable==args.disable: ap.error('choose --enable or --disable')
    if args.enable:
        state=supervisor.snapshot()
        assert not state['stop'] and state['pipeline_active'] and state['state_valid'], 'pipeline must already be running'
        assert not state['issues'], 'first resolve current health issues'
        assert account.allowed(account.read_account()), 'subscription quota/model/auth unavailable or near limit'
        assert runtime_policy.ready(), 'exact source runtime validation required'
        integrity.atomic_json(supervisor.ENABLED,{'schema':'phpretro.codex-activation.v1','enabled_at':time.time()})
        try:
            subprocess.run(['systemctl','--user','enable','--now','phpretro-codex-supervisor.timer'],env=worker.bus_env(),check=True)
        except BaseException:
            supervisor.ENABLED.unlink(missing_ok=True)
            subprocess.run(['systemctl','--user','disable','--now','phpretro-codex-supervisor.timer'],env=worker.bus_env())
            raise
        print('Supervisor enabled; no pipeline scope, STOP, or budgets changed.')
    else:
        supervisor.ENABLED.unlink(missing_ok=True)
        subprocess.run(['systemctl','--user','disable','--now','phpretro-codex-supervisor.timer'],env=worker.bus_env(),check=True)
        subprocess.run(['systemctl','--user','stop','phpretro-codex-supervisor.service'],env=worker.bus_env(),check=True)
        supervisor.cycle(inspect=True)
        print('Supervisor disabled; coding pipeline untouched.')

if __name__=='__main__': main()

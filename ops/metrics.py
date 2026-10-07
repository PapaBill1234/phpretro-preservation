#!/usr/bin/env python3
"""Read-only throughput snapshot. Historical occupancy is never reconstructed
from publication timestamps. All output is counts/times, not prompts or logs.
"""
import argparse,json,statistics,time
from datetime import datetime,timezone
from pathlib import Path
import throughput

def rows(path):
    if not path.is_file(): return []
    result=[]
    for line in path.read_text().splitlines():
        if line.strip(): result.append(json.loads(line))
    return result

def timestamp(value):
    try: return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
    except (ValueError,AttributeError): return None

def snapshot(state_dir,repo,start,end):
    import yaml
    board={u['id']:u for u in yaml.safe_load((state_dir/'units.live.yaml').read_text())['units']}
    events=rows(state_dir/'process-events.jsonl')
    result=throughput.metrics(events,start,end)
    result.update(start=throughput.iso(start),end=throughput.iso(end),
        ready_queue_depth=len(throughput.ready_buffer(board,repo,6_000_000)),
        ready_target=throughput.READY_TARGET,source='process-events.jsonl immutable exit receipts',
        STOP=(state_dir.parent/'STOP').exists())
    # Legacy dispatch and actual merge events can establish elapsed delivery
    # time, but their delayed run-end records cannot establish CPU occupancy.
    legacy=rows(state_dir/'events.jsonl')
    dispatch={};seen=set();elapsed=[]
    for row in legacy+events:
        ts=timestamp(row.get('ts'));uid=row.get('unit')
        if ts is None or not uid: continue
        if row.get('kind')=='dispatched' or row.get('kind')=='process_dispatched' and row.get('role')=='builder':
            dispatch.setdefault(uid,ts)
        if row.get('kind')=='merged' and start<=ts<=end and uid in dispatch and uid not in seen and ts>=dispatch[uid]:
            elapsed.append((ts-dispatch[uid])/60);seen.add(uid)
    result['legacy_dispatch_to_merge_median_minutes']=statistics.median(elapsed) if elapsed else None
    result['legacy_timed_units']=len(elapsed)
    result['limitations']=['Git deliveries include docs/scaffolds; they are not product completion.',
        'Historical occupancy is unknown without independent process-exit receipts.',
        'Elapsed delivery time includes stopped/idle time and every retry; legacy history deduplicates by unit.',
        'Ready depth is dependency/evidence/path readiness before daily admission; the existing caps still govern dispatch.']
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--state',type=Path,required=True);ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--start',required=True);ap.add_argument('--end');ap.add_argument('--output',type=Path)
    a=ap.parse_args();end=timestamp(a.end) if a.end else time.time();start=timestamp(a.start)
    if start is None or end is None or end<=start: raise ValueError('invalid measurement window')
    result=snapshot(a.state,a.repo,start,end)
    text=json.dumps(result,indent=2)+'\n'
    if a.output: a.output.write_text(text)
    else: print(text,end='')

#!/usr/bin/env python3
"""Local metadata for native /doctor; all recorded project runtime roles."""
import json,os,sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import doctor_sessions

def report(home=Path('/home/ubuntu')):
    result=doctor_sessions.sessions(home)
    rows=result['sessions']
    return {'project':'PHPRetro','sessions':len(rows),'session_limit':result['session_limit'],
      'coverage':result['evidence'],'runtimes':result['runtimes'],
      'roles':dict(Counter(row.get('role','Unknown') for row in rows)),
      'models':dict(Counter(row.get('model','Unknown') for row in rows)),
      'issues':result['issues'],'billing_collected_at':result.get('billing_collected_at'),
      'recent_sessions':[{k:r.get(k) for k in ('id','native_session_id','runtime','role','model','provider','status','tokens','conservative_tokens','complete','journal_available')} for r in rows[:30]],
      'notes':['All recorded builder, reviewer, supervisor and interactive runtime types are included.',
        'Retention and missing historical transcripts remain explicit; account calls are not reconstructed sessions.',
        'No inference or Deep Scan is run by this report. Use the dashboard for timelines and manual analysis.']}

if __name__=='__main__':print(json.dumps(report(),indent=2))

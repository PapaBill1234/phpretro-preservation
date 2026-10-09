"""One exact-head required-CI snapshot; pending checks defer without rebuilding."""
import json

def evaluate(pr,head,required):
    if not isinstance(pr,dict) or pr.get('headRefOid')!=head:return 'failed','PR head differs from approved head'
    if pr.get('state')!='OPEN':return 'pending','PR is not open'
    if pr.get('isDraft'):return 'pending','PR is draft'
    checks=pr.get('statusCheckRollup')
    if not isinstance(checks,list):return 'pending','CI status unavailable'
    for name in sorted(required):
        rows=[r for r in checks if isinstance(r,dict) and (r.get('name') or r.get('context'))==name]
        if not rows:return 'pending','required check missing: '+name
        for row in rows:
            if row.get('__typename')=='StatusContext':
                status=row.get('state')
                if status in ('ERROR','FAILURE'):return 'failed','required check failed: '+name
                if status!='SUCCESS':return 'pending','required check pending: '+name
            else:
                if row.get('status')!='COMPLETED':return 'pending','required check pending: '+name
                if row.get('conclusion')!='SUCCESS':return 'failed','required check failed: '+name
    if pr.get('mergeStateStatus')!='CLEAN':return 'pending','GitHub merge readiness: '+str(pr.get('mergeStateStatus','unknown'))
    return 'ready','required CI passed on approved head'

def check(pr,head,repo,run):
    rc,out=run(['gh','api',f'repos/{repo}/rules/branches/main'],timeout=30)
    if rc:return 'pending','required-check policy unavailable'
    try:
        rules=json.loads(out); required={'foundation'}
        for rule in rules:
            if rule.get('type')=='required_status_checks':
                required.update(r['context'] for r in rule['parameters']['required_status_checks'])
        rc,out=run(['gh','pr','view',str(pr),'--repo',repo,'--json',
                    'state,isDraft,headRefOid,mergeStateStatus,statusCheckRollup'],timeout=30)
        if rc:return 'pending','GitHub CI snapshot unavailable'
        return evaluate(json.loads(out),head,required)
    except (ValueError,TypeError,KeyError,AttributeError):return 'pending','GitHub CI snapshot invalid'

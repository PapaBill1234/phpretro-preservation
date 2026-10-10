"""Claude engine admission. Source/CLI/auth evidence is mandatory, never forged."""
import json,math,subprocess,time
from pathlib import Path
import integrity as control

def load(path):
    data=json.loads(Path(path).read_text())
    if data.get('schema')!='phpretro.claude-code-policy.v1' or data.get('runtime')!='claude-code':raise control.IntegrityError('Invalid Claude policy')
    if data.get('automatic_planning') is not False or data.get('max_builders')!=2:raise control.IntegrityError('Claude dispatch ceiling changed')
    if data.get('auth_mode') not in ('subscription','api'):raise control.IntegrityError('Unconfigured Claude authentication')
    if data.get('estimated_daily_cost_ceiling')!=5.0:raise control.IntegrityError('Original estimated daily cap changed')
    if data.get('required_review_families') not in (1,2,3):raise control.IntegrityError('Invalid Claude review policy')
    if data['required_review_families']==1 and data.get('review_policy')!='user-authorized-independent-claude-sessions':raise control.IntegrityError('Independent session policy not authorized')
    if data.get('context_window_tokens')!=1000000 or data.get('max_output_tokens')!=4096:raise control.IntegrityError('Unvalidated Claude request bounds')
    for settings in data['models'].values():
        if settings.get('provider_order')!=['anthropic'] or settings.get('input_includes_cache') is not False:raise control.IntegrityError('Unvalidated Claude route/accounting')
        for key in ('input','output','cache_read','cache_write'):
            if type(settings.get(key)) not in (int,float) or not 0<=settings[key]<=100:raise control.IntegrityError('Invalid Claude price quote')
    return data

def authenticated(data):
    try:
        r=subprocess.run([data['cli'],'auth','status','--json'],capture_output=True,text=True,timeout=15)
        j=json.loads(r.stdout)
        return r.returncode==0 and j.get('loggedIn') is True and (data['auth_mode']!='subscription' or j.get('authMethod')=='claude.ai')
    except (OSError,ValueError,subprocess.SubprocessError):return False

def version_matches(data):
    try:return subprocess.check_output([data['cli'],'--version'],text=True,timeout=10).strip()==data['cli_version']
    except (OSError,subprocess.SubprocessError):return False

def request_ceiling(data):return data['context_window_tokens']+data['max_output_tokens']

def request_cost_ceiling(data,model):
    settings=data['models'][model]
    return (data['context_window_tokens']*max(settings[k] for k in ('input','cache_read','cache_write'))+data['max_output_tokens']*settings['output'])/1e6

def bootstrap_ready(data,ops,fingerprint):
    """Manual provider acceptance under the unchanged owned migration STOP.

    This permits a charged maintenance receipt only after reviewed installation
    and all six non-provider checks. It cannot dispatch units or clear STOP.
    """
    try:
        stop=ops/'STOP';pause=json.loads((ops/'state/maintenance-pause.json').read_text())
        activation=json.loads((ops/'state/claude-code-activation.json').read_text())
        review=json.loads((ops/'state/claude-code-source-review.json').read_text())
        evidence=json.loads((ops/'state/claude-code-validation.json').read_text())
        if (not stop.is_file() or pause.get('owner')!='codex-claude-code-runtime-migration' or
            pause.get('previous_stop') is not False or pause.get('resumed_at') or
            stop.stat().st_mtime_ns!=pause.get('stop_mtime_ns')):return False
        if activation.get('installed') is not True or activation.get('enabled') is not False:return False
        if review.get('head')!=activation.get('source_head') or review.get('verdict')!='pass' or review.get('independent') is not True:return False
        if evidence.get('implementation_sha256')!=fingerprint or not all(evidence.get('checks',{}).get(k) is True
          for k in ('foundation','ops','frontend','isolation','lifecycle','resources')):return False
        if not 0<=time.time()-evidence.get('validated_at',0)<=172800:return False
        if not 0<=time.time()-evidence.get('vulnerability_snapshot_at',0)<=172800:return False
        image=subprocess.check_output(['docker','image','inspect','--format={{.Id}}',data['image']],text=True,stderr=subprocess.DEVNULL,timeout=10).strip()
        return evidence.get('image_id')==image and bool(image) and version_matches(data) and authenticated(data)
    except (OSError,ValueError,TypeError,KeyError,subprocess.SubprocessError):return False

def ready(data,ops,fingerprint,model=None):
    try:
        activation=json.loads((ops/'state/claude-code-activation.json').read_text())
        evidence=json.loads((ops/'state/claude-code-validation.json').read_text())
        if activation.get('authorized_by')!='user' or activation.get('enabled') is not True:return False
        if data['required_review_families']==1 and activation.get('review_policy')!='independent-claude-sessions':return False
        if len({control.model_family(m) for m,v in data['models'].items() if v.get('automatic')})<data['required_review_families']:return False
        if evidence.get('implementation_sha256')!=fingerprint or evidence.get('passed') is not True:return False
        required=('foundation','ops','frontend','isolation','lifecycle','resources','provider')
        if not all(evidence.get('checks',{}).get(k) is True for k in required):return False
        if not 0<=time.time()-evidence['validated_at']<=48*3600:return False
        if not 0<=time.time()-evidence.get('vulnerability_snapshot_at',0)<=48*3600:return False
        image=subprocess.check_output(['docker','image','inspect','--format={{.Id}}',data['image']],
                 text=True,stderr=subprocess.DEVNULL,timeout=10).strip()
        if not image or evidence.get('image_id')!=image:return False
        if model and evidence.get('models',{}).get(model,{}).get('tool_calls') is not True:return False
        if model and evidence.get('models',{}).get(model,{}).get('usage') is not True:return False
        return version_matches(data) and authenticated(data)
    except (OSError,ValueError,KeyError,subprocess.SubprocessError):return False

def cash_reservation(data,role,allowance,rows,state,reservations,legacy,bill):
    """Keep historical route charges and the original daily $5 quote ceiling.

    Subscription usage has an API-equivalent quote, never a fabricated invoice.
    Hold the remaining DAILY allowance, not a new unit budget. Before every
    opaque request the runner rechecks this original cash hold and token hold.
    """
    model=data['model_roles']['builder' if role=='builder' else 'reviewer']
    if allowance<request_ceiling(data):raise control.IntegrityError('Remaining unit allowance cannot cover a Claude request')
    def money(value):
        if type(value) not in (int,float) or not math.isfinite(value) or value<0:
            raise control.IntegrityError('Invalid spending observation or reservation')
        return value
    legacy_rate=max(money(m['output']) for m in legacy['models'].values() if m.get('automatic'))
    old_spent=0.0;new_spent=0.0;day_charges=0
    for row in rows:
        if not str(row.get('ts_end','')).startswith(state['day']):continue
        tokens=control.charged_tokens(row,1000000);day_charges+=tokens
        if row.get('provider')=='custom:portdan' and data['portdan_cost_check']=='user-disabled':continue
        cost=row.get('cost_estimate')
        if type(cost) not in (int,float) or not __import__('math').isfinite(cost) or cost<0 or row.get('usage_complete') is False:
            if row.get('runtime')=='claude-code':
                cost=row.get('usage',{}).get('estimated_cost_usd')
                if type(cost) not in (int,float) or not __import__('math').isfinite(cost) or cost<0:
                    raise control.IntegrityError('Claude usage cost is unknown')
            elif row.get('provider')=='custom:a6api' and bill.get('fresh') is True and bill.get('day')==state['day']:
                cost=tokens*legacy_rate/1e6
            else:raise control.IntegrityError('Historical usage cost is unknown')
        if row.get('runtime')=='claude-code':new_spent+=cost
        else:old_spent+=cost
    old_spent+=max(0,state.get('tokens_today',0)-day_charges)*legacy_rate/1e6
    if bill.get('fresh') is True and bill.get('day')==state['day']:
        old_spent=max(old_spent,money(bill['account_day_billed_usd']))
    held=sum(money(r.get('reserved_cost_estimate')) for r in reservations.values())
    available=data['estimated_daily_cost_ceiling']-old_spent-new_spent-held
    if available+1e-9<request_cost_ceiling(data,model):
        raise control.IntegrityError('Estimated daily spending allowance cannot cover a Claude request')
    return available

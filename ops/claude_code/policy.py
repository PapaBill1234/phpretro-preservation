"""Claude engine admission. Source/CLI/auth evidence is mandatory, never forged."""
import json,math,subprocess,time
from pathlib import Path
import integrity as control

def load(path):
    data=json.loads(Path(path).read_text())
    if data.get('schema')!='phpretro.claude-code-policy.v1' or data.get('runtime')!='claude-code':raise control.IntegrityError('Invalid Claude policy')
    if data.get('automatic_planning') is not False or data.get('max_builders')!=2:raise control.IntegrityError('Claude dispatch ceiling changed')
    if data.get('auth_mode')!='gateway':raise control.IntegrityError('Private gateway authentication required')
    if data.get('estimated_daily_cost_ceiling')!=5.0:raise control.IntegrityError('Original estimated daily cap changed')
    if data.get('required_review_families')!=2 or data.get('review_policy')!='temporary-two-family-user-override':
        raise control.IntegrityError('Original independent-family policy changed')
    if data.get('context_window_tokens')!=60000 or data.get('max_output_tokens')!=4096:raise control.IntegrityError('Unvalidated request bounds')
    if data.get('providers')!={'a6api':{'base_url':'https://api.a6api.com/v1'},'portdan':{'base_url':'https://portdan.com/v1'}}:
        raise control.IntegrityError('Unexpected provider endpoint')
    for settings in data['models'].values():
        if not settings.get('automatic'):continue
        if settings.get('provider_order')!=['a6api','portdan'] or settings.get('input_includes_cache') is not True:
            raise control.IntegrityError('Unvalidated provider route/accounting')
        for key in ('input','output','cache_read','cache_write'):
            if type(settings.get(key)) not in (int,float) or not math.isfinite(settings[key]) or not 0<=settings[key]<=100:
                raise control.IntegrityError('Invalid provider price quote')
    return data

def authenticated(data):
    try:
        from claude_code.gateway import credentials
        import provider_routing
        value=credentials(data['providers_file'])
        return all(bool(provider_routing.credential(value,'a6api',model)) for model,settings in data['models'].items() if settings.get('automatic'))
    except (OSError,ValueError,control.IntegrityError):return False


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
        if activation.get('review_policy')!=data['review_policy']:return False
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
        if model:
            import runtime_policy
            if not runtime_policy.verified_providers(model):return False
        return version_matches(data) and authenticated(data)
    except (OSError,ValueError,KeyError,subprocess.SubprocessError):return False

def cash_reservation(data,role,allowance,rows,state,reservations,legacy,bill):
    """Read-only estimate helper; A6API billing and receipt costs share one basis."""
    import billing
    def money(value):
        if type(value) not in (int,float) or not math.isfinite(value) or value<0:raise control.IntegrityError('Invalid spending observation')
        return value
    if allowance<=data['max_output_tokens']:raise control.IntegrityError('Remaining allowance cannot cover output')
    rate=max(money(m['output']) for m in data['models'].values() if m.get('automatic'))
    spent=0.0;charges=0;fresh=bill.get('fresh') is True and bill.get('day')==state['day']
    for row in rows:
        if row.get('record_type','run')!='run' or not str(row.get('ts_end','')).startswith(state['day']):continue
        tokens=control.charged_tokens(row,1000000);charges+=tokens
        if billing.cash_exempt(row,data):continue
        cost=row.get('cost_estimate')
        if row.get('usage_complete') is False or type(cost) not in (int,float) or not math.isfinite(cost) or cost<0:
            if row.get('provider')=='custom:a6api' and fresh:cost=tokens*rate/1e6
            else:raise control.IntegrityError('Historical usage cost is unknown')
        spent+=cost
    spent+=max(0,state.get('tokens_today',0)-charges)*rate/1e6
    if fresh:spent=max(spent,money(bill['account_day_billed_usd']))
    held=sum(money(r.get('reserved_cost_estimate')) for r in reservations.values())
    estimate=allowance*rate/1e6
    if fresh and held+estimate>money(bill['account_balance_usd']):raise control.IntegrityError('Provider balance cannot cover reservation')
    if spent+held+estimate>data['estimated_daily_cost_ceiling']:raise control.IntegrityError('Estimated daily spending allowance exhausted')
    return estimate

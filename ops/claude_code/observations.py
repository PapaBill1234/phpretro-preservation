"""Read-only route renewal from real, source-bound native receipts.

No inference, charge changes or synthetic freshness. A new successful tool
round-trip can renew its own provider/model; unrelated and tool-free runs cannot.
"""
import hashlib,json,math,re,time
from pathlib import Path
import integrity as control
import request_accounting

SCHEMA='phpretro.claude-route-observation.v1'
TTL=86400
LIMIT=1024*1024


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def usage_digest(value):
    keys=(*request_accounting.FIELDS,'runtime','usage_complete','input_includes_cache',
      'model','reported_model','provider','session_id','conservative_tokens',
      'input_tokens','output_tokens','cache_read_tokens','cache_write_tokens','total_tokens','api_calls')
    return digest({k:value[k] for k in keys if k in value})


def read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>LIMIT:raise ValueError('Invalid observation file')
    value=json.loads(path.read_text())
    if not isinstance(value,dict):raise ValueError('Invalid observation object')
    return value


def fresh(value,now=None):
    now=time.time() if now is None else now
    return type(value) in (int,float) and math.isfinite(value) and 0<=now-value<=TTL


def record(receipt_path,fingerprint,usage,context):
    """Called only after native success/export; readers also require worker rc0."""
    if (usage.get('usage_complete') is not True or usage.get('runtime')!='claude-code'
        or context.get('tool_calls',0)<1 or context.get('tool_errors')!=0):return
    receipt=read(receipt_path)
    provider=usage.get('provider','').removeprefix('custom:')
    if provider not in ('a6api','portdan'):return
    row={'schema':SCHEMA,'implementation_sha256':fingerprint,'run_id':receipt['run_id'],
      'model':usage['model'],'provider':provider,'session_id':usage['session_id'],
      'reported_model':usage['reported_model'],'checked_at':time.time(),
      'usage_sha256':usage_digest(usage),'context_sha256':digest(context)}
    control.atomic_json(receipt_path.with_suffix('.route.json'),row)


def recent(ops,fingerprint,settings,now=None):
    """Inspect bounded metadata only. Missing/partial/old proof never qualifies."""
    now=time.time() if now is None else now
    result={}
    try:
        paths=sorted((ops/'state/receipts').glob('*.route.json'),key=lambda p:p.lstat().st_mtime,reverse=True)[:256]
    except OSError:return result
    for path in paths:
        try:
            proof=read(path)
            if proof.get('schema')!=SCHEMA or proof.get('implementation_sha256')!=fingerprint:continue
            observed=proof.get('checked_at')
            if not fresh(observed,now):continue
            rid=proof.get('run_id')
            if not isinstance(rid,str) or not re.fullmatch(r'[a-f0-9-]{36}',rid):continue
            if path.name!=rid+'.route.json':continue
            receipt=read(path.with_name(rid+'.json'))
            context=read(path.with_name(rid+'.context.json'))
            usage=receipt.get('usage')
            if (receipt.get('runtime')!='claude-code' or receipt.get('status')!='complete'
                or type(receipt.get('rc')) is not int or receipt['rc']!=0
                or receipt.get('run_id')!=rid or not isinstance(usage,dict)):continue
            start,end=receipt.get('prepared_at'),receipt.get('completed_at')
            if any(type(t) not in (int,float) or not math.isfinite(t) for t in (start,end)):continue
            if not start<=observed<=end<=now:continue
            model=proof.get('model');provider=proof.get('provider')
            config=settings.get(model,{})
            if not config.get('automatic') or provider not in config.get('provider_order',[]):continue
            if (usage.get('runtime')!='claude-code' or usage.get('usage_schema')!='phpretro.claude-gateway-usage.v2'
                or usage.get('usage_complete') is not True or usage.get('model')!=model
                or receipt.get('model')!=model or usage.get('provider')!='custom:'+provider
                or usage.get('session_id')!=proof.get('session_id')
                or usage.get('reported_model')!=proof.get('reported_model')
                or proof.get('reported_model') not in [model,*config.get('reported_model_aliases',[])]):continue
            parts=('input_tokens','output_tokens','cache_read_tokens','cache_write_tokens','total_tokens')
            if (any(type(usage.get(k)) is not int or usage[k]<0 for k in parts)
                or sum(usage[k] for k in parts[:-1])!=usage['total_tokens']
                or usage.get('input_includes_cache') is not False):continue
            if (type(usage.get('api_calls')) is not int or usage['api_calls']<2
                or request_accounting.bounded_tokens(usage,usage.get('total_tokens',0))!=usage.get('total_tokens')
                or type(receipt.get('reserved_tokens')) is not int
                or not 0<usage['total_tokens']<=receipt['reserved_tokens']):continue
            if (context.get('schema')!='phpretro.context-usage.v1' or context.get('enabled_tools')!=['execute']
                or type(context.get('tool_calls')) is not int or context['tool_calls']<1
                or type(context.get('tool_errors')) is not int or context['tool_errors']!=0
                or proof.get('usage_sha256')!=usage_digest(usage) or proof.get('context_sha256')!=digest(context)):continue
            row={'tool_calls':True,'usage':True,'reported_model':proof['reported_model'],
              'checked_at':observed,'run_id':rid,'evidence_source':'completed-native-tool-receipt'}
            current=result.setdefault(provider,{}).get(model,{})
            if observed>current.get('checked_at',0):result[provider][model]=row
        except (OSError,ValueError,TypeError,KeyError,control.IntegrityError):continue
    return result


def merge(ops,fingerprint,settings,existing,now=None):
    now=time.time() if now is None else now
    result={}
    for provider,models in existing.items() if isinstance(existing,dict) else []:
        if provider not in ('a6api','portdan') or not isinstance(models,dict):continue
        for model,row in models.items():
            if (isinstance(row,dict) and row.get('tool_calls') is True and row.get('usage') is True
                and fresh(row.get('checked_at'),now)):
                result.setdefault(provider,{})[model]=dict(row)
    for provider,models in recent(ops,fingerprint,settings,now).items():
        for model,row in models.items():
            if row['checked_at']>result.get(provider,{}).get(model,{}).get('checked_at',0):
                result.setdefault(provider,{})[model]=row
    return result

"""Explicit DeepSeek counter-conflict exception; uncertainty stays accounted."""
import integrity as control,request_accounting

MODEL='deepseek-v4.1-flash'
POLICY='user-authorized-conservative'

def enabled(data,model):
    return (data.get('runtime')=='claude-code' and model==MODEL and
      data.get('models',{}).get(model,{}).get('usage_conflict_policy')==POLICY)

def operator_route(data,provider,model):
    # User approval of the recognized A6API response is separate from measured
    # tool/usage evidence. It does not admit the failed Portdan fallback.
    return provider=='a6api' and enabled(data,model)

def model_admitted(data,model,row):
    return operator_route(data,'a6api',model) or (row.get('tool_calls') is True and row.get('usage') is True)

def continuation_allowed(data,row):
    if row.get('usage_complete') is True:return True
    if not enabled(data,row.get('model')) or row.get('usage_conflict_policy')!=POLICY:return False
    try:
        admitted=control.nonnegative(row.get('usage_conflict_calls'),'admitted conflict calls')
        unknown=control.nonnegative(row.get('unknown_api_calls'),'unknown calls')
        observed=sum(control.nonnegative(row.get(k),'known usage') for k in
          ('input_tokens','output_tokens','cache_read_tokens','cache_write_tokens'))
        return (admitted>0 and admitted==unknown and row.get('runtime')=='claude-code'
          and row.get('usage_schema')=='phpretro.claude-gateway-usage.v2'
          and request_accounting.bounded_tokens(row,observed)==row.get('conservative_tokens'))
    except (control.IntegrityError,TypeError,ValueError):return False

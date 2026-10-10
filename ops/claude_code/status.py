"""Allowlisted status for the PHPRetro dashboard; never exposes auth output."""
import json,time
from pathlib import Path
from claude_code import policy

def public_summary(ops):
    root=Path(__file__).parent
    data=policy.load(root/'policy.json')
    def read(name):
        try:
            path=ops/'state'/name
            if path.is_symlink() or path.stat().st_size>65536:return {}
            value=json.loads(path.read_text());return value if isinstance(value,dict) else {}
        except (OSError,ValueError):return {}
    activation=read('claude-code-activation.json');validation=read('claude-code-validation.json')
    import runtime_policy
    current=(validation.get('implementation_sha256')==runtime_policy.fingerprint() and
      type(validation.get('validated_at')) in (int,float) and 0<=time.time()-validation['validated_at']<=172800)
    return {'runtime':'claude-code','installed':policy.version_matches(data),
      'version':data['cli_version'],'authenticated':policy.authenticated(data),
      'activated':activation.get('enabled') is True,'paused':(ops/'STOP').exists(),
      'validation_passed':current and validation.get('passed') is True,'model':data['model_roles']['builder'],
      'review_policy':data['review_policy'],'quota_status':'Unavailable; no remaining subscription quota is inferred',
      'cost_basis':'API-equivalent quotes; subscription bill unknown',
      'session_view':'/skill-doctor/#/context?view=evidence','ssh_alias':'phpretro'}

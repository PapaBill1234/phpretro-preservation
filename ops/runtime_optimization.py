"""Manual, reversible SDK efficiency settings and receipt-backed verification.

No instructions, tools, routes, budgets or active conversations are removed.
Settings are snapshotted when a new runner starts. Doctor never applies them
from a scan or a timer.
"""
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

import integrity as control
import doctor_sessions

TARGETS = {
    'compact-tool-output': {'title': 'Bound long builder tool observations', 'role': 'builder',
        'detail': 'Keep the first and last parts of observations longer than 8,192 characters. Exit codes and an explicit truncation marker remain. Full instructions and execution tools remain available.'},
    'reviewer-thinking': {'title': 'Request a direct DeepSeek review verdict', 'role': 'reviewer',
        'detail': 'Request non-thinking mode for new DeepSeek reviewers. The full diff and acceptance/security review contract remain. Provider support and review quality must be checked in subsequent sessions.'},
}


def base(home=None):
    return Path(home) / 'phpretro-ops/state/runtime-optimization' if home else Path(
        os.environ.get('PHPRETRO_OPS', Path.home() / 'phpretro-ops')) / 'state/runtime-optimization'


def identity(value):
    if not isinstance(value, str) or str(uuid.UUID(value)) != value:
        raise ValueError('Invalid optimization identity')
    return value


def read_file(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
        raise ValueError('Invalid optimization record')
    if path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise ValueError('Optimization records must be private')
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError('Invalid optimization record')
    return data


def load(home=None):
    if base(home).is_symlink():
        raise ValueError('Invalid optimization directory')
    path = base(home) / 'settings.json'
    if not path.exists() and not path.is_symlink():
        return {'revision': 'default', 'values': {k: False for k in TARGETS}, 'versions': {k: None for k in TARGETS}}
    data = read_file(path)
    identity(data.get('revision'))
    if set(data.get('values', {})) != set(TARGETS) or any(type(v) is not bool for v in data['values'].values()):
        raise ValueError('Invalid optimization settings')
    if set(data.get('versions', {})) != set(TARGETS):
        raise ValueError('Invalid optimization versions')
    for v in data['versions'].values():
        if v is not None:
            identity(v)
    return {k:data[k] for k in ('revision','values','versions')}


def snapshot(home=None):
    data = load(home)
    return {k: data[k] for k in ('revision', 'values', 'versions')}


def source_digest():
    here = Path(__file__).resolve().parent
    return hashlib.sha256(Path(__file__).read_bytes() + (here / 'openhands/runner.py').read_bytes()).hexdigest()


def compact_output(text, enabled):
    if not enabled or len(text) <= 8192:
        return text
    marker = '\n[Tool observation truncated: retained beginning and end; rerun a narrower read for omitted content.]\n'
    keep = (8192 - len(marker)) // 2
    return text[:keep] + marker + text[-keep:]


def period_bounds(period, now):
    end = dt.datetime.fromtimestamp(now, dt.timezone.utc)
    start = end.replace(hour=0, minute=0, second=0, microsecond=0)
    start = start - dt.timedelta(days=start.weekday()) if period == 'week' else start.replace(day=1)
    return start.timestamp(), now


def costs(row):
    # Subscription and Canvas invoices cannot be inferred from an SDK quote.
    if row.get('runtime')=='claude-code':
        try:
            rates=json.loads((Path(__file__).parent/'claude_code/policy.json').read_text())['models'][row['model']]
            values=[row.get(k) for k in ('input','output','cached','cache_write')]
            if not row.get('complete') or any(doctor_sessions.number(v) is None for v in values):raise ValueError()
            return {'usd':sum(v*rates[k] for v,k in zip(values,('input','output','cache_read','cache_write')))/1e6,
                    'basis':'Native Claude actual-model API-equivalent quote; not the subscription invoice'}
        except (OSError,ValueError,KeyError,TypeError):return {'usd':None,'basis':'Unknown native Claude usage/pricing'}
    if row.get('runtime') != 'openhands' or row.get('provider') != 'custom:a6api':
        return {'usd': None, 'basis': 'Unknown provider price / subscription usage'}
    try:
        import runtime_policy
        rates = runtime_policy.model_settings(row['model'])
        values = [row.get(k) for k in ('input', 'output', 'cached', 'cache_write')]
        if any(doctor_sessions.number(v) is None for v in values):
            raise ValueError()
        charge = sum(v * rates[k] for v, k in zip(values, ('input', 'output', 'cache_read', 'cache_write'))) / 1e6
        partial = not row.get('complete') or row.get('unknown_requests') not in (None,0)
        return {'usd': charge, 'basis': 'Configured A6API quote for known counters only; '+('partial usage excludes unknown calls; ' if partial else '')+'not a matched invoice or conservative ledger charge'}
    except (ValueError, KeyError, TypeError, control.IntegrityError):
        return {'usd': None, 'basis': 'Unknown or partial pricing evidence'}


def suggestions(row, settings):
    result = []
    for key, target in TARGETS.items():
        available = row.get('runtime') == 'openhands' and row.get('role') == target['role']
        if key == 'reviewer-thinking':
            available = available and row.get('model') == 'deepseek-v4.1-flash'
        reason = ('Retain required tools and instructions; this control applies to a different role/model.' if not available
                  else 'Partial history: potential benefit is unknown.' if not row.get('context_complete')
                  else 'Use subsequent sessions to verify effect; historical token savings are not measured.')
        if key == 'reviewer-thinking' and available and row.get('reasoning') is not None:
            reason = f"{row['reasoning']:,} reasoning tokens recorded. Non-thinking mode may trade review depth for a direct response; savings are unmeasured."
        result.append({'id': key, **target, 'available': available,
                       'enabled': settings['values'][key], 'reason': reason,
                       'estimated_saved_tokens': None})
    return result


def overview(home=None, report=None, period='month', now=None):
    if period not in ('week', 'month'):
        raise ValueError('Choose week or month')
    now = time.time() if now is None else now
    start, end = period_bounds(period, now)
    settings = load(home)
    report = report if report is not None else doctor_sessions.sessions(home)
    rows = []
    for row in report['sessions']:
        if row.get('started') is None or not start <= row['started'] <= end:
            continue
        rows.append({**row, 'cost': costs(row), 'suggestions': suggestions(row, settings)})
    return {'period': period, 'period_start': start, 'period_end': end,
            'settings': settings, 'sessions': rows, 'operations': operations(home),
            'evidence': 'Retained session usage and SDK context estimates. Missing counters remain unknown. Provider billing is separate and is never added to session estimates. These changes apply only to new SDK runs; savings require a matched comparison.'}


def operations(home=None):
    root = base(home)
    if root.is_symlink():
        raise ValueError('Invalid optimization directory')
    rows = []
    for path in sorted(root.glob('*.operation.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:100]:
        record = read_file(path)
        identity(record.get('id'))
        rows.append({k: record.get(k) for k in ('id', 'target', 'enabled', 'created_at', 'status', 'session_id')})
    return rows


def locked(home, action):
    root = base(home)
    if root.is_symlink() or any(p.is_symlink() for p in root.parents if p.name in ('state', 'phpretro-ops')):
        raise ValueError('Invalid optimization directory')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077:
        raise ValueError('Optimization directory must be private')
    lock_path = root / 'lock'
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        return action(root)


def preview(session_id, target, enabled, home=None, report=None):
    identity(session_id)
    if target not in TARGETS or type(enabled) is not bool:
        raise ValueError('Unknown efficiency setting')
    report = report if report is not None else doctor_sessions.sessions(home)
    row = next((r for r in report['sessions'] if r['id'] == session_id), None)
    if row is None:
        raise ValueError('No retained session for this baseline')
    def create(root):
        settings = load(home)
        item = next(s for s in suggestions(row, settings) if s['id'] == target)
        if not item['available']:
            raise ValueError('This setting does not apply to the selected runtime/role/model')
        if settings['values'][target] == enabled:
            raise ValueError('This setting already has that value')
        rid = str(uuid.uuid4())
        value = {'id': rid, 'target': target, 'enabled': enabled, 'before': settings['values'][target],
                 'revision': settings['revision'], 'session_id': session_id, 'expires_at': time.time() + 900,
                 'source_sha256': source_digest(),
                 'confirmation': hashlib.sha256(os.urandom(32)).hexdigest(), 'detail': item['detail'],
                 'estimated_saved_tokens': None, 'scope': 'New SDK runs for the stated role/model'}
        control.atomic_json(root / (rid + '.preview.json'), value)
        return value
    return locked(home, create)


def apply(preview_id, confirmation, home=None):
    identity(preview_id)
    def commit(root):
        path = root / (preview_id + '.preview.json')
        value = read_file(path)
        if value['confirmation'] != confirmation or time.time() > value['expires_at'] or value['source_sha256'] != source_digest():
            raise ValueError('Preview expired or confirmation does not match')
        settings = load(home)
        if settings['revision'] != value['revision']:
            raise ValueError('Settings changed; refresh the preview')
        target = value['target']
        operation = {'id': str(uuid.uuid4()), 'target': target, 'enabled': value['enabled'],
                     'before': settings['values'][target], 'previous_version': settings['versions'][target],
                     'created_at': time.time(), 'session_id': value['session_id'], 'status': 'prepared'}
        op_path = root / (operation['id'] + '.operation.json')
        control.atomic_json(op_path, operation)
        settings['values'][target] = value['enabled']
        settings['versions'][target] = operation['id']
        settings['revision'] = str(uuid.uuid4())
        control.atomic_json(root / 'settings.json', settings)
        operation['status'] = 'applied'
        control.atomic_json(op_path, operation)
        path.unlink()
        return operation
    return locked(home, commit)


def undo(operation_id, home=None):
    identity(operation_id)
    def restore(root):
        path = root / (operation_id + '.operation.json')
        operation = read_file(path)
        settings = load(home)
        target = operation['target']
        if settings['versions'][target] != operation_id or settings['values'][target] != operation['enabled']:
            raise ValueError('A newer change owns this setting; refresh before undoing')
        settings['values'][target] = operation['before']
        settings['versions'][target] = operation['previous_version']
        settings['revision'] = str(uuid.uuid4())
        control.atomic_json(root / 'settings.json', settings)
        operation.update(status='restored', restored_at=time.time())
        control.atomic_json(path, operation)
        return operation
    return locked(home, restore)


def verify(operation_id, home=None, report=None):
    identity(operation_id)
    operation = read_file(base(home) / (operation_id + '.operation.json'))
    settings = load(home)
    target = operation['target']
    if operation['status'] == 'restored':
        return {'status': 'restored', 'reason': 'The prior setting was restored. Existing runs were not changed.', 'measured_savings': None}
    if settings['versions'][target] != operation_id:
        return {'status': 'superseded', 'reason': 'A newer setting replaced this operation.', 'measured_savings': None}
    report = report if report is not None else doctor_sessions.sessions(home)
    for row in report['sessions']:
        profile = row.get('optimization') or {}
        if row.get('started', 0) and row['started'] > operation['created_at'] and profile.get('versions', {}).get(target) == operation_id:
            relevant = next(s for s in suggestions(row, settings) if s['id'] == target)['available']
            if not relevant or row.get('status') == 'running':
                continue
            if profile.get('values',{}).get(target) is not operation['enabled'] or not (doctor_sessions.number(row.get('requests')) or 0)>0:
                return {'status':'effect-unverified','session_id':row['id'],'reason':'Matching version alone is insufficient: the setting value and an actual provider request must be recorded.','measured_savings':None}
            if not row.get('context_complete') or not row.get('complete') or row.get('rc') != 0:
                return {'status': 'observed-partial', 'session_id': row['id'], 'reason': 'The setting was snapshotted in a new run, but its result or usage is incomplete. Effect and savings remain unverified.', 'measured_savings': None}
            detail = 'The setting was observed in a new successful SDK run. Review task quality separately.'
            if target == 'reviewer-thinking':
                explicit = row.get('reported_reasoning_tokens')
                if operation['enabled'] and explicit != 0:
                    return {'status': 'effect-unverified', 'session_id': row['id'], 'reason': 'The request used the setting, but the provider did not explicitly report zero reasoning tokens.', 'measured_savings': None}
            return {'status': 'observed', 'session_id': row['id'], 'reason': detail, 'measured_savings': None}
    return {'status': 'pending', 'reason': 'Waiting for a new completed session for this role/model. This check does not launch inference.', 'measured_savings': None}


def dispatch(body, home=None, report=None):
    if not isinstance(body, dict):
        raise ValueError('Invalid optimization request')
    action = body.get('action')
    if action == 'overview':
        return overview(home, report, body.get('period', 'month'))
    if action == 'preview':
        return preview(body.get('session_id'), body.get('target'), body.get('enabled'), home, report)
    if action == 'apply':
        return apply(body.get('preview_id'), body.get('confirmation'), home)
    if action == 'verify':
        return verify(body.get('operation_id'), home, report)
    if action == 'undo':
        if body.get('confirmation') != body.get('operation_id'):
            raise ValueError('Undo confirmation does not match')
        return undo(body.get('operation_id'), home)
    raise ValueError('Unknown optimization action')

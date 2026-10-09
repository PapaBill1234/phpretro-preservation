"""Read-only A6API console collection. Credentials and raw account data stay private."""
from __future__ import annotations
import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import time
import urllib.parse
import integrity as control

AUTH = Path.home() / 'phpretro-openhands/secrets/a6api-billing.json'
OPS = Path(os.environ.get('PHPRETRO_OPS', Path.home() / 'phpretro-ops'))
SNAPSHOT = 'a6api-billing.json'


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('invalid provider billing number')
    return value


def request(path, auth=None):
    if path.split('?')[0] not in ('/api/status', '/api/user/self', '/api/log/self', '/api/log/self/stat'):
        raise ValueError('billing endpoint outside read-only allowlist')
    config = ''
    if auth:
        token = auth['access_token']
        if not isinstance(token, str) or not token or any(c.isspace() for c in token):
            raise ValueError('invalid billing credential')
        config = 'header = ' + json.dumps('Authorization: Bearer ' + token) + '\n'
        config += 'header = ' + json.dumps('New-API-User: ' + str(int(auth['user_id']))) + '\n'
    # No redirects, insecure TLS, shell, command-line credentials or response logs.
    result = subprocess.run(['curl', '-4', '--silent', '--fail', '--connect-timeout', '10',
                             '--max-time', '20', '--retry', '2', '--retry-all-errors',
                             '--max-filesize', '2097152', '--config', '-', 'https://a6api.com' + path],
                            input=config, text=True, capture_output=True, timeout=90)
    if result.returncode:
        raise ValueError('billing HTTP request failed (curl code ' + str(result.returncode) + ')')
    payload = json.loads(result.stdout)
    if payload.get('success') is not True or not isinstance(payload.get('data'), dict):
        raise ValueError('billing API rejected request')
    return payload['data']


def read_auth(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('billing credentials require owner-only regular file')
    if info.st_size > 4096:
        raise ValueError('billing credential file too large')
    data = json.loads(path.read_text())
    if type(data.get('user_id')) is not int or data['user_id'] <= 0:
        raise ValueError('invalid billing account')
    return data


def normalize(row, factor):
    other = row.get('other') or {}
    if isinstance(other, str):
        other = json.loads(other)
    prompt = number(row['prompt_tokens'])
    cache = number(other.get('cache_tokens', 0))
    if cache > prompt:
        raise ValueError('cache tokens exceed inclusive prompt tokens')
    return {'request_id': str(row.get('request_id') or '')[:160],
            'created_at': number(row['created_at']), 'model': str(row['model_name'])[:100],
            'input_tokens_including_cache': prompt, 'cache_read_tokens': cache,
            'output_tokens': number(row['completion_tokens']),
            'billed_usd': number(row['quota']) / factor}


def collect(auth, now=None, fetch=request):
    now = int(time.time() if now is None else now)
    start = now // 86400 * 86400
    status = fetch('/api/status')
    factor = number(status['quota_per_unit'])
    if factor == 0 or status.get('quota_display_type') != 'USD':
        raise ValueError('billing currency is not verified USD')
    user = fetch('/api/user/self', auth)
    if user.get('id') != auth['user_id']:
        raise ValueError('billing account mismatch')
    # Whole-account total is conservative for pipeline admission and includes UI use.
    query = {'type': 2, 'start_timestamp': start, 'end_timestamp': now}
    stats = fetch('/api/log/self/stat?' + urllib.parse.urlencode(query), auth)
    rows, account_rows, seen = [], [], set()
    total = None
    for page in range(1, 21):
        data = fetch('/api/log/self?' + urllib.parse.urlencode({**query, 'p': page, 'page_size': 100}), auth)
        current_total = number(data['total'])
        if total is None:
            total = current_total
        if total != current_total or data.get('page') != page or data.get('page_size') != 100:
            raise ValueError('billing pagination changed during collection')
        for raw in data['items']:
            if raw.get('type') != 2:
                raise ValueError('billing filter mismatch')
            row = normalize(raw, factor)
            if not start <= row['created_at'] <= now or not row['request_id'] or row['request_id'] in seen:
                raise ValueError('billing window or request identity mismatch')
            seen.add(row['request_id']); account_rows.append(row)
            if raw.get('token_name') == 'coding':rows.append(row)
        if len(account_rows) >= total:
            break
        if not data['items']:
            raise ValueError('billing pagination incomplete')
    if len(account_rows) != total:
        raise ValueError('billing collection page bound exceeded')
    return {'schema': 'phpretro.a6api-billing.v1', 'collected_at': time.time(),
            'window_start': start, 'window_end': now, 'day': dt.datetime.fromtimestamp(now, dt.timezone.utc).date().isoformat(),
            'currency': 'USD', 'quota_per_usd': factor, 'account_balance_usd': number(user['quota']) / factor,
            'account_day_billed_usd': number(stats['quota']) / factor,
            'coding_day_billed_usd': sum(r['billed_usd'] for r in rows), 'coding_requests': len(rows),
            'rows': rows, 'account_rows': account_rows, 'account_rows_scope': 'All account inference keys, current UTC day, maximum 2000 calls',
            'source': 'https://a6api.com/api/log/self',
            'usage_complete': False, 'note': 'Provider billing observation; does not settle missing SDK responses.'}


def summary(ops=OPS, now=None):
    now = time.time() if now is None else now
    try:
        path = Path(ops) / 'state' / SNAPSHOT
        if path.stat().st_size > 2097152:
            raise ValueError('snapshot too large')
        data = json.loads(path.read_text())
        if data.get('schema') != 'phpretro.a6api-billing.v1' or data.get('currency') != 'USD':
            raise ValueError('invalid snapshot')
        result = {k: data.get(k) for k in ('collected_at', 'day', 'account_balance_usd', 'account_day_billed_usd',
                                          'coding_day_billed_usd', 'coding_requests', 'note')}
        fresh = 0 <= now - number(data['collected_at']) <= 300
        result['fresh'] = fresh and not (Path(ops) / 'state/a6api-billing-error.json').exists()
        result['available'] = True
        return result
    except (OSError, ValueError, TypeError, KeyError):
        return {'available': False, 'fresh': False}


def cash_exempt(row, policy):
    return row.get('provider') == 'custom:portdan' and policy.get('portdan_cost_check') == 'user-disabled'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--auth', type=Path, default=AUTH)
    args = ap.parse_args()
    os.umask(0o077)
    try:
        data = collect(read_auth(args.auth))
        control.atomic_json(OPS / 'state' / SNAPSHOT, data)
        (OPS / 'state/a6api-billing-error.json').unlink(missing_ok=True)
        print(json.dumps(summary()))
        return 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        # Keep last good snapshot but make freshness fail closed; never log credentials/raw payloads.
        control.atomic_json(OPS / 'state/a6api-billing-error.json', {'at': time.time(), 'error': 'Collection failed; check authentication/connectivity or API schema.'})
        print('A6API billing collection failed; previous snapshot retained.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

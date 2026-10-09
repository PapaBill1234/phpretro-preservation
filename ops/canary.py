"""Explicit, expiring operator authorization for one bounded coding canary."""
import json
import os
from pathlib import Path
import time
import integrity as control

OPS = Path(os.environ.get('PHPRETRO_OPS', Path.home() / 'phpretro-ops'))


def load():
    path = OPS / 'state/canary-admission.json'
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    if (data.get('schema') != 'phpretro.canary.v1' or data.get('authorized_by') != 'user'
            or set(data.get('units', {})) != {'F39b', 'F61'}
            or not 0 < data.get('per_role_tokens', 0) <= 600000
            or not 0 < data.get('per_unit_tokens', 0) <= 1800000
            or not 0 < data.get('expires_at', 0) - data.get('authorized_at', 0) <= 21600):
        raise control.IntegrityError('invalid canary authorization')
    return data


def allowed(unit=None):
    data = load()
    return data is None or (time.time() < data['expires_at'] and
                           (unit is None or unit.get('id') in data['units']))


def allowance(unit, role, amount):
    data = load()
    if data is None:
        return amount
    if not allowed(unit) or not unit:
        return 0
    baseline = data['units'][unit['id']]
    if role == 'builder' and unit.get('attempts', 0) >= baseline['attempts'] + 1:
        return 0
    remaining = data['per_unit_tokens'] - max(0, unit.get('tokens', 0) - baseline['tokens'])
    return max(0, min(amount, data['per_role_tokens'], remaining))


def unknown_estimate(row, rate):
    """None means blocked; zero means explicitly excluded, never a billed zero."""
    data = load()
    if data is None or not allowed():
        return None
    provider = row.get('provider', '')
    if provider == 'custom:portdan' and data.get('portdan_spend_override') is True:
        return 0.0
    if provider == 'custom:a6api' and row.get('run_id') in data.get('historical_a6api_runs', []):
        return control.charged_tokens(row, 1000000) * rate / 1e6
    return None


def operator_route(provider, model):
    data = load()
    return bool(data and allowed() and provider == 'a6api' and model == 'gpt-6.1-sol'
                and data.get('a6api_sol_operator_confirmation') is True)


def finished(roadmap):
    data = load()
    if not data:
        return False
    return not allowed() or all(
        roadmap[uid].get('status') in ('merged', 'parked') or
        (roadmap[uid].get('status') == 'todo' and
         roadmap[uid].get('attempts', 0) >= baseline['attempts'] + 1)
        for uid, baseline in data['units'].items())

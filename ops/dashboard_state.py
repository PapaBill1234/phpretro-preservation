"""Typed dashboard projections shared with controller accounting; no prompts."""
from __future__ import annotations
import json
from pathlib import Path
import integrity
import telemetry
import worker
import re
import math


def live_workers(ops, units, now):
    result = []
    for path in sorted((Path(ops) / "state" / "receipts").glob("*.json")):
        if path.name.count(".") != 1 or path.stat().st_size > 65536:
            continue
        try:
            rec = json.loads(path.read_text())
            if rec.get("runtime") != "openhands" or rec.get("status") != "running":
                continue
            if not worker.alive(rec.get("worker_pid"), rec.get("worker_identity")):
                continue
            uid = rec.get("unit", "")
            unit = units.get(uid, {})
            usage = rec.get("usage") or {}
            result.append({"id": uid, "title": unit.get("title"), "model": rec.get("model"),
                           "role": rec.get("role"), "age": max(0, now - rec.get("prepared_at", now)),
                           "attempts": rec.get("attempt"), "tokens": usage.get("total_tokens"),
                           "pid": rec["worker_pid"], "run_id": rec["run_id"],
                           "api_calls": usage.get("api_calls"), "provider": usage.get("provider"),
                           "usage_complete": usage.get("usage_complete") is True,
                           "updated_at": path.stat().st_mtime,
                           "hint": "OpenHands " + str(rec.get("role")) + "; durable worker receipt active"})
        except (OSError, ValueError, TypeError, KeyError):
            continue
    return result


def builder_activity(ops, units, rows, events, live, stopped, now):
    """Allowlisted activity metadata only; no free-form logs or conversation content."""
    def count(value):
        return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None
    def label(value, allowed):
        return value if value in allowed else 'unknown'
    models = {'gpt-6.1-sol', 'gpt-6-luna', 'deepseek-v4.1-flash'}
    providers = {'custom:a6api', 'custom:portdan', 'mixed:a6api-portdan'}
    outcomes = {'success', 'passed', 'failed', 'gate_failed', 'timeout', 'timed_out', 'no_change',
                'no-change', 'provider_error', 'other', 'interrupted', 'completed', 'merged'}
    recent = []
    for row in reversed(rows):
        uid = row.get('unit')
        if uid not in units or row.get('record_type', 'run') != 'run' or row.get('role') not in ('builder', 'reviewer', 'review', 'audit'):
            continue
        ended = str(row.get('ts_end', ''))
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T[0-9:.+Z-]+', ended):
            continue
        usage = row.get('usage') if isinstance(row.get('usage'), dict) else {}
        observed = count(usage.get('total_tokens', row.get('total_tokens')))
        outcome = label(row.get('outcome'), outcomes)
        if outcome == 'other' and type(row.get('rc')) is int and row['rc'] == 0: outcome = 'completed'
        recent.append({'unit': uid, 'role': row['role'], 'model': label(row.get('model'), models),
                       'provider': label(row.get('provider'), providers),
                       'outcome': outcome, 'ended_at': ended,
                       'observed_tokens': observed,
                       'charged_tokens': integrity.charged_tokens(row, 1000000),
                       'api_calls': count(row.get('api_calls')),
                       'usage_complete': row.get('usage_complete') is True})
        if len(recent) == 20: break
    safe_live = [{k: w.get(k) for k in ('id', 'title', 'role', 'age', 'attempts', 'tokens', 'api_calls', 'updated_at', 'usage_complete')}
                 | {'model': label(w.get('model'), models), 'provider': label(w.get('provider'), providers)}
                 for w in live if w.get('id') in units]
    labels = {'dispatch': 'Worker dispatched', 'started': 'Worker started', 'merged': 'Pull request merged',
              'dispatched': 'Worker dispatched', 'built': 'Build completed', 'gate_pass': 'Checks passed',
              'gate_fail': 'Checks failed', 'review_verdict': 'Independent review recorded',
              'gate_failed': 'Checks failed', 'failed': 'Run failed', 'timeout': 'Run timed out',
              'parked': 'Unit parked', 'pr_opened': 'Pull request opened', 'review_passed': 'Review passed',
              'review_failed': 'Review failed', 'canary_started': 'Bounded run started',
              'budget_denied': 'Budget admission denied', 'provider_error': 'Provider request failed'}
    timeline = [{'unit': e['unit'], 'label': labels[e['kind']], 'kind': e['kind'], 'at': e['ts']}
                for e in events if e.get('unit') in units and e.get('kind') in labels
                and re.fullmatch(r'\d{4}-\d{2}-\d{2}T[0-9:.+Z-]+', str(e.get('ts', '')))][-30:][::-1]
    bounded = []
    try:
        path = Path(ops) / 'state/canary-admission.json'
        if path.stat().st_size > 65536: raise ValueError('scope too large')
        scope = json.loads(path.read_text())
        for uid, baseline in scope.get('units', {}).items():
            if uid not in units: continue
            # Ledger charges, not stale roadmap counters, determine allowance.
            charges = sum(integrity.charged_tokens(r, 1000000) for r in rows
                          if r.get('unit') == uid and r.get('record_type', 'run') == 'run')
            used = max(count(units[uid].get('tokens')) or 0, charges)
            remaining = max(0, float(scope['per_unit_tokens']) - max(0, used - float(baseline['tokens'])))
            bounded.append({'unit': uid, 'remaining_tokens': remaining,
                            'expired': now >= float(scope['expires_at']), 'status': units[uid].get('status')})
    except (OSError, ValueError, TypeError, KeyError): pass
    exhausted = [b['unit'] for b in bounded if b['remaining_tokens'] <= 0 and b['status'] not in ('merged', 'parked')]
    reason = ('Bounded review allowance exhausted for ' + ', '.join(exhausted) + '. Previous charges are preserved.') if exhausted else (
        'Coding is intentionally paused. No new workers will start.' if stopped else
        'Workers are running.' if safe_live else 'No active workers. Waiting for eligible work or the next dispatch cycle.')
    return {'mode': 'paused' if stopped else 'running' if safe_live else 'idle', 'reason': reason,
            'live': safe_live, 'recent': recent, 'timeline': timeline, 'bounded': bounded, 'updated_at': now}


def run_cost(record, prices=None):
    if record.get("usage_complete") is False:
        return None
    if "cost_estimate" in record:
        return telemetry._finite_nonnegative(record["cost_estimate"])
    usage = dict(record.get("usage") or record)
    usage.setdefault("model", record.get("model"))
    usage.setdefault("cache_read_tokens", record.get("cached_tokens", 0))
    return telemetry.estimate_cost(usage, prices)


def planning_queue(ops):
    result = []
    for path in sorted((Path(ops) / "state" / "planning-needed").glob("*.json"))[:100]:
        try:
            if path.stat().st_size > 65536:
                continue
            record = json.loads(path.read_text())
            if record.get("status") != "awaiting-subscription-brief":
                continue
            result.append({k: record.get(k) for k in ("unit", "reason", "status", "attempts", "tokens", "paths", "depends_on")})
        except (OSError, ValueError):
            continue
    return result

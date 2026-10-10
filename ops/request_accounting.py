"""Typed accounting for the trusted runner's bounded inference requests."""
import integrity as control

SCHEMA = "phpretro.bounded-usage.v3"
# The trusted runner already rejects contexts above 60,000 tokens. Match the
# reservation to that enforced bound; retain v1 charges for historical receipts.
MAX_INPUT = 60000
MAX_OUTPUT = 4096
CALL_CEILING = MAX_INPUT + MAX_OUTPUT
CEILINGS = {"phpretro.bounded-usage.v1": 69632, "phpretro.bounded-usage.v2": CALL_CEILING, SCHEMA: CALL_CEILING}
FIELDS = ("usage_schema", "request_token_ceiling", "completed_api_calls", "unknown_api_calls", "usage_known_calls", "unknown_request_ceilings")


def next_ceiling(remaining):
    remaining = control.nonnegative(remaining, "remaining request allowance")
    return min(CALL_CEILING, remaining) if remaining > MAX_OUTPUT else 0


def bounded_tokens(data, observed):
    """Legacy/missing evidence retains the old pessimistic floor.

    This is an estimate for unknown provider usage, never a complete bill.
    Tools cannot access these trusted-host checkpoints.
    """
    schema = data.get("usage_schema")
    if data.get('runtime') == 'claude-code':
        if schema=='phpretro.claude-gateway-usage.v2':
            ceiling=control.nonnegative(data.get('request_token_ceiling'),'gateway ceiling')
            started=control.nonnegative(data.get('api_calls'),'gateway calls')
            known=control.nonnegative(data.get('completed_api_calls'),'gateway known calls')
            unknown=control.nonnegative(data.get('unknown_api_calls'),'gateway unknown calls')
            pending=data.get('unknown_request_ceilings')
            if not isinstance(pending,list) or len(pending)!=unknown:raise control.IntegrityError('Missing physical request holds')
            if any(type(v) is not int or not MAX_OUTPUT<v<=CALL_CEILING for v in pending):raise control.IntegrityError('Invalid physical request hold')
            estimate=control.nonnegative(data.get('conservative_tokens'),'gateway estimate')
            if (ceiling!=CALL_CEILING or started!=known+unknown or control.nonnegative(data.get('usage_known_calls'),'gateway usage calls')!=known
                or estimate<observed+sum(pending) or unknown==0 and estimate!=observed
                or data.get('usage_complete') is True and unknown!=0):raise control.IntegrityError('Gateway accounting mismatch')
            return estimate
        if schema != 'phpretro.claude-cli-usage.v1':return None
        ceiling=control.nonnegative(data.get('request_token_ceiling'),'Claude ceiling')
        started=control.nonnegative(data.get('api_calls'),'Claude started calls')
        known=control.nonnegative(data.get('completed_api_calls'),'Claude completed calls')
        unknown=control.nonnegative(data.get('unknown_api_calls'),'Claude unknown calls')
        estimate=control.nonnegative(data.get('conservative_tokens'),'Claude estimate')
        if (ceiling != 1004096 or started != known+unknown or
            control.nonnegative(data.get('usage_known_calls'),'Claude known calls') != known or
            estimate < max(observed,unknown*ceiling) or
            unknown==0 and estimate!=observed or
            data.get('usage_complete') is True and unknown!=0):
            raise control.IntegrityError('Claude invocation accounting mismatch')
        return estimate
    expected = CEILINGS.get(schema) if isinstance(schema, str) else None
    if expected is None or data.get("runtime") != "openhands":
        return None
    ceiling = control.nonnegative(data.get("request_token_ceiling"), "request ceiling")
    started = control.nonnegative(data.get("api_calls"), "started calls")
    completed = control.nonnegative(data.get("completed_api_calls"), "completed calls")
    unknown = control.nonnegative(data.get("unknown_api_calls"), "unknown calls")
    known = control.nonnegative(data.get("usage_known_calls"), "known calls")
    estimate = control.nonnegative(data.get("conservative_tokens"), "bounded estimate")
    unknown_charge = unknown * ceiling
    if schema == SCHEMA:
        pending = data.get("unknown_request_ceilings")
        if not isinstance(pending, list) or len(pending) != unknown:
            raise control.IntegrityError("missing bounded request ceilings")
        for value in pending:
            amount = control.nonnegative(value, "unknown request ceiling")
            if not MAX_OUTPUT < amount <= CALL_CEILING:
                raise control.IntegrityError("invalid bounded request ceiling")
        unknown_charge = sum(pending)
    if (ceiling != expected or started != completed + unknown or known != completed
            or (completed > 0 and observed <= 0) or estimate != observed + unknown_charge
            or (data.get("usage_complete") is True and unknown != 0)):
        raise control.IntegrityError("bounded request accounting mismatch")
    return estimate

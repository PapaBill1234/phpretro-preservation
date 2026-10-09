"""Typed accounting for the trusted runner's bounded inference requests."""
import integrity as control

SCHEMA = "phpretro.bounded-usage.v2"
# The trusted runner already rejects contexts above 60,000 tokens. Match the
# reservation to that enforced bound; retain v1 charges for historical receipts.
MAX_INPUT = 60000
MAX_OUTPUT = 4096
CALL_CEILING = MAX_INPUT + MAX_OUTPUT
CEILINGS = {"phpretro.bounded-usage.v1": 69632, SCHEMA: CALL_CEILING}
FIELDS = ("usage_schema", "request_token_ceiling", "completed_api_calls", "unknown_api_calls", "usage_known_calls")


def bounded_tokens(data, observed):
    """Legacy/missing evidence retains the old pessimistic floor.

    This is an estimate for unknown provider usage, never a complete bill.
    Tools cannot access these trusted-host checkpoints.
    """
    schema = data.get("usage_schema")
    expected = CEILINGS.get(schema) if isinstance(schema, str) else None
    if expected is None or data.get("runtime") != "openhands":
        return None
    ceiling = control.nonnegative(data.get("request_token_ceiling"), "request ceiling")
    started = control.nonnegative(data.get("api_calls"), "started calls")
    completed = control.nonnegative(data.get("completed_api_calls"), "completed calls")
    unknown = control.nonnegative(data.get("unknown_api_calls"), "unknown calls")
    known = control.nonnegative(data.get("usage_known_calls"), "known calls")
    estimate = control.nonnegative(data.get("conservative_tokens"), "bounded estimate")
    if (ceiling != expected or started != completed + unknown or known != completed
            or (completed > 0 and observed <= 0) or estimate != observed + unknown * ceiling
            or (data.get("usage_complete") is True and unknown != 0)):
        raise control.IntegrityError("bounded request accounting mismatch")
    return estimate

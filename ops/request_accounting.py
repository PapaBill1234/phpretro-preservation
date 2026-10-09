"""Typed accounting for the trusted runner's bounded inference requests."""
import integrity as control

SCHEMA = "phpretro.bounded-usage.v1"
MAX_INPUT = 65536
MAX_OUTPUT = 4096
CALL_CEILING = MAX_INPUT + MAX_OUTPUT
FIELDS = ("usage_schema", "request_token_ceiling", "completed_api_calls", "unknown_api_calls", "usage_known_calls")


def bounded_tokens(data, observed):
    """Legacy/missing evidence retains the old pessimistic floor.

    This is an estimate for unknown provider usage, never a complete bill.
    Tools cannot access these trusted-host checkpoints.
    """
    if data.get("usage_schema") != SCHEMA or data.get("runtime") != "openhands":
        return None
    ceiling = control.nonnegative(data.get("request_token_ceiling"), "request ceiling")
    started = control.nonnegative(data.get("api_calls"), "started calls")
    completed = control.nonnegative(data.get("completed_api_calls"), "completed calls")
    unknown = control.nonnegative(data.get("unknown_api_calls"), "unknown calls")
    known = control.nonnegative(data.get("usage_known_calls"), "known calls")
    estimate = control.nonnegative(data.get("conservative_tokens"), "bounded estimate")
    if (ceiling != CALL_CEILING or started != completed + unknown or known != completed
            or (completed > 0 and observed <= 0) or estimate != observed + unknown * ceiling):
        raise control.IntegrityError("bounded request accounting mismatch")
    return estimate

"""Explicit provider failover; no model substitution or implicit retries."""
from __future__ import annotations
import integrity as control


def credential(credentials, provider, model):
    nested = credentials.get(provider, {})
    if provider == "a6api":
        key = credentials.get("a6api_api_key") or credentials.get("A6API_API_KEY")
        key = key or (nested.get("api_key") or nested.get("key") if isinstance(nested, dict) else nested)
    elif provider == "portdan":
        key = nested.get("deepseek" if model.startswith("deepseek-") else "openai") if isinstance(nested, dict) else None
    else:
        raise control.IntegrityError("provider outside configured routes")
    if not isinstance(key, str) or not key:
        raise control.IntegrityError("configured provider credential unavailable")
    return key


def retryable(exc):
    if isinstance(exc, (control.IntegrityError, InterruptedError)):
        return False
    status = getattr(exc, "status_code", None)
    return (isinstance(status, int) and not isinstance(status, bool)
            and (status in (401, 403, 404, 408, 429) or 500 <= status <= 599)) or type(exc).__name__ in (
                "Timeout", "TimeoutError", "APITimeoutError", "APIConnectionError", "ConnectionError")


def call(routes, invoke, failed):
    """A route is attempted once per session; failed routes stay suppressed."""
    last = None
    for provider in routes:
        if provider in failed:
            continue
        try:
            return invoke(provider)
        except Exception as exc:
            if not retryable(exc):
                raise
            failed.add(provider)
            last = exc
    if last is not None:
        raise last
    raise control.IntegrityError("no verified provider route remains")

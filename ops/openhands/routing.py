"""Explicit provider failover; no model substitution or implicit retries."""
from __future__ import annotations
import integrity as control
import time

RECONNECT_DELAYS = (5, 15)


def transient(exc):
    """Authentication/model errors can fail over, but cannot reconnect."""
    return retryable(exc) and getattr(exc, "status_code", None) not in (401, 403, 404)


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


def call(routes, invoke, failed, *, wait=time.sleep):
    """Retry the same request, never a completed tool turn or conversation.

    Successful fallback remains preferred for this session. Only when all
    routes fail do transient routes reconnect, in original primary-first order.
    Permanent failures stay suppressed. The caller owns budget/cancellation.
    """
    last = None
    reconnect = set()
    for round_number in range(len(RECONNECT_DELAYS) + 1):
        for provider in routes:
            if provider in failed:
                continue
            try:
                return invoke(provider)
            except Exception as exc:
                if not retryable(exc):
                    raise
                failed.add(provider)
                if transient(exc):
                    reconnect.add(provider)
                last = exc
        if round_number == len(RECONNECT_DELAYS) or not reconnect:
            break
        wait(RECONNECT_DELAYS[round_number])
        failed.difference_update(reconnect)
        reconnect.clear()
    if last is not None:
        raise last
    raise control.IntegrityError("no verified provider route remains")

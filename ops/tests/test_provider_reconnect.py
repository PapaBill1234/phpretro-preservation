"""Offline recovery, cancellation and trusted checkpoint accounting."""
import unittest
from unittest.mock import patch
from harness import tmpdir
import integrity as control
import orchestrator as o
import worker
import request_accounting as requests
import sys
from pathlib import Path
sys.path.insert(0, str(Path(o.__file__).parent / "openhands"))
import routing


class ReconnectTests(unittest.TestCase):
    def test_previous_transient_primary_can_recover_on_a_later_turn(self):
        failed, recoverable, calls = set(), set(), []
        def invoke(provider):
            calls.append(provider)
            if len(calls) in (4, 6): return "continued"
            raise TimeoutError()
        for _ in range(2):
            self.assertEqual(routing.call(["a6api", "portdan"], invoke, failed,
                recoverable=recoverable, wait=lambda _: None), "continued")
        self.assertEqual(calls, ["a6api", "portdan", "a6api", "portdan", "portdan", "a6api"])

    def test_single_route_reconnects_same_request_after_backoff(self):
        attempts, waits = [], []
        def invoke(provider):
            attempts.append(provider)
            if len(attempts) < 3:
                raise TimeoutError()
            return "continued"
        self.assertEqual(routing.call(["a6api"], invoke, set(), wait=waits.append), "continued")
        self.assertEqual(attempts, ["a6api"] * 3)
        self.assertEqual(waits, [5, 15])

    def test_permanent_primary_stays_disabled_during_fallback_reconnect(self):
        class AuthError(Exception): status_code = 401
        calls = []
        def invoke(provider):
            calls.append(provider)
            raise AuthError() if provider == "a6api" else TimeoutError()
        with self.assertRaises(TimeoutError):
            routing.call(["a6api", "portdan"], invoke, set(), wait=lambda _: None)
        self.assertEqual(calls, ["a6api", "portdan", "portdan", "portdan"])

    def test_cancellation_during_backoff_prevents_reconnect(self):
        calls = []
        def invoke(provider):
            calls.append(provider)
            raise TimeoutError()
        def cancel(_): raise InterruptedError()
        with self.assertRaises(InterruptedError): routing.call(["a6api"], invoke, set(), wait=cancel)
        self.assertEqual(calls, ["a6api"])

    def test_retry_still_obeys_next_call_budget_denial(self):
        calls = []
        def invoke(provider):
            calls.append(provider)
            if len(calls) == 1: raise TimeoutError()
            raise control.IntegrityError("allowance exhausted")
        with self.assertRaises(control.IntegrityError):
            routing.call(["a6api"], invoke, set(), wait=lambda _: None)
        self.assertEqual(len(calls), 2)


class BoundedUsageTests(unittest.TestCase):
    def usage(self):
        return {"runtime":"openhands", "usage_schema":requests.SCHEMA,
                "request_token_ceiling":requests.CALL_CEILING,
                "api_calls":3, "completed_api_calls":2, "unknown_api_calls":1,
                "usage_known_calls":2, "total_tokens":240, "usage_complete":False,
                "unknown_request_ceilings":[requests.CALL_CEILING],
                "conservative_tokens":240 + requests.CALL_CEILING}

    def test_partial_checkpoint_roundtrip_retains_unknown_charge(self):
        root = tmpdir("bounded-usage-")
        path = root / "usage.json"
        control.atomic_json(path, self.usage())
        result = worker.usage_snapshot(path, root / "unused.db", "", "openhands")
        self.assertFalse(result["usage_complete"])
        self.assertEqual(o.accounted_usage(result)["accounted_tokens"], 240 + requests.CALL_CEILING)

    def test_historical_v1_charge_is_not_reduced_by_new_ceiling(self):
        data = self.usage()
        data.update(usage_schema='phpretro.bounded-usage.v1', request_token_ceiling=69632,
                    conservative_tokens=69872)
        self.assertEqual(o.accounted_usage(data)['accounted_tokens'], 69872)
        data['request_token_ceiling'] = requests.CALL_CEILING
        with self.assertRaises(control.IntegrityError): o.accounted_usage(data)

    def test_new_ceiling_matches_existing_enforced_context_limit(self):
        self.assertEqual(requests.MAX_INPUT, 60000)
        self.assertEqual(requests.CALL_CEILING, 64096)
        self.assertLess(requests.CALL_CEILING, 69455)

    def test_small_remaining_allowance_still_admits_a_bounded_request(self):
        self.assertEqual(requests.next_ceiling(69455),64096)
        self.assertEqual(requests.next_ceiling(59667),59667)
        self.assertEqual(requests.next_ceiling(4096),0)
        data=self.usage();data.update(unknown_request_ceilings=[59667],conservative_tokens=59907)
        self.assertEqual(o.accounted_usage(data)['accounted_tokens'],59907)
        root=tmpdir('narrowed-usage-');path=root/'usage.json';control.atomic_json(path,data)
        recorded=worker.usage_snapshot(path,root/'unused.db','','openhands')
        self.assertEqual(o.accounted_usage(recorded)['accounted_tokens'],59907)
        data['usage_schema']='phpretro.bounded-usage.v2'
        with self.assertRaises(control.IntegrityError):o.accounted_usage(data)

    def test_variable_unknown_ceilings_cannot_be_tampered_with(self):
        for value in (None,[],[True],[4096],[64097],[64096,1]):
            data=self.usage();data['unknown_request_ceilings']=value
            with self.subTest(value=value),self.assertRaises(control.IntegrityError):o.accounted_usage(data)

    def test_legacy_unknown_usage_keeps_million_token_floor(self):
        data = self.usage(); data.pop("usage_schema")
        self.assertEqual(o.accounted_usage(data)["accounted_tokens"], o.TIMEOUT_FALLBACK_TOKENS)

    def test_malformed_envelope_cannot_lower_charge(self):
        for key, value in (("unknown_api_calls",0), ("request_token_ceiling",1),
                           ("completed_api_calls",True), ("usage_known_calls",1),
                           ("conservative_tokens",240), ("total_tokens",0), ("usage_complete",True)):
            data = self.usage(); data[key] = value
            with self.subTest(key=key), self.assertRaises(control.IntegrityError): o.accounted_usage(data)

    def test_worker_invalid_envelope_falls_back_to_unknown(self):
        root = tmpdir("invalid-envelope-"); path = root / "usage.json"
        data = self.usage(); data["unknown_api_calls"] = 0
        control.atomic_json(path, data)
        result = worker.usage_snapshot(path, root / "unused.db", "", "openhands")
        self.assertEqual(o.accounted_usage(result)["accounted_tokens"], o.TIMEOUT_FALLBACK_TOKENS)


if __name__ == "__main__": unittest.main()

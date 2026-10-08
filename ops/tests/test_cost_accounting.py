import sys
import unittest

from harness import OPS_DIR

if str(OPS_DIR) not in sys.path:
    sys.path.insert(0, str(OPS_DIR))

import telemetry


class CostAccountingTests(unittest.TestCase):
    prices = {"m": {"input": 1.0, "output": 2.0}}

    def test_no_cache_and_aliases(self):
        self.assertEqual(
            telemetry.estimate_cost({"model": "m", "prompt_tokens": 1_000_000,
                                     "completion_tokens": 1_000_000}, self.prices), 3.0)

    def test_cache_requires_rate_and_inclusion_semantics(self):
        usage = {"model": "m", "input_tokens": 100, "output_tokens": 20,
                 "cache_read_tokens": 5}
        self.assertIsNone(telemetry.estimate_cost(usage, self.prices))
        p = {"m": {"input": 1.0, "output": 2.0, "cache_read": 0.1}}
        self.assertIsNone(telemetry.estimate_cost(usage, p))
        self.assertAlmostEqual(telemetry.estimate_cost(
            {**usage, "input_includes_cache": False}, p), 0.0001405)
        self.assertAlmostEqual(telemetry.estimate_cost(
            {**usage, "input_includes_cache": True}, p), 0.0001355)

    def test_cache_write_requires_rate(self):
        usage = {"model": "m", "input_tokens": 100, "output_tokens": 20,
                 "cache_write_tokens": 5, "input_includes_cache": False}
        self.assertIsNone(telemetry.estimate_cost(usage, self.prices))
        p = {"m": {"input": 1.0, "output": 2.0, "cache_write": 0.2}}
        self.assertAlmostEqual(telemetry.estimate_cost(usage, p), 0.000141)

    def test_invalid_usage_and_prices_are_unknown(self):
        base = {"model": "m", "input_tokens": 1, "output_tokens": 1}
        for bad in (-1, float("nan"), float("inf"), "nope"):
            self.assertIsNone(telemetry.estimate_cost({**base, "input_tokens": bad}, self.prices))
        for bad in (-1, float("nan"), float("inf"), "nope"):
            self.assertIsNone(telemetry.estimate_cost(base, {"m": {"input": bad, "output": 2}}))
        self.assertIsNone(telemetry.estimate_cost({"model": "m", "input_tokens": 1}, self.prices))

    def test_build_run_uses_authoritative_model_without_mutating_usage(self):
        usage = {"input_tokens": 1, "output_tokens": 1, "accounting_source": "state.db",
                 "reasoning_tokens": 3, "cache_write_tokens": 0, "usage_complete": True}
        old = telemetry.load_prices
        telemetry.load_prices = lambda: {"authoritative": {"input": 1.0, "output": 2.0}}
        try:
            rec = telemetry.build_run(ts_start="x", ts_end="y", role="builder",
                                       model="authoritative", usage=usage)
        finally:
            telemetry.load_prices = old
        self.assertNotIn("model", usage)
        self.assertEqual(rec["model"], "authoritative")
        self.assertEqual(rec["cost_estimate"], 0.000003)
        self.assertEqual(rec["accounting_source"], "state.db")
        self.assertEqual(rec["reasoning_tokens"], 3)
        self.assertEqual(rec["cache_write_tokens"], 0)
        self.assertTrue(rec["usage_complete"])

    def test_write_prices_preserves_extra_fields(self):
        old = telemetry.DEFAULT_PRICES
        telemetry.DEFAULT_PRICES = {"m": {"input": 1, "output": 2, "cache_read": 0.1,
                                           "input_includes_cache": False, "provider_tag": 7}}
        try:
            telemetry.write_prices()
            loaded = telemetry.load_prices()
        finally:
            telemetry.DEFAULT_PRICES = old
        self.assertEqual(loaded["m"]["cache_read"], 0.1)
        self.assertFalse(loaded["m"]["input_includes_cache"])
        self.assertEqual(loaded["m"]["provider_tag"], 7.0)


if __name__ == "__main__":
    unittest.main()

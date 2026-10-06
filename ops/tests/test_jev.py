"""Jev fail-open paths, the review-cascade gates, and the auto-disable guards.

Jev is routing-only help. Every entry point must fall back to the existing rule
on any error, timeout, malformed response, or missing probability/confidence -
Jev must never block or stall the pipeline. Nothing here touches the network:
the transport and the key are stubbed.
"""

from __future__ import annotations

import json
import unittest

import harness  # noqa: F401  (forces temp PHPRETRO_OPS before importing jev)

import jev


class FailOpenTest(unittest.TestCase):
    def setUp(self):
        # No key at all: this is the unconfigured install.
        self._saved_key = jev.api_key
        jev.api_key = lambda: ""
        jev.save_state({**jev.load_state(), "enabled": {"a": True, "b": True, "c": True}})

    def tearDown(self):
        jev.api_key = self._saved_key

    def test_size_check_falls_back_to_the_rule(self):
        res = jev.size_check({"id": "X", "paths": ["p"], "size": "S"})
        self.assertEqual(res["source"], "rule")
        self.assertEqual(res["action"], "run_as_is")

    def test_triage_falls_back_to_the_rule(self):
        res = jev.triage({"id": "X"}, "boom", 1, 4, False)
        self.assertIn(res["source"], ("rule",))
        self.assertIn(res["action"], jev.TRIAGE_OPTIONS)

    def test_review_gate_never_skips_without_a_key(self):
        res = jev.review_gate({"id": "X"}, "diff --git a/a b/a\n+ x\n", True)
        self.assertFalse(res["skip"])

    def test_a_timed_out_unit_is_never_run_as_is(self):
        res = jev.size_check({"id": "X", "paths": ["p"], "timeouts": 1})
        self.assertEqual(res["action"], "split")
        self.assertEqual(res["source"], "rule")


class TransportFailureTest(unittest.TestCase):
    """A key IS configured but the call fails: still the existing rule."""

    def setUp(self):
        self._saved_key = jev.api_key
        self._saved_post = jev._post
        jev.api_key = lambda: "test-key-not-real"
        jev.save_state({**jev.load_state(), "enabled": {"a": True, "b": True, "c": True}})

    def tearDown(self):
        jev.api_key = self._saved_key
        jev._post = self._saved_post

    def _explode(self, *a, **k):
        raise TimeoutError("simulated transport failure")

    def test_timeout_falls_back_for_all_three_sites(self):
        jev._post = self._explode
        self.assertEqual(jev.size_check({"id": "X", "paths": ["p"], "size": "S"})["source"], "rule")
        self.assertEqual(jev.triage({"id": "X"}, "o", 1, 4, False)["source"], "rule")
        self.assertFalse(jev.review_gate(
            {"id": "X"}, "diff --git a/a b/a\n+ x\n", True)["skip"])

    def test_malformed_response_falls_back(self):
        jev._post = lambda *a, **k: {"nonsense": True}
        res = jev.size_check({"id": "X", "paths": ["p"], "size": "S"})
        self.assertEqual(res["source"], "rule")

    def test_missing_confidence_is_treated_as_zero(self):
        option, prob, conf = jev._choice_answer(
            {"q": {"type": "choice", "choice": "yes", "probabilities": {"yes": 0.99}}}, "q")
        self.assertEqual(option, "yes")
        self.assertEqual(prob, 0.99)
        self.assertEqual(conf, 0.0)

    def test_missing_probability_is_treated_as_zero(self):
        option, prob, conf = jev._choice_answer(
            {"q": {"type": "choice", "choice": "yes", "confidence": 0.99}}, "q")
        self.assertEqual(prob, 0.0)


class ReviewCascadeGateTest(unittest.TestCase):
    """The rule gates are checked BEFORE any call, and they fail closed."""

    def setUp(self):
        self._saved_key = jev.api_key
        self._saved_post = jev._post
        jev.api_key = lambda: "test-key-not-real"
        jev.save_state({**jev.load_state(), "enabled": {"a": True, "b": True, "c": True}})
        self.called = False

        def _post(*a, **k):
            self.called = True
            raise TimeoutError("must not be called")

        jev._post = _post

    def tearDown(self):
        jev.api_key = self._saved_key
        jev._post = self._saved_post

    SMALL = "diff --git a/internal/api/h.go b/internal/api/h.go\n+ x\n"

    def test_sensitive_path_never_skips_and_never_calls(self):
        res = jev.review_gate({"id": "X"},
                              "diff --git a/internal/session/s.go b/internal/session/s.go\n+ x\n",
                              True)
        self.assertFalse(res["skip"])
        self.assertEqual(res["reason"], "sensitive path")
        self.assertFalse(self.called)

    def test_large_diff_never_skips_and_never_calls(self):
        big = "diff --git a/internal/api/b.go b/internal/api/b.go\n" + "+x\n" * 350
        res = jev.review_gate({"id": "X"}, big, True)
        self.assertFalse(res["skip"])
        self.assertFalse(self.called)

    def test_failing_tests_never_skip_and_never_call(self):
        res = jev.review_gate({"id": "X"}, self.SMALL, False)
        self.assertFalse(res["skip"])
        self.assertEqual(res["reason"], "tests not passing")
        self.assertFalse(self.called)

    def test_empty_diff_never_skips(self):
        res = jev.review_gate({"id": "X"}, "", True)
        self.assertFalse(res["skip"])
        self.assertFalse(self.called)

    def test_ops_path_is_sensitive(self):
        res = jev.review_gate({"id": "X"}, "diff --git a/ops/x.py b/ops/x.py\n+ y\n", True)
        self.assertFalse(res["skip"])
        self.assertEqual(res["reason"], "sensitive path")


class LadderTest(unittest.TestCase):
    def test_model_is_pinned_and_not_the_alias(self):
        self.assertEqual(jev.JEV_MODEL, "typesafe/jev-1.13")
        self.assertFalse(jev.JEV_MODEL.endswith("-latest"))

    def test_endpoint_is_the_decisions_api(self):
        self.assertEqual(jev.ENDPOINT, "https://openrouter.ai/api/alpha/decisions")

    def test_allowed_options_shrink_with_the_ladder(self):
        self.assertEqual(jev.allowed_triage(4, 4, True), ["park"])
        self.assertIn("escalate_model", jev.allowed_triage(1, 4, False))
        self.assertNotIn("escalate_model", jev.allowed_triage(1, 4, True))


class AutoDisableTest(unittest.TestCase):
    def setUp(self):
        jev.save_state({**jev.load_state(),
                        "enabled": {"a": True, "b": True, "c": True},
                        "skips": [], "misses": 0, "miss_units": [],
                        "last_miss_date": "", "recent_merged": [],
                        "median_checked_at": 0, "changed": 0, "calls": 0})
        self._saved_log = jev.log_call
        jev.log_call = lambda rec: None

    def tearDown(self):
        jev.log_call = self._saved_log

    def test_two_misses_in_ten_skipped_reviews_disable_c(self):
        for i in range(2):
            jev.note_skip(f"M{i}", 10, 100)
            # Each miss must be on a distinct day, or the same incident is
            # assumed and the second is suppressed by design.
            st = jev.load_state()
            st["last_miss_date"] = "2000-01-01"
            jev.save_state(st)
            jev.note_miss(f"M{i}", "nightly failure")
        self.assertFalse(jev.load_state()["enabled"]["c"])
        self.assertTrue(jev.load_state()["disabled_reason"]["c"])

    def test_one_miss_does_not_disable_c(self):
        jev.note_skip("M0", 10, 100)
        jev.note_miss("M0", "nightly failure")
        self.assertTrue(jev.load_state()["enabled"]["c"])

    def test_a_single_incident_counts_once(self):
        jev.note_skip("M0", 10, 100)
        jev.note_miss("M0", "nightly failure")
        jev.note_skip("M1", 10, 100)
        jev.note_miss("M1", "the same night's fix unit")
        self.assertTrue(jev.load_state()["enabled"]["c"])
        self.assertEqual(jev.load_state()["misses"], 1)

    def test_recent_miss_attributes_to_the_newest_skip(self):
        jev.note_skip("M-old", 10, 100)
        jev.note_skip("M-new", 10, 100)
        got = jev.note_miss_recent("nightly integration failure")
        self.assertEqual(got, ["M-new"])

    def test_no_recent_skip_means_no_miss(self):
        self.assertEqual(jev.note_miss_recent("nothing to blame"), [])


class MedianDisableTest(unittest.TestCase):
    def test_medians_that_do_not_improve_disable_a_and_b(self):
        st = {**jev.load_state(),
              "enabled": {"a": True, "b": True, "c": True},
              "recent_merged": [{"unit": f"U{i}", "tokens": 1000} for i in range(20)],
              "median_checked_at": 0}
        jev.save_state(st)
        jev._maybe_disable_ab(jev.load_state())
        st2 = jev.load_state()
        self.assertFalse(st2["enabled"]["a"])
        self.assertFalse(st2["enabled"]["b"])

    def test_medians_that_improve_keep_a_and_b_on(self):
        merged = ([{"unit": f"old{i}", "tokens": 2000} for i in range(10)]
                  + [{"unit": f"new{i}", "tokens": 500} for i in range(10)])
        st = {**jev.load_state(),
              "enabled": {"a": True, "b": True, "c": True},
              "recent_merged": merged, "median_checked_at": 0}
        jev.save_state(st)
        jev._maybe_disable_ab(jev.load_state())
        self.assertTrue(jev.load_state()["enabled"]["a"])


class InputBudgetTest(unittest.TestCase):
    def test_oversized_state_is_trimmed_to_fit(self):
        big = {"field": "x" * 400000}
        trimmed, dropped = jev.trim_state(big, limit=1000)
        self.assertLessEqual(jev.estimate_tokens(trimmed), 1000)
        self.assertGreater(dropped, 0)

    def test_call_returns_none_when_it_cannot_fit(self):
        # A structure trim_state cannot shrink (no long strings) is skipped, not sent.
        saved = jev.api_key
        saved_post = jev._post
        jev.api_key = lambda: "k"
        jev._post = lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not post"))
        try:
            huge = {"numbers": [0] * 1_000_000}
            self.assertIsNone(jev.call(huge, {"q": {"type": "choice"}}, place="a", unit="X"))
        finally:
            jev.api_key = saved
            jev._post = saved_post


class NoSecretInLogTest(unittest.TestCase):
    def test_the_key_never_reaches_jev_jsonl(self):
        jev.log_call({"place": "a", "unit": "X", "question": "q", "chosen": "run_as_is",
                      "probability": 0.5, "confidence": 0.5, "cost": None})
        text = jev.JEV_LOG.read_text()
        self.assertNotIn("OPENROUTER", text)
        self.assertNotIn("Bearer", text)
        self.assertNotIn("test-key-not-real", text)


if __name__ == "__main__":
    unittest.main()

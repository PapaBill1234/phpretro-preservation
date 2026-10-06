"""Tests for the Token Terminator builder-context-engine guard and marker.

Requirement: the engine is kept only if it measurably pays off, and its savings
are never credited on an inactive path. These tests pin both halves: the cost
accounting (including that failed attempts stay charged and unknown spend never
becomes a number) and the marker (which must report active ONLY when the engine
staged context for the run's own session).
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import harness
from harness import tmpdir

import telemetry
import tt_guard


def run(unit, role, attempt, outcome, cost, tokens=(100, 10), eng="token-terminator",
        active=True, ts="2026-10-06T00:00:00Z"):
    return {"unit": unit, "role": role, "attempt": attempt, "outcome": outcome,
            "cost_estimate": cost, "input_tokens": tokens[0], "output_tokens": tokens[1],
            "ts_end": ts, "flags": {"context_engine": eng,
                                    "plugins": {"tt": eng == "token-terminator",
                                                "active": active}}}


def window(name, base, merged_first=True):
    rows = []
    for i in range(6):
        u = f"{name}{i}"
        rows.append(run(u, "builder", 1, "merged" if merged_first else "gate_failed", base))
        if not merged_first:
            rows.append(run(u, "builder", 2, "merged", base))
    return rows


class CostAccountingTest(unittest.TestCase):
    def test_charging_every_attempt_of_a_unit(self):
        recs = [run("U2", "builder", 1, "gate_failed", 0.50),
                run("U2", "builder", 2, "merged", 0.10)]
        cost = 0.0 if tt_guard.unit_cost(recs) is None else tt_guard.unit_cost(recs)
        assert cost is not None
        self.assertAlmostEqual(cost, 0.60)

    def test_unknown_spend_is_none_never_zero(self):
        recs = [run("U3", "builder", 1, "merged", None)]
        self.assertIsNone(tt_guard.unit_cost(recs))

    def test_a_unit_with_one_unknown_attempt_is_not_a_number(self):
        recs = [run("U4", "builder", 1, "timeout", None),
                run("U4", "builder", 2, "merged", 0.10)]
        self.assertIsNone(tt_guard.unit_cost(recs),
                          "partial knowledge must not be reported as a full cost")

    def test_review_spend_belongs_to_the_unit(self):
        recs = [run("U5", "builder", 1, "merged", 0.10),
                run("U5", "reviewer", 1, "other", 0.02)]
        self.assertAlmostEqual(tt_guard.unit_cost(recs), 0.12)

    def test_first_attempt_merged(self):
        ok = [run("U1", "builder", 1, "merged", 0.1)]
        no = [run("U2", "builder", 1, "gate_failed", 0.1),
              run("U2", "builder", 2, "merged", 0.1)]
        self.assertTrue(tt_guard.first_attempt_merged(ok))
        self.assertFalse(tt_guard.first_attempt_merged(no))


class VerdictTest(unittest.TestCase):
    def test_no_ruling_without_both_windows(self):
        r = tt_guard.measure([*window("A", 0.2)[:2], *window("B", 0.1)[:2]])
        self.assertEqual(r["status"], "insufficient")
        self.assertFalse(r["revert"], "a young sample must not revert the engine")

    def test_flat_cost_reverts(self):
        v = tt_guard.measure([*window("A", 0.20), *window("B", 0.20)])
        self.assertEqual(v["status"], "measured")
        self.assertTrue(v["revert"])
        self.assertIn("need >= 15%", v["verdict"])

    def test_15_percent_is_the_boundary(self):
        # exactly 15% cheaper must pass; 14% must not.
        ok = tt_guard.measure([*window("A", 0.20), *window("B", 0.17)])
        self.assertFalse(ok["revert"], ok["verdict"])
        no = tt_guard.measure([*window("A", 0.20), *window("B", 0.172)])
        self.assertTrue(no["revert"], no["verdict"])

    def test_cheaper_but_sloppier_reverts(self):
        v = tt_guard.measure([*window("A", 0.20, merged_first=True),
                              *window("B", 0.10, merged_first=False)])
        self.assertTrue(v["revert"])
        self.assertIn("first-attempt", v["verdict"])

    def test_cheaper_and_cleaner_keeps(self):
        v = tt_guard.measure([*window("A", 0.20), *window("B", 0.10)])
        self.assertFalse(v["revert"], v["verdict"])
        self.assertAlmostEqual(v["saving_pct"], 50.0, places=1)


class MarkerTest(unittest.TestCase):
    def test_inactive_engine_is_not_active(self):
        recs = [run("U9", "builder", 1, "merged", 0.1, eng="compressor",
                    active=False)]
        self.assertFalse(tt_guard.marker_active(recs))

    def test_active_requires_both_tt_and_active(self):
        tt_but_off = [run("U9", "builder", 1, "merged", 0.1, active=False)]
        self.assertFalse(tt_guard.marker_active(tt_but_off))

    def test_marker_reads_real_evidence_not_config(self):
        """A profile whose engine is configured but which has no store is inactive."""
        fake_home = tmpdir("home-")
        original = telemetry.HOME
        try:
            telemetry.HOME = fake_home
            (fake_home / ".hermes" / "profiles" / "builder").mkdir(parents=True)
            (fake_home / ".hermes" / "profiles" / "builder" / "config.yaml").write_text(
                "context:\n  engine: token-terminator\n")
            marker = telemetry._plugin_marker("builder", "sess-1")
            self.assertTrue(marker["tt"])
            self.assertFalse(marker["active"], "configured is not active without evidence")
            self.assertIn("error", marker)
        finally:
            telemetry.HOME = original

    def test_marker_active_only_for_the_own_session(self):
        fake_home = tmpdir("home-")
        original = telemetry.HOME
        try:
            telemetry.HOME = fake_home
            home = fake_home / ".hermes" / "profiles" / "builder"
            (home / "plugins" / "token-terminator").mkdir(parents=True)
            (home / "plugins" / "token-terminator" / "plugin.yaml").write_text(
                "name: token-terminator\nversion: '0.11.0'\n")
            db = home / "token-terminator" / "artifacts.sqlite3"
            db.parent.mkdir(parents=True)
            import sqlite3
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE tt_context_sources (session_id TEXT)")
            con.execute("INSERT INTO tt_context_sources VALUES ('sess-1')")
            con.commit()
            con.close()
            (home / "config.yaml").write_text("context:\n  engine: token-terminator\n")
            self.assertTrue(telemetry._plugin_marker("builder", "sess-1")["active"])
            self.assertFalse(telemetry._plugin_marker("builder", "other")["active"])
            self.assertFalse(telemetry._plugin_marker("builder", "")["active"])
            self.assertEqual(telemetry._plugin_marker("builder", "sess-1")["version"], "0.11.0")
        finally:
            telemetry.HOME = original

    def test_other_profiles_are_not_token_terminator(self):
        m = telemetry._plugin_marker("reviewer", "sess-1")
        self.assertFalse(m["tt"])
        self.assertFalse(m["active"])


class SymptomTest(unittest.TestCase):
    def test_two_units_with_symptoms_force_revert(self):
        p = tmpdir("tt-") / "tt.json"
        self.assertFalse(tt_guard.note_symptom("X1", p)["revert"])
        self.assertTrue(tt_guard.note_symptom("X2", p)["revert"])

    def test_reread_detection_is_strict(self):
        thrash = "\n".join(['read_file path="internal/a.go"'] * 3)
        self.assertTrue(tt_guard.context_loss_symptom([], thrash))
        self.assertFalse(tt_guard.context_loss_symptom([], 'read_file path="internal/a.go"'))

    def test_revert_state_survives_recompute(self):
        p = tmpdir("tt-") / "tt.json"
        tt_guard.note_symptom("X1", p)
        tt_guard.note_symptom("X2", p)
        st = tt_guard.record(p, runs=[*window("A", 0.2), *window("B", 0.1)])
        self.assertTrue(st["revert"], "a symptom revert must not be cleared by a good cost window")


class StateLinesTest(unittest.TestCase):
    def test_collecting_line_names_the_shortfall(self):
        p = tmpdir("tt-") / "tt.json"
        tt_guard.record(p, runs=[run("U1", "builder", 1, "merged", 0.1)])
        text = "\n".join(tt_guard.summary_lines(p))
        self.assertIn("collecting", text)
        self.assertIn("need 12", text)

    def test_verdict_line_carries_numbers(self):
        p = tmpdir("tt-") / "tt.json"
        tt_guard.record(p, runs=[*window("A", 0.2), *window("B", 0.1)])
        text = "\n".join(tt_guard.summary_lines(p))
        self.assertIn("KEEP", text)
        self.assertIn("median cost/merged unit", text)


class WiringTest(unittest.TestCase):
    """Source-level guards: the guard must be invoked by the pipeline."""

    OPS = Path(__file__).resolve().parent.parent

    def test_cycle_calls_the_guard(self):
        self.assertRegex((self.OPS / "orchestrator.py").read_text(),
                         r"def cycle\(\)[\s\S]*?_tt_auto_revert\(\)")

    def test_state_md_has_a_token_terminator_section(self):
        src = (self.OPS / "orchestrator.py").read_text()
        self.assertIn("tt_lines()", src)
        self.assertIn("Token Terminator (builder context engine)", src)

    def test_revert_deselects_the_engine(self):
        src = (self.OPS / "orchestrator.py").read_text()
        self.assertIn("token-terminator", src)
        self.assertIn("uninstall", src)

    def test_run_records_are_marked_with_the_engine(self):
        src = (self.OPS / "orchestrator.py").read_text()
        self.assertIn("default_flags(profile, toolsets", src)
        self.assertIn("session_id", src)

    def test_builder_dispatch_allows_the_context_engine_toolset(self):
        """Without the toolset the engine refuses to reduce, silently. Pin it."""
        src = (self.OPS / "orchestrator.py").read_text()
        self.assertIn('toolsets = "file,terminal,context_engine"', src)
        self.assertIn("file,terminal,context_engine", src)

    def test_revert_targets_the_dependency_venv_not_the_launcher(self):
        """The package lives in the uv venv, not the launcher interpreter."""
        import orchestrator as o
        src = (self.OPS / "orchestrator.py").read_text()
        self.assertIn("_venv_has", src)
        self.assertIn("environments", src)
        # The helper must pick a venv that actually holds the distribution when
        # one exists on this machine; otherwise it is a no-op we cannot assert.
        p = o._hermes_venv_python()
        if p is not None:
            self.assertIn("environments", str(p))


if __name__ == "__main__":
    unittest.main()

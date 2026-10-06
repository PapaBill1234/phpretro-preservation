"""The suite is wired into the gates: a red suite must fail the self-check.

This guards the PLUMBING, not the pipeline logic. To stay fast and to avoid
recursing into itself, every case here drives a THROWAWAY copy of run_all.sh
containing one tiny test; the entry points are pointed at that copy with
``PHPRETRO_OPS_TESTS``. Nothing writes into the real ops/tests, and the real
suite is never spawned from inside the suite.
"""

from __future__ import annotations

import os
import shutil
import unittest

import harness
from harness import OPS_DIR, REPO, run, tmpdir

import nightly as n
import orchestrator as o

RUN_ALL = OPS_DIR / "tests" / "run_all.sh"

RED_TEST = ("import unittest\n\n"
            "class Red(unittest.TestCase):\n"
            "    def test_fails(self):\n"
            "        self.fail('deliberately failing test')\n")
GREEN_TEST = ("import unittest\n\n"
              "class Green(unittest.TestCase):\n"
              "    def test_passes(self):\n"
              "        self.assertTrue(True)\n")


def _clean_env(extra: dict | None = None) -> dict:
    """Env for a spawned suite: depth 1, no inherited skip flag.

    The nightly self-check exports PHPRETRO_SKIP_OPS_TESTS=1 (so --selftest does
    not run the suite twice); if that leaked into a spawned --selftest here, the
    red-suite cases would be skipped and pass by accident. Depth 1 stops the
    meta-tests from spawning again.
    """
    env = {"PHPRETRO_SUITE_DEPTH": "1", "PHPRETRO_SKIP_OPS_TESTS": "0"}
    if extra:
        env.update(extra)
    return env


def _fake_suite(test_body: str):
    """A throwaway suite dir: a copy of run_all.sh plus one small test module."""
    d = tmpdir("suite-")
    shutil.copy2(RUN_ALL, d / "run_all.sh")
    (d / "test_zz.py").write_text(test_body)
    return d


class RunAllScriptTest(unittest.TestCase):
    """run_all.sh itself: discovery and exit-code propagation."""

    def test_propagates_a_failing_test(self):
        d = _fake_suite(RED_TEST)
        r = run(["bash", str(d / "run_all.sh")], cwd=REPO, timeout=300, env=_clean_env())
        self.assertNotEqual(r.returncode, 0, r.stdout[-1500:])
        self.assertIn("ops/tests: FAIL", r.stdout + r.stderr)

    def test_reports_pass_on_a_green_suite(self):
        d = _fake_suite(GREEN_TEST)
        r = run(["bash", str(d / "run_all.sh")], cwd=REPO, timeout=300, env=_clean_env())
        self.assertEqual(r.returncode, 0, r.stdout[-1500:] + r.stderr[-1500:])
        self.assertIn("ops/tests: PASS", r.stdout)


class EntryPointWiringTest(unittest.TestCase):
    """The real entry points must run the suite and go red when it does."""

    def _selftest(self, suite: str, extra: dict | None = None):
        env = _clean_env()
        env["PHPRETRO_OPS_TESTS"] = suite
        if extra:
            env.update(extra)
        return run(["python3", str(OPS_DIR / "orchestrator.py"), "--selftest"],
                   cwd=REPO, timeout=600, env=env)

    def test_red_suite_fails_orchestrator_selftest(self):
        d = _fake_suite(RED_TEST)
        r = self._selftest(str(d / "run_all.sh"))
        self.assertNotEqual(r.returncode, 0, r.stdout[-1500:])
        self.assertNotIn("selftest OK", r.stdout)

    def test_green_suite_leaves_orchestrator_selftest_green(self):
        d = _fake_suite(GREEN_TEST)
        r = self._selftest(str(d / "run_all.sh"))
        self.assertEqual(r.returncode, 0, r.stdout[-1500:])
        self.assertIn("selftest OK", r.stdout)

    def test_skip_flag_leaves_selftest_green(self):
        # The nightly job runs the suite as its own check; the copy inside
        # --selftest must be skippable so the job does not run it twice.
        d = _fake_suite(RED_TEST)
        r = self._selftest(str(d / "run_all.sh"), {"PHPRETRO_SKIP_OPS_TESTS": "1"})
        self.assertEqual(r.returncode, 0, r.stdout[-1500:])
        self.assertIn("selftest OK", r.stdout)

    def test_missing_suite_fails_closed(self):
        r = self._selftest(str(tmpdir("gone-") / "nope.sh"))
        self.assertNotEqual(r.returncode, 0, "a missing suite must not pass silently")
        self.assertNotIn("selftest OK", r.stdout)

    def test_nightly_check_goes_red_on_a_red_suite(self):
        d = _fake_suite(RED_TEST)
        os.environ["PHPRETRO_OPS_TESTS"] = str(d / "run_all.sh")
        try:
            check = n.check_ops_tests()
        finally:
            os.environ.pop("PHPRETRO_OPS_TESTS", None)
        self.assertFalse(check["ok"], check)
        self.assertIn("FAIL", check["detail"])

    def test_nightly_check_is_green_on_a_green_suite(self):
        d = _fake_suite(GREEN_TEST)
        os.environ["PHPRETRO_OPS_TESTS"] = str(d / "run_all.sh")
        try:
            check = n.check_ops_tests()
        finally:
            os.environ.pop("PHPRETRO_OPS_TESTS", None)
        self.assertTrue(check["ok"], check["detail"][-800:])


class SourceWiringTest(unittest.TestCase):
    """Cheap guards: if a call is dropped, nothing else would notice."""

    def test_selftest_invokes_run_ops_tests(self):
        self.assertRegex((OPS_DIR / "orchestrator.py").read_text(),
                         r"def selftest\(\)[\s\S]*?run_ops_tests\(\)")

    def test_nightly_selfcheck_lists_the_ops_suite_check(self):
        self.assertRegex((OPS_DIR / "nightly.py").read_text(),
                         r"checks = \[check_selftest\(\), check_ops_tests\(\)")

    def test_run_all_uses_unittest_discover(self):
        self.assertIn("unittest discover", RUN_ALL.read_text())

    def test_run_all_defaults_to_this_directory(self):
        self.assertIn('dirname "${BASH_SOURCE[0]}"', RUN_ALL.read_text())


class HarnessIsolationTest(unittest.TestCase):
    """The harness must redirect every writable root, or tests hit real state."""

    def test_home_is_redirected(self):
        self.assertEqual(os.environ["HOME"], str(harness._TMP / "home"))

    def test_ops_and_work_are_redirected(self):
        self.assertTrue(os.environ["PHPRETRO_OPS"].startswith(str(harness._TMP)))
        self.assertTrue(os.environ["PHPRETRO_WORK"].startswith(str(harness._TMP)))

    def test_module_paths_point_into_the_temp_tree(self):
        self.assertTrue(str(o.STATE_DIR).startswith(str(harness._TMP)))
        self.assertTrue(str(n.STATE_DIR).startswith(str(harness._TMP)))

    def test_repo_still_points_at_the_real_checkout(self):
        # REPO is read (not written) and must resolve, or the suite cannot run.
        self.assertEqual(str(o.REPO), str(REPO))
        self.assertTrue((REPO / "ops" / "orchestrator.py").exists())

    def test_no_real_key_is_visible(self):
        import jev
        self.assertEqual(jev.api_key(), "")


if __name__ == "__main__":
    unittest.main()

"""The pre-push hook, driven through REAL git pushes in a scratch repository.

The hook is the boundary that holds even if a model talks its way past the
orchestrator's diff guard, so it is tested the way it is used: a real push to a
real (temporary) bare remote, with the project repository only READ.
"""

from __future__ import annotations

import unittest

from harness import OPS_DIR, git_repo, run, tmpdir

HOOK_DIR = OPS_DIR / "hooks"


class PrePushHookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (HOOK_DIR / "pre-push").exists():
            raise unittest.SkipTest(f"no hook at {HOOK_DIR / 'pre-push'}")

    def setUp(self):
        self.root = tmpdir("hook-")
        self.origin = self.root / "origin.git"
        self.repo = self.root / "repo"
        self.env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
        run(["git", "init", "-q", "--bare", str(self.origin)])
        git_repo(self.repo)
        (self.repo / "internal").mkdir()
        (self.repo / "internal" / "ok.go").write_text("package internal\n")
        (self.repo / "ops").mkdir()
        (self.repo / "ops" / "orchestrator.py").write_text("# pipeline\n")
        run(["git", "add", "-A"], cwd=self.repo)
        run(["git", "commit", "-qm", "base"], cwd=self.repo)
        run(["git", "branch", "-M", "main"], cwd=self.repo)
        run(["git", "remote", "add", "origin", str(self.origin)], cwd=self.repo)
        # Seed origin/main with the hook OFF, as in reality.
        p = run(["git", "-c", "core.hooksPath=", "push", "-q", "origin", "main"],
                cwd=self.repo, env=self.env)
        self.assertEqual(p.returncode, 0, p.stderr)
        run(["git", "fetch", "-q", "origin"], cwd=self.repo)
        # Hook ON for unit pushes.
        run(["git", "config", "core.hooksPath", str(HOOK_DIR)], cwd=self.repo)

    def _push(self, refspec):
        return run(["git", "push", *refspec], cwd=self.repo, env=self.env)

    def test_protected_path_is_refused(self):
        run(["git", "checkout", "-q", "-B", "unit/T1", "origin/main"], cwd=self.repo)
        (self.repo / "ops" / "orchestrator.py").write_text("# tampered\n")
        run(["git", "add", "-A"], cwd=self.repo)
        run(["git", "commit", "-qm", "edit ops"], cwd=self.repo)
        p = self._push(["origin", "HEAD:refs/heads/unit/T1"])
        self.assertNotEqual(p.returncode, 0, "a protected path must not be published")
        self.assertIn("protected paths", p.stdout + p.stderr)

    def test_in_scope_change_is_allowed(self):
        run(["git", "checkout", "-q", "-B", "unit/T2", "origin/main"], cwd=self.repo)
        (self.repo / "internal" / "ok.go").write_text("package internal\n// work\n")
        run(["git", "commit", "-aqm", "in scope"], cwd=self.repo)
        p = self._push(["origin", "HEAD:refs/heads/unit/T2"])
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_push_to_main_is_refused(self):
        run(["git", "checkout", "-q", "main"], cwd=self.repo)
        (self.repo / "internal" / "ok.go").write_text("package internal\n// main change\n")
        run(["git", "commit", "-aqm", "main change"], cwd=self.repo)
        p = self._push(["origin", "main"])
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("protected branch", p.stdout + p.stderr)

    def test_deleting_a_protected_branch_is_refused(self):
        p = self._push(["origin", "--delete", "main"])
        self.assertNotEqual(p.returncode, 0)

    def test_force_update_of_a_non_unit_branch_is_refused(self):
        run(["git", "checkout", "-q", "-B", "feature/x", "origin/main"], cwd=self.repo)
        (self.repo / "internal" / "ok.go").write_text("package internal\n// one\n")
        run(["git", "commit", "-aqm", "one"], cwd=self.repo)
        p = self._push(["origin", "HEAD:refs/heads/feature/x"])
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        # Rewrite history, then force-push: the hook must refuse.
        run(["git", "reset", "-q", "--hard", "HEAD~1"], cwd=self.repo)
        (self.repo / "internal" / "ok.go").write_text("package internal\n// two\n")
        run(["git", "commit", "-aqm", "two"], cwd=self.repo)
        p = self._push(["origin", "--force", "HEAD:refs/heads/feature/x"])
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("non-fast-forward", p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()

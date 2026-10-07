"""quality: the removal / coverage / evidence gates, and the diff base."""

from __future__ import annotations

import unittest

from harness import commit, git_repo, head, run, tmpdir

import quality as q


class DiffBaseTest(unittest.TestCase):
    """quality.changed_files must use the merge base, like the guard does."""

    def setUp(self):
        self.repo = git_repo(tmpdir("qdiff-"))
        (self.repo / "docs/units").mkdir(parents=True)
        (self.repo / "a.txt").write_text("a")
        (self.repo / "docs/units/OTHER.md").write_text("base")
        commit(self.repo, "base")
        run(["git", "branch", "origin/main"], cwd=self.repo)
        run(["git", "checkout", "-qb", "unit/X"], cwd=self.repo)
        (self.repo / "b.txt").write_text("b")
        commit(self.repo, "unit work")
        run(["git", "checkout", "-q", "origin/main"], cwd=self.repo)
        (self.repo / "docs/units/OTHER.md").write_text("main")
        (self.repo / "mainonly.txt").write_text("m")
        commit(self.repo, "main advances")
        run(["git", "checkout", "-q", "unit/X"], cwd=self.repo)

    def test_ignores_files_main_gained_after_the_branch_point(self):
        files = q.changed_files(self.repo, "origin/main")
        self.assertNotIn("mainonly.txt", files)
        self.assertNotIn("docs/units/OTHER.md", files)
        self.assertIn("b.txt", files)


class ClassifyTest(unittest.TestCase):
    def test_split_changes_separates_impl_tests_and_docs(self):
        impl, tests = q.split_changes(
            ["internal/a/x.go", "internal/a/x_test.go", "docs/units/F1.md"])
        self.assertEqual(impl, ["internal/a/x.go"])
        self.assertEqual(tests, ["internal/a/x_test.go"])

    def test_go_package_dirs_are_unique_targets(self):
        self.assertEqual(
            q.go_package_dirs(["internal/a/x.go", "internal/a/y_test.go", "internal/b/z.go"]),
            ["./internal/a", "./internal/b"])


class CoverageParseTest(unittest.TestCase):
    PROFILE = ("mode: count\n"
               "github.com/PHP-Retro/x/internal/registration/registration.go:10.2,12.4 2 1\n"
               "github.com/PHP-Retro/x/internal/registration/registration.go:14.2,16.4 2 0\n"
               "github.com/PHP-Retro/x/internal/other/other.go:1.1,2.2 4 4\n")

    def test_parses_only_the_changed_file(self):
        per = q.parse_coverprofile(self.PROFILE, ["internal/registration/registration.go"])
        self.assertEqual(per["internal/registration/registration.go"],
                         {"covered": 2, "total": 4})
        self.assertNotIn("internal/other/other.go", per)

    def test_percent_and_empty_profile(self):
        per = q.parse_coverprofile(self.PROFILE, ["internal/registration/registration.go"])
        self.assertEqual(q.coverage_percent(per), (50.0, 2, 4))
        self.assertEqual(q.coverage_percent(q.parse_coverprofile("mode: count\n", ["a.go"])),
                         (0.0, 0, 0))


class RemovalCheckTest(unittest.TestCase):
    """Item 1: with the implementation gone, the new tests must FAIL.

    The unit's change lives on the branch; ``base`` is the pre-change commit.
    ``removal_check`` restores the implementation from ``base`` and re-runs the
    tests: if they still pass, they never exercised the new code.
    """

    def _repo(self, *, test_asserts_the_behaviour: bool):
        repo = git_repo(tmpdir("removal-"))
        (repo / "go.mod").write_text("module example.com/x\n\ngo 1.21\n")
        (repo / "p").mkdir()
        # base version is WRONG on purpose, so the branch's fix is observable.
        (repo / "p" / "impl.go").write_text(
            "package p\n\nfunc Add(a, b int) int { return 0 }\n")
        commit(repo, "base")
        base = head(repo)
        # the unit's change: fix the implementation and add the test
        (repo / "p" / "impl.go").write_text(
            "package p\n\nfunc Add(a, b int) int { return a + b }\n")
        if test_asserts_the_behaviour:
            body = ('package p\n\nimport "testing"\n\n'
                    'func TestAdd(t *testing.T) {\n'
                    '\tif Add(1, 2) != 3 {\n\t\tt.Fatalf("Add(1,2) = %d, want 3", Add(1, 2))\n\t}\n}\n')
        else:
            body = 'package p\n\nimport "testing"\n\nfunc TestNothing(t *testing.T) {}\n'
        (repo / "p" / "impl_test.go").write_text(body)
        commit(repo, "unit work")
        return repo, base

    def _go(self):
        import shutil
        return shutil.which("go") is not None

    def test_no_impl_files_is_not_applicable(self):
        res = q.removal_check(tmpdir("norem-"), "HEAD", [], ["go test ./p"])
        self.assertTrue(res["ok"])
        self.assertFalse(res.get("applicable", True))

    def test_go_implementation_without_command_fails_closed(self):
        res = q.removal_check(tmpdir("nocmd-"), "HEAD", ["p/impl.go"], ["bash scripts/check.sh"])
        self.assertFalse(res["ok"])
        self.assertTrue(res.get("applicable"))

    def test_tests_that_exercise_the_code_fail_without_it(self):
        if not self._go():
            self.skipTest("go toolchain not on PATH")
        repo, base = self._repo(test_asserts_the_behaviour=True)
        res = q.removal_check(repo, base, ["p/impl.go"], ["go test ./p"])
        self.assertTrue(res["ok"], res)

    def test_tests_that_do_not_exercise_the_code_are_rejected(self):
        if not self._go():
            self.skipTest("go toolchain not on PATH")
        repo, base = self._repo(test_asserts_the_behaviour=False)
        res = q.removal_check(repo, base, ["p/impl.go"], ["go test ./p"])
        self.assertFalse(res["ok"], res)
        self.assertEqual(res["reason"], "tests do not exercise the change")

    def test_the_implementation_is_restored_afterwards(self):
        if not self._go():
            self.skipTest("go toolchain not on PATH")
        repo, base = self._repo(test_asserts_the_behaviour=True)
        q.removal_check(repo, base, ["p/impl.go"], ["go test ./p"])
        self.assertIn("a + b", (repo / "p" / "impl.go").read_text(),
                      "the hidden implementation must be put back")


class EvidenceTest(unittest.TestCase):
    def test_guessed_label_does_not_accept_an_uncited_test(self):
        repo = tmpdir("evid-")
        (repo / "docs/units").mkdir(parents=True)
        (repo / "docs/units/F1.md").write_text("# F1\nfidelity: guessed\n")
        (repo / "p").mkdir()
        (repo / "p" / "x_test.go").write_text("package p\n")
        res = q.evidence_check(repo, {"id": "F1"}, ["p/x_test.go"])
        self.assertFalse(res["ok"], res)
        self.assertTrue(res["guessed"])

    def test_uncited_test_without_the_label_is_rejected(self):
        repo = tmpdir("evid2-")
        (repo / "docs/units").mkdir(parents=True)
        (repo / "docs/units/F2.md").write_text("# F2\n")
        (repo / "p").mkdir()
        (repo / "p" / "x_test.go").write_text("package p\n")
        res = q.evidence_check(repo, {"id": "F2"}, ["p/x_test.go"])
        self.assertFalse(res["ok"], res)

    def test_a_recognised_citation_is_accepted(self):
        repo = tmpdir("evid3-")
        (repo / "docs/units").mkdir(parents=True)
        (repo / "docs/units/F3.md").write_text("# F3\n")
        (repo / "docs/roadmap").mkdir()
        (repo / "docs/roadmap/spec.md").write_text("Bounded profile reads are required.\n")
        (repo / "docs/evidence").mkdir()
        (repo / "docs/evidence/F3.md").write_text("Acceptance: docs/roadmap/spec.md\n")
        (repo / "p").mkdir()
        (repo / "p" / "x_test.go").write_text("// source: docs/evidence/F3.md\npackage p\n")
        res = q.evidence_check(repo, {"id": "F3"}, ["p/x_test.go"])
        self.assertTrue(res["ok"], res)


if __name__ == "__main__":
    unittest.main()

"""Maintenance B: behavior proof, fresh coverage and feature-specific evidence.

Everything uses isolated repositories; no workers, providers or GitHub calls.
"""
import json
import shutil
import unittest
from unittest.mock import patch

from harness import tmpdir, git_repo, commit, head, run, REPO
import quality as q


def assertion(name="TestAdd", message="impl_test.go:8: got 0, want 3"):
    return "\n".join(json.dumps(event) for event in (
        {"Action": "output", "Test": name, "Output": message + "\n"},
        {"Action": "fail", "Test": name}, {"Action": "fail", "Package": "example/p"}))


class AssertionProof(unittest.TestCase):
    def test_named_assertion_only(self):
        self.assertTrue(q.assertion_failure(1, assertion())["ok"])
        for rc, output in [(0, assertion()), (124, assertion()), (2, assertion()),
                           (1, '[build failed]'), (1, assertion(message="panic: nil pointer")),
                           (1, assertion(message="impl_test.go:8: panic: nil pointer")),
                           (1, assertion() + '\nnot JSON')]:
            self.assertFalse(q.assertion_failure(rc, output)["ok"], (rc, output))

    def test_unchanged_tests_cannot_be_claimed_as_new_test_proof(self):
        self.assertFalse(q.assertion_failure(1, assertion(), {"TestOther"})["ok"])
        self.assertTrue(q.assertion_failure(1, assertion("TestAdd/sub"), {"TestAdd"})["ok"])


class FrontendProof(unittest.TestCase):
    def test_type_errors_compile_errors_and_missing_tools_never_pass(self):
        def event(asserted, kind="testCodeFailure"):
            return json.dumps({"type": "test:fail", "assertion": asserted, "failure_type": kind})
        self.assertTrue(q.frontend_assertion_failure(1, event(True)))
        self.assertFalse(q.frontend_assertion_failure(1, event(False)))
        self.assertFalse(q.frontend_assertion_failure(2, event(True)))
        self.assertFalse(q.frontend_assertion_failure(1, "TS2304 compile error"))
        self.assertFalse(q.frontend_assertion_failure(1, event(True) + "\n" + event(False)))
        repo = tmpdir("frontend-tools-")
        (repo / "frontend/src").mkdir(parents=True)
        (repo / "frontend/tests").mkdir()
        (repo / "frontend/src/a.ts").write_text("export function add(a:number,b:number){return a+b;}")
        (repo / "frontend/tests/a.test.ts").write_text('import {add} from "../src/a.js";')
        self.assertFalse(q.frontend_removal_check(repo, ["frontend/src/a.ts"], ["frontend/tests/a.test.ts"])["ok"])

    def test_test_local_fake_without_production_source_is_rejected(self):
        repo = tmpdir("frontend-fake-")
        (repo / "frontend/tests").mkdir(parents=True)
        (repo / "frontend/tests/a.test.ts").write_text("function fake(){return 1;}")
        self.assertFalse(q.frontend_removal_check(repo, [], ["frontend/tests/a.test.ts"])["ok"])


@unittest.skipUnless((REPO / "frontend/node_modules/typescript/lib/typescript.js").is_file() and shutil.which("node"), "pinned frontend dependency required")
class FrontendMutationIntegration(unittest.TestCase):
    def setUp(self):
        self.repo = tmpdir("frontend-mutation-")
        (self.repo / "frontend/src").mkdir(parents=True)
        (self.repo / "frontend/tests").mkdir()
        (self.repo / "frontend/node_modules").symlink_to(REPO / "frontend/node_modules", target_is_directory=True)
        (self.repo / "frontend/tsconfig.json").write_text(json.dumps({"compilerOptions": {"target": "ES2022", "module": "NodeNext", "moduleResolution": "NodeNext", "strict": True, "skipLibCheck": True}, "include": ["src", "tests"]}))
        (self.repo / "frontend/src/a.ts").write_text("export function add(a:number,b:number):number { return a+b; }\n")

    def test_real_assertion_and_fake_only_test_are_distinguished(self):
        path = self.repo / "frontend/tests/a.test.ts"
        path.write_text('import {strict as assert} from "node:assert"; import test from "node:test"; import {add} from "../src/a.js"; test("sum",()=>assert.equal(add(1,2),3));\n')
        original = (self.repo / "frontend/src/a.ts").read_bytes()
        result = q.frontend_removal_check(self.repo, ["frontend/src/a.ts"], ["frontend/tests/a.test.ts"])
        self.assertTrue(result["ok"], result)
        self.assertEqual((self.repo / "frontend/src/a.ts").read_bytes(), original)
        path.write_text('import {strict as assert} from "node:assert"; import test from "node:test"; import {add} from "../src/a.js"; function fake(a:number,b:number){return a+b;} test("sum",()=>assert.equal(fake(1,2),3));\n')
        self.assertFalse(q.frontend_removal_check(self.repo, ["frontend/src/a.ts"], ["frontend/tests/a.test.ts"])["ok"])
        self.assertFalse(list((self.repo / "frontend").glob(".quality-compiled-*")))

    def test_already_failing_fake_is_not_removal_proof(self):
        (self.repo / "frontend/tests/a.test.ts").write_text('import {strict as assert} from "node:assert"; import test from "node:test"; import {add} from "../src/a.js"; function fake(a:number,b:number){return a+b;} test("sum",()=>assert.equal(fake(1,2),99));\n')
        result = q.frontend_removal_check(self.repo, ["frontend/src/a.ts"], ["frontend/tests/a.test.ts"])
        self.assertFalse(result["ok"], result)
        self.assertIn("before behavior removal", result["reason"])


class FreshCoverage(unittest.TestCase):
    def setUp(self):
        self.repo = tmpdir("coverage-B-")

    def check(self, profile=None, rc=0):
        def runner(command, **kwargs):
            if profile is not None:
                from pathlib import Path
                Path(next(a.split("=", 1)[1] for a in command if a.startswith("-coverprofile="))).write_text(profile)
            return rc, "fixture output"
        with patch.object(q, "run", side_effect=runner):
            return q.coverage_check(self.repo, ["p/impl.go"], ["go test ./p"])

    def test_errors_missing_empty_and_malformed_never_pass(self):
        for profile, rc in [(None, 0), (None, 1), ("mode: count\n", 0),
                            ("garbage\n", 0), ("mode: count\np/impl.go:1.1,2.1 1 1\n", 1)]:
            result = self.check(profile, rc)
            self.assertFalse(result["ok"], result)
            self.assertEqual(result["failure_kind"], "unavailable")

    def test_valid_zero_coverage_is_below_floor_not_missing(self):
        result = self.check("mode: count\nexample/p/impl.go:1.1,2.1 2 0\n")
        self.assertEqual(result["failure_kind"], "below_floor")
        self.assertEqual(result["percent"], 0)

    def test_coverage_exemption_cannot_mask_error(self):
        (self.repo / "docs/units").mkdir(parents=True)
        (self.repo / "docs/units/F1.md").write_text("coverage-exempt: fixture\n")
        with patch.object(q, "changed_files", return_value=["p/impl.go"]), patch.object(q, "removal_check", return_value={"ok": True}), patch.object(q, "coverage_check", return_value={"ok": False, "failure_kind": "unavailable", "percent": None, "reason": "error"}):
            self.assertFalse(q.evaluate(self.repo, "HEAD", {"id": "F1"})["ok"])

    def test_all_command_packages_are_parsed(self):
        self.assertEqual(q._packages_from_cmds(["go test -run TestX ./a ./b/...", "go test -tags=fixture ./c"]), ["./a", "./b/...", "./c"])


class AcceptanceSources(unittest.TestCase):
    def setUp(self):
        self.repo = git_repo(tmpdir("sources-B-"))
        (self.repo / "docs/roadmap").mkdir(parents=True)
        (self.repo / "docs/units").mkdir()
        (self.repo / "p").mkdir()
        (self.repo / "docs/roadmap/spec.md").write_text("Original `profile.php:28-42` defines tabs. New themes cannot select identity.\n")
        (self.repo / "docs/stage3-original-phpretro-sha256.csv").write_text('Path,Hash\nfixture/stage3-original-phpretro/profile.php,retained\n')
        commit(self.repo, "approved spec")
        self.base = head(self.repo)

    def result(self, uid, citation):
        (self.repo / "p/x_test.go").write_text("// Evidence: " + citation + "\npackage p\n")
        return q.evidence_check(self.repo, {"id": uid}, ["p/x_test.go"], base=self.base)

    def test_legacy_needs_original_or_retained_capture(self):
        self.assertTrue(self.result("F18", "docs/roadmap/spec.md")["ok"])
        (self.repo / "docs/roadmap/spec.md").write_text("Self-invented projection\n")
        self.assertFalse(self.result("F18", "docs/roadmap/spec.md")["ok"])

    def test_new_feature_uses_approved_spec(self):
        self.assertTrue(self.result("F30", "docs/roadmap/spec.md")["ok"])
        self.assertFalse(self.result("F30", "docs/units/F30.md")["ok"])
        self.assertFalse(self.result("F30", "docs/roadmap/nonexistent.md")["ok"])
        (self.repo / "docs/roadmap/spec.md").write_text("Self-authored expected values\n")
        self.assertFalse(self.result("F30", "docs/roadmap/spec.md")["ok"])

    def test_symlink_cannot_supply_source(self):
        target = tmpdir("outside-B-") / "spec.md"
        target.write_text("new feature spec")
        (self.repo / "docs/roadmap/linked.md").symlink_to(target)
        self.assertFalse(self.result("F30", "docs/roadmap/linked.md")["ok"])


@unittest.skipUnless(shutil.which("go"), "Go toolchain required")
class MutationIntegration(unittest.TestCase):
    def setUp(self):
        self.repo = git_repo(tmpdir("mutation-B-"))
        (self.repo / "go.mod").write_text("module example.com/mutation\n\ngo 1.21\n")
        (self.repo / "p").mkdir()
        commit(self.repo, "baseline")
        self.base = head(self.repo)
        (self.repo / "p/impl.go").write_text('package p\nimport "strings"\nfunc Add(a,b int) int { return a+b }\nfunc Named(s string) (result string, err error) { return strings.TrimSpace(s), nil }\nfunc Identity[T any](v T) T { return v }\n')

    def test_new_api_preserves_compilation_and_exact_original_work(self):
        (self.repo / "p/impl_test.go").write_text('package p\nimport "testing"\nfunc TestAdd(t *testing.T) { if Add(1,2)!=3 { t.Fatal("wrong sum") } }\n')
        original = (self.repo / "p/impl.go").read_bytes()
        index = run(["git", "diff", "--cached"], cwd=self.repo).stdout
        result = q.removal_check(self.repo, self.base, ["p/impl.go"], ["go test ./p"], test_files=["p/impl_test.go"])
        self.assertTrue(result["ok"], result)
        self.assertEqual((self.repo / "p/impl.go").read_bytes(), original)
        self.assertEqual(run(["git", "diff", "--cached"], cwd=self.repo).stdout, index)

    def test_fake_defined_in_test_cannot_prove_production_behavior(self):
        (self.repo / "p/impl_test.go").write_text('package p\nimport "testing"\nfunc fakeAdd(a,b int) int {return a+b}\nfunc TestAdd(t *testing.T) {if fakeAdd(1,2)!=3 {t.Fatal("wrong")}}\n')
        result = q.removal_check(self.repo, self.base, ["p/impl.go"], ["go test ./p"], test_files=["p/impl_test.go"])
        self.assertFalse(result["ok"], result)

    def test_already_failing_go_fake_is_not_removal_proof(self):
        (self.repo / "p/impl_test.go").write_text('package p\nimport "testing"\nfunc fakeAdd(a,b int) int {return a+b}\nfunc TestAdd(t *testing.T) {if fakeAdd(1,2)!=99 {t.Fatal("wrong")}}\n')
        result = q.removal_check(self.repo, self.base, ["p/impl.go"], ["go test ./p"], test_files=["p/impl_test.go"])
        self.assertFalse(result["ok"], result)
        self.assertIn("before behavior removal", result["reason"])


if __name__ == "__main__":
    unittest.main()

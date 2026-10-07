#!/usr/bin/env python3
"""Quality safeguards for one builder attempt (items 1-3 of the quality work).

These run in the unit's worktree after ``scripts/check.sh`` passes and before
the PR is opened:

* ``removal_check``  (item 1) the new tests must fail when the implementation is
  taken away, otherwise they do not exercise the change.
* ``coverage_check`` (item 2) ``go test -cover`` over the changed packages; the
  changed files must reach the floor, unless the unit doc records why.
* ``evidence_check`` (item 3) changed tests cite an acceptance source appropriate
  to the feature. A guessed label reports uncertainty, never waives a gate.

Everything here is pure or takes an explicit worktree, so it can be exercised
without the orchestrator. ``ops/quality.py --selftest`` checks the parsers.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

COVERAGE_FLOOR = 60.0
# A unit doc can excuse a package that cannot be usefully covered, but it has to
# say so on an explicit line rather than leaving it to the reviewer's judgement.
COVERAGE_EXEMPT_RE = re.compile(r"^coverage-exempt:\s*(\S.*)$", re.M)
GUESSED_RE = re.compile(r"fidelity:\s*guessed", re.I)
# Evidence roots a test may cite; the unit's own fixtures are added per unit.
EVIDENCE_ROOTS = ("docs/evidence", "docs/roadmap", "docs/decisions", "tests/golden/original")


# --------------------------------------------------------------------------
# tiny process helper (kept local so quality.py has no import cycle)
# --------------------------------------------------------------------------

def run(cmd, cwd=None, timeout=900, env=None, input_text=None) -> tuple[int, str]:
    full = None
    if env:
        import os
        full = {**os.environ, **env}
    try:
        p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=full,
                           capture_output=True, text=True, timeout=timeout, input=input_text)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"[timeout after {timeout}s: {' '.join(cmd)}]"
    except OSError as exc:
        return 127, f"cannot execute {cmd[0]}: {exc}"


def git(wt: Path, *args, timeout=180) -> tuple[int, str]:
    return run(["git", *args], cwd=wt, timeout=timeout)


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------

def is_test_file(path: str) -> bool:
    return path.endswith(("_test.go", ".test.ts", ".test.tsx", ".test.js", ".test.jsx"))


def is_doc_file(path: str) -> bool:
    return path.startswith("docs/") or path.endswith(".md") or path.endswith(".mdx")


def is_go_file(path: str) -> bool:
    return path.endswith(".go")


def go_package_dirs(files) -> list:
    """Unique ``./dir`` test targets for a set of repo-relative .go paths."""
    pkgs = []
    for f in files:
        if not is_go_file(f):
            continue
        d = str(Path(f).parent)
        target = "./" if d in (".", "") else f"./{d}"
        if target not in pkgs:
            pkgs.append(target)
    return pkgs


def changed_files(wt: Path, base: str) -> list:
    """Paths this attempt changed, committed or not, relative to ``base``."""
    files = set()
    for args in (("diff", "--name-only", f"{base}...HEAD"),
                 ("diff", "--name-only", "HEAD"),
                 ("ls-files", "--others", "--exclude-standard")):
        rc, out = git(wt, *args)
        if rc != 0:
            continue
        for ln in out.splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("[timeout"):
                files.add(ln)
    return sorted(files)


def split_changes(files) -> tuple[list, list]:
    """(implementation files, test files) - docs are neither."""
    impl, tests = [], []
    for f in files:
        if is_doc_file(f):
            continue
        if is_test_file(f):
            tests.append(f)
        else:
            impl.append(f)
    return impl, tests


# --------------------------------------------------------------------------
# item 1 - do the tests exercise the change?
# --------------------------------------------------------------------------

def removal_check(wt: Path, base: str, impl_files, test_cmds, env=None,
                  timeout: int = 900, test_files=None, test_only=False) -> dict:
    """Require a named behavioral assertion against a compilable mutant.

    First try the base behavior. For new APIs, zero one function while retaining
    its signature/imports/type-checked body. Build errors, panics, timeouts and
    tool failures never prove a test exercised production behavior. Original
    bytes are restored, including uncommitted work; the Git index is untouched.
    """
    impl_files = [p for p in impl_files if is_go_file(p)]
    if not impl_files:
        return {"ok": True, "reason": "no implementation files changed", "applicable": False}
    cmds = [shlex.split(str(c)) for c in (test_cmds or []) if str(c).strip().startswith("go test ")]
    if not cmds and any(is_go_file(p) for p in impl_files):
        cmds = [["go", "test", *go_package_dirs(impl_files)]]
    if not cmds:
        return {"ok": True, "reason": "no `go test` command listed for this unit",
                "applicable": False}
    snapshots = {}
    names = None
    if test_files is not None:
        names = set()
        for tf in test_files:
            names.update(re.findall(r"\bfunc\s+(Test\w+)\s*\(", (wt / tf).read_text()))
    results = []
    deadline = time.monotonic() + timeout
    def remaining():
        return max(0.01, deadline - time.monotonic())
    def restore():
        for path, content in snapshots.items():
            (wt / path).write_bytes(content)
    def judged(label):
        for c in cmds:
            if c[:2] != ["go", "test"] or any(v in (";", "&&", "||", "|", "-args") for v in c):
                results.append("unsupported focused test command")
                continue
            cmd = [*c[:2], "-json", "-count=1", *c[2:]]
            rc, out = run(cmd, cwd=wt, timeout=remaining(), env=env)
            proof = assertion_failure(rc, out, names)
            results.append(f"{label}: rc={rc}; {proof['reason']}")
            if proof["ok"]:
                return {"ok": True, "applicable": True, "reason": "a named test assertion rejects removed behavior",
                        "method": label, "failed_tests": proof["failed_tests"], "detail": "\n".join(results)[-3000:]}
        return None
    try:
        # The mutant must cause a failure; an already-red test proves nothing.
        for c in cmds:
            if c[:2] != ["go", "test"] or any(v in (";", "&&", "||", "|", "-args") for v in c):
                raise ValueError("unsupported focused test command")
            rc, out = run([*c[:2], "-json", "-count=1", *c[2:]], cwd=wt, timeout=remaining(), env=env)
            if rc:
                return {"ok": False, "applicable": True, "reason": "focused tests fail before behavior removal", "detail": out[-1200:]}
        for p in impl_files:
            target = wt / p
            if target.is_symlink() or not target.resolve().is_relative_to(wt.resolve()):
                raise ValueError("removal path escapes worktree")
            if target.exists():
                snapshots[p] = target.read_bytes()
        changed = False
        for p in snapshots:
            rc, original = git(wt, "show", f"{base}:{p}")
            if rc == 0 and original.encode() != snapshots[p]:
                (wt / p).write_text(original)
                changed = True
        if changed:
            proof = judged("base behavior")
            if proof:
                return proof
        restore()
        helper = Path(__file__).with_name("go-removal") / "main.go"
        candidates = []
        for p, content in snapshots.items():
            if not p.endswith(".go"):
                continue
            rc, out = run(["go", "run", str(helper)], cwd=wt, env=env,
                          timeout=remaining(), input_text=content.decode())
            if rc:
                results.append("Go mutation helper failed")
                continue
            functions = json.loads(out) or []
            if not test_only:
                rc, diff = git(wt, "diff", "--no-ext-diff", "--unified=0", base, "--", p)
                if rc:
                    raise ValueError("cannot identify changed Go functions")
                ranges = [(int(a), max(int(b or 1), 1)) for a, b in re.findall(r"^@@.*\+(\d+)(?:,(\d+))? @@", diff, re.M)]
                # An untracked source file is entirely new.
                tracked, _ = git(wt, "ls-files", "--error-unmatch", "--", p)
                if tracked:
                    ranges = [(1, len(content.splitlines()))]
                functions = [fn for fn in functions if any(start <= fn["end_line"] and start + size - 1 >= fn["line"] for start, size in ranges)]
            candidates.extend((fn.get("constructor", False), p, fn) for fn in functions)
        # At most eight individually tested mutations, inside one wall timeout.
        for _, p, fn in sorted(candidates, key=lambda row: (row[0], row[1], row[2]["index"]))[:8]:
            if time.monotonic() >= deadline:
                break
            restore()
            rc, mutant = run(["go", "run", str(helper), "-index", str(fn["index"])],
                             cwd=wt, env=env, timeout=remaining(), input_text=snapshots[p].decode())
            if rc:
                results.append("Go mutation helper failed")
                continue
            (wt / p).write_text(mutant)
            proof = judged(f"zero behavior: {p}:{fn['name']}")
            if proof:
                return proof
        return {"ok": False, "applicable": True, "reason": "tests do not exercise the change",
                "detail": "No compilable mutation produced a named assertion failure.\n" + "\n".join(results)[-2400:]}
    except (OSError, ValueError, TypeError) as exc:
        return {"ok": False, "applicable": True, "reason": "behavioral removal check unavailable",
                "detail": str(exc)[:600]}
    finally:
        restore()


def assertion_failure(rc: int, output: str, test_names=None) -> dict:
    """Only go-test JSON with a named test and an assertion location is proof."""
    fail = {"ok": False, "failed_tests": [], "reason": "no behavioral assertion failed"}
    if rc != 1:
        fail["reason"] = "tests passed" if rc == 0 else "test runner failed or timed out"
        return fail
    if re.search(r"(?im)\bpanic:|\bfatal error:|\bbuild failed\b|DATA RACE|\bundefined:", output):
        fail["reason"] = "compile, panic or infrastructure failure is not behavioral evidence"
        return fail
    assertions, failures = set(), set()
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            fail["reason"] = "test runner output is not complete JSON"
            return fail
        if not isinstance(event, dict):
            return fail
        name = event.get("Test")
        if not isinstance(event.get("Output", ""), str) or (name is not None and not isinstance(name, str)):
            return fail
        if name and event.get("Action") == "fail":
            failures.add(name)
        if name and re.search(r"(?m)^\s*[^\s/]+_test\.go:\d+:\s+\S", event.get("Output", "")):
            assertions.add(name)
        if event.get("Action") in ("build-fail", "build-output"):
            fail["reason"] = "compile failure is not behavioral evidence"
            return fail
    proven = sorted(name for name in assertions & failures
                    if test_names is None or name.split("/", 1)[0] in test_names)
    return {"ok": bool(proven), "failed_tests": proven,
            "reason": "named assertion failed" if proven else fail["reason"]}


def frontend_assertion_failure(rc, output):
    """A Node test assertion, not TypeError/module/compile failure, is proof."""
    failures = []
    if rc != 1:
        return False
    try:
        for line in output.splitlines():
            event = json.loads(line)
            if event.get("type") == "test:fail":
                failures.append(event)
    except (ValueError, AttributeError):
        return False
    # File-level suite failures may wrap the child assertion; the reporter
    # distinguishes those from failures in named tests.
    tests = [e for e in failures if e.get("failure_type") != "subtestsFailed"]
    return bool(tests) and all(e.get("assertion") is True for e in tests)


def frontend_removal_check(wt, impl_files, test_files, env=None, timeout=900):
    tests = [tf for tf in test_files if tf.startswith("frontend/tests/") and not tf.endswith(".go")]
    sources = [p for p in impl_files if p.startswith("frontend/src/") and p.endswith((".ts", ".tsx"))]
    for tf in tests:
        text = (wt / tf).read_text()
        for relative in re.findall(r'from\s+["\']([^"\']+)["\']', text):
            if not relative.startswith("."):
                continue
            target = (wt / tf).parent / relative
            for extension in (".ts", ".tsx"):
                p = target.with_suffix(extension).resolve()
                if p.is_relative_to((wt / "frontend/src").resolve()) and p.is_file():
                    sources.append(str(p.relative_to(wt.resolve())))
    if not tests and not sources:
        return {"ok": True, "applicable": False, "reason": "no frontend code/tests changed"}
    if not tests or not sources:
        return {"ok": False, "applicable": True, "reason": "frontend change lacks production behavioral tests"}
    frontend = wt / "frontend"
    module = frontend / "node_modules/typescript/lib/typescript.js"
    helper = Path(__file__).with_name("frontend-removal.mjs")
    reporter = Path(__file__).with_name("assertion-reporter.mjs")
    deadline = time.monotonic() + timeout
    original = {}
    def remaining():
        return max(.01, deadline - time.monotonic())
    def restore():
        for path, content in original.items():
            (wt / path).write_bytes(content)
    def test_current_source():
        with tempfile.TemporaryDirectory(prefix=".quality-compiled-", dir=frontend) as temporary:
            rc, out = run(["node", str(frontend / "node_modules/typescript/bin/tsc"), "-p", "tsconfig.json", "--outDir", temporary], cwd=frontend, timeout=remaining(), env=env)
            if rc:
                return rc, out
            emitted = [str(Path(temporary) / Path(tf).relative_to("frontend").with_suffix(".js")) for tf in tests]
            return run(["node", "--test", f"--test-reporter={reporter}", *emitted], cwd=frontend, timeout=remaining(), env=env)
    try:
        if not module.is_file():
            raise ValueError("pinned TypeScript dependency unavailable")
        for p in sorted(set(sources)):
            target = wt / p
            if target.is_symlink() or not target.resolve().is_relative_to(wt.resolve()):
                raise ValueError("frontend mutation path escapes worktree")
            original[p] = target.read_bytes()
        rc, out = test_current_source()
        if rc:
            return {"ok": False, "applicable": True, "reason": "frontend tests fail before behavior removal"}
        candidates = []
        for p, content in original.items():
            rc, out = run(["node", str(helper), str(module), p], cwd=frontend, timeout=remaining(), env=env, input_text=content.decode())
            if rc:
                raise ValueError("TypeScript mutation helper unavailable")
            candidates.extend((p, index) for index in json.loads(out))
        for p, index in candidates[:8]:
            if time.monotonic() >= deadline:
                break
            restore()
            rc, mutant = run(["node", str(helper), str(module), p, str(index)], cwd=frontend, timeout=remaining(), env=env, input_text=original[p].decode())
            if rc:
                continue
            (wt / p).write_text(mutant)
            # Compile to a fresh directory inside frontend so Node resolves the
            # pinned dependencies. Old emitted files can never prove a mutant.
            rc, out = test_current_source()
            if frontend_assertion_failure(rc, out):
                return {"ok": True, "applicable": True, "reason": "named frontend assertion rejects removed production behavior", "method": f"zero behavior: {p}"}
        return {"ok": False, "applicable": True, "reason": "no compilable frontend mutation produced an assertion failure"}
    except (OSError, ValueError, TypeError) as exc:
        return {"ok": False, "applicable": True, "reason": "frontend behavioral check unavailable", "detail": str(exc)[:400]}
    finally:
        restore()


# --------------------------------------------------------------------------
# item 2 - coverage on the changed files
# --------------------------------------------------------------------------

def parse_coverprofile(text: str, changed_files) -> dict:
    """Statement coverage for the changed files from a coverprofile.

    Profile lines look like
    ``github.com/x/y/internal/pkg/file.go:12.2,14.5 2 1``. The first field is
    the import path plus the repo-relative file; the numbers are statement count
    and times-executed. Returns ``{file: {covered, total}}`` for the changed
    files only.
    """
    want = {str(f) for f in changed_files}
    per: dict = {f: {"covered": 0, "total": 0} for f in want}
    for line in (text or "").splitlines():
        if not line or line.startswith("mode:"):
            continue
        head = line.split(" ", 1)[0]
        if ":" not in head:
            continue
        filepart, _range = head.rsplit(":", 1)
        nums = line.rsplit(" ", 2)[-2:]
        try:
            stmts = int(nums[0])
            count = int(nums[1])
        except (ValueError, IndexError):
            continue
        for f in want:
            if filepart == f or filepart.endswith("/" + f):
                per[f]["total"] += stmts
                if count > 0:
                    per[f]["covered"] += stmts
                break
    return per


def coverage_percent(per_file: dict) -> tuple[float, int, int]:
    covered = sum(v["covered"] for v in per_file.values())
    total = sum(v["total"] for v in per_file.values())
    if total == 0:
        return 0.0, 0, 0
    return 100.0 * covered / total, covered, total


def coverage_check(wt: Path, impl_files, test_cmds, env=None,
                   floor: float = COVERAGE_FLOOR, timeout: int = 900) -> dict:
    """Item 2: coverage over the changed packages must reach the floor.

    ``go test -coverprofile`` is run over the packages the unit's tests name
    (falling back to the changed packages). Coverage is measured on the changed
    implementation files only.
    """
    go_impl = [f for f in impl_files if is_go_file(f)]
    if not go_impl:
        return {"ok": True, "percent": None, "files": {},
                "reason": "no changed Go implementation files"}
    # Focused commands cannot omit another changed package.
    pkgs = list(dict.fromkeys(_packages_from_cmds(test_cmds) + go_package_dirs(go_impl)))
    with tempfile.TemporaryDirectory(prefix="phpretro-cover-") as temporary:
        profile = Path(temporary) / "profile.out"
        cmd = ["go", "test", "-count=1", "-covermode=count", f"-coverprofile={profile}", *pkgs]
        rc, out = run(cmd, cwd=wt, timeout=timeout, env=env)
        if rc != 0 or not profile.exists():
            return {"ok": False, "percent": None, "files": {}, "failure_kind": "unavailable",
                    "reason": f"coverage failed or profile missing (rc={rc})", "detail": out[-600:]}
        try:
            text = profile.read_text()
        except OSError:
            return {"ok": False, "percent": None, "files": {}, "failure_kind": "unavailable",
                    "reason": "coverage profile unreadable"}
    rows = text.splitlines()
    if not rows or rows[0] != "mode: count" or any(not re.fullmatch(r"\S+:\d+\.\d+,\d+\.\d+ \d+ \d+", row) for row in rows[1:] if row.strip()):
        return {"ok": False, "percent": None, "files": {}, "failure_kind": "unavailable", "reason": "coverage profile malformed"}
    per = parse_coverprofile(text, go_impl)
    pct, covered, total = coverage_percent(per)
    if total == 0:
        return {"ok": False, "percent": None, "files": per, "failure_kind": "unavailable",
                "reason": "no instrumented coverage for changed files"}
    missing = [f for f, value in per.items() if value["total"] == 0]
    if missing:
        return {"ok": False, "percent": None, "files": per, "failure_kind": "unavailable",
                "reason": "missing coverage for changed files: " + ", ".join(sorted(missing))}
    return {"ok": pct >= floor, "percent": round(pct, 1), "files": per,
            "covered": covered, "total": total,
            "failure_kind": "below_floor" if pct < floor else None,
            "reason": f"coverage on changed files {pct:.1f}% (floor {floor:.0f}%)"}


def _packages_from_cmds(test_cmds) -> list:
    pkgs = []
    for c in test_cmds or []:
        try:
            args = shlex.split(str(c))
        except ValueError:
            continue
        if args[:2] != ["go", "test"]:
            continue
        takes_value = {"-run", "-skip", "-timeout", "-count", "-parallel", "-tags", "-cpu", "-coverpkg"}
        skip = False
        for value in args[2:]:
            if skip:
                skip = False
                continue
            if value in takes_value:
                skip = True
            elif value.startswith(("./", "github.com/")) and value not in pkgs:
                pkgs.append(value)
    return pkgs


# --------------------------------------------------------------------------
# item 3 - evidence tie
# --------------------------------------------------------------------------

SOURCE_RE = re.compile(r"(?:docs/(?:evidence|roadmap|decisions)/[\w./-]+\.md|DECISIONS\.md|stage3-original-phpretro/[\w./-]+\.(?:php|html)|tests/golden/original/[\w./-]+\.(?:json|html|txt))")
LEGACY_IDS = {f"F{i}" for i in range(18, 30)} | {"F15", "F16", "F17", "F40"}


def feature_policy(unit: dict, test_file: str) -> str:
    """Evidence policy, not scheduling or scope. New security/theme contracts
    use the approved design even when original behavior is adjacent context.
    """
    if test_file.startswith(("internal/cache/", "internal/localization/", "internal/staff/", "internal/audit/")):
        return "new"
    if unit["id"].split("-", 1)[0] in LEGACY_IDS:
        return "legacy"
    if unit["id"].split("-", 1)[0] in {"F7", "F8", "F30", "F35", "F36", "F37", "F38"} or re.fullmatch(r"F(?:4[6-9]|5\d|60)", unit["id"]):
        return "new"
    return "production"


def _source_text(wt: Path, path: str, base=None) -> str | None:
    """Only non-secret acceptance artifacts inside the worktree. Approved
    specs must predate this candidate and be byte-identical to its base.
    """
    p = wt / path
    if p.is_symlink() or not p.resolve().is_relative_to(wt.resolve()) or not p.is_file():
        return None
    if any(part.startswith(".") or re.search(r"(?i)secret|credential|config|\.env", part) for part in Path(path).parts):
        return None
    if p.stat().st_size > 512_000:
        return None
    text = p.read_text(errors="replace")
    spec = path == "DECISIONS.md" or path.startswith(("docs/roadmap/", "docs/decisions/"))
    if spec and base:
        rc, approved = git(wt, "show", f"{base}:{path}")
        if rc or approved != text:
            return None
    return text


def source_supports(wt: Path, path: str, policy: str, base=None, seen=None) -> bool:
    seen = set() if seen is None else seen
    if path in seen or len(seen) >= 12:
        return False
    seen.add(path)
    text = _source_text(wt, path, base)
    if text is None:
        return False
    if path.startswith("tests/golden/original/"):
        # A retained body alone is not provenance: captures require a manifest.
        manifest = _source_text(wt, "tests/golden/original/manifest.json")
        if not manifest:
            return False
        try:
            entries = json.loads(manifest).get("captures", [])
            return any(e.get("path") == path and e.get("synthetic_seed") is True and e.get("original_source") for e in entries if isinstance(e, dict))
        except (ValueError, AttributeError, TypeError):
            return False
    if path.startswith("stage3-original-phpretro/"):
        return policy in ("legacy", "production")
    spec = path == "DECISIONS.md" or path.startswith(("docs/roadmap/", "docs/decisions/"))
    if spec and policy != "legacy":
        return True
    # Retained original path/hash inventory lets a source-backed research doc
    # link the original without copying its untracked (possibly secret) tree.
    if policy == "legacy":
        index = wt / "docs/stage3-original-phpretro-sha256.csv"
        if index.is_file() and not index.is_symlink():
            import csv
            with index.open(newline="") as fh:
                for row in csv.DictReader(fh):
                    original = row.get("Path", "").replace("\\", "/").split("stage3-original-phpretro/", 1)[-1]
                    if original.endswith(".php") and not re.search(r"(?i)config|secret|credential", original) and re.search(r"(?<![\w/])" + re.escape(original) + r"(?=[:`\s]|$)", text):
                        return True
    return any(source_supports(wt, ref, policy, base, seen) for ref in SOURCE_RE.findall(text) if ref != path)


def unit_doc_text(wt: Path, unit: dict) -> str:
    for cand in (unit.get("doc"), f"docs/units/{unit['id']}.md"):
        if not cand:
            continue
        p = wt / str(cand)
        if p.exists():
            return p.read_text(errors="replace")
    return ""


def evidence_check(wt: Path, unit: dict, test_files, base=None) -> dict:
    """Validate real citation paths and their acceptance provenance. Review
    still checks whether the assertion actually follows the cited statement.
    """
    doc = unit_doc_text(wt, unit)
    guessed = bool(GUESSED_RE.search(doc))
    unsourced = []
    cited = {}
    policies = {}
    for tf in test_files:
        policy = feature_policy(unit, tf)
        policies[tf] = policy
        text = (wt / tf).read_text(errors="replace")
        hits = sorted({path for path in SOURCE_RE.findall(text) if source_supports(wt, path, policy, base)})
        cited[tf] = hits
        if not hits:
            unsourced.append(tf)
    ok = not unsourced
    if not unsourced:
        reason = "every changed test cites a retained acceptance source for its feature type"
    else:
        reason = "missing retained acceptance source (guessed labels do not waive review): " + ", ".join(unsourced)
    return {"ok": ok, "unsourced": unsourced, "cited": cited,
            "guessed": guessed, "policies": policies, "reason": reason}


# --------------------------------------------------------------------------
# aggregate
# --------------------------------------------------------------------------

def evaluate(wt: Path, base: str, unit: dict, env=None,
             floor: float = COVERAGE_FLOOR) -> dict:
    """Run items 1-3 for one attempt.

    Returns ``{"ok", "reason", "checks", "coverage", "fidelity"}``. ``reason``
    names the first failing check; all checks are reported either way.
    """
    files = changed_files(wt, base)
    impl, tests = split_changes(files)
    checks = {}
    failures = []

    # Test-only changes must also reject a mutation of their production package.
    probes = [f for f in impl if is_go_file(f)]
    test_only = not probes and bool(tests)
    if test_only:
        for tf in tests:
            probes.extend(str(p.relative_to(wt)) for p in (wt / tf).parent.glob("*.go") if not is_test_file(str(p)))
    r1 = removal_check(wt, base, sorted(set(probes)), unit.get("tests"), env=env,
                       test_files=[tf for tf in tests if tf.endswith("_test.go")], test_only=test_only)
    frontend_proof = frontend_removal_check(wt, impl, tests, env=env)
    checks["frontend_tests_exercise_change"] = frontend_proof
    if not frontend_proof["ok"]:
        failures.append(("frontend tests do not exercise the change", frontend_proof))
    checks["tests_exercise_change"] = r1
    if not r1["ok"]:
        failures.append(("tests do not exercise the change", r1))

    r3 = evidence_check(wt, unit, tests, base=base)
    checks["evidence"] = r3
    if not r3["ok"]:
        failures.append(("tests do not cite their evidence", r3))

    r2 = coverage_check(wt, impl, unit.get("tests"), env=env, floor=floor)
    doc = unit_doc_text(wt, unit)
    exempt = COVERAGE_EXEMPT_RE.search(doc)
    if exempt:
        r2["exempt_reason"] = exempt.group(1).strip()
    checks["coverage"] = r2
    if not r2["ok"]:
        if exempt and r2.get("failure_kind") == "below_floor":
            r2["ok"] = True
            r2["reason"] += f" - accepted: {r2['exempt_reason']}"
        else:
            failures.append((f"coverage on changed files below {floor:.0f}%", r2))

    fidelity = "guessed" if r3["guessed"] else "evidence"
    if failures:
        parts = []
        for label, res in (("tests_exercise_change", r1), ("evidence", r3),
                           ("frontend_tests_exercise_change", frontend_proof), ("coverage", r2)):
            if not res.get("ok"):
                parts.append(f"{label}:\n{res.get('detail') or res.get('reason')}")
        return {"ok": False, "reason": failures[0][0], "failures": [f[0] for f in failures],
                "checks": checks, "coverage": r2.get("percent"), "fidelity": fidelity,
                "detail": "\n\n".join(parts)[:3000]}
    return {"ok": True, "reason": "quality checks passed", "failures": [],
            "checks": checks, "coverage": r2.get("percent"), "fidelity": fidelity,
            "detail": ""}


# --------------------------------------------------------------------------
# selftest
# --------------------------------------------------------------------------

def selftest() -> int:
    per = parse_coverprofile("""mode: count
github.com/PapaBill1234/phpretro-preservation/internal/registration/registration.go:10.2,12.4 2 1
github.com/PapaBill1234/phpretro-preservation/internal/registration/registration.go:14.2,16.4 2 0
github.com/PapaBill1234/phpretro-preservation/internal/other/other.go:1.1,2.2 4 4
""", ["internal/registration/registration.go"])
    got = per["internal/registration/registration.go"]
    assert got == {"covered": 2, "total": 4}, got
    pct, cov, tot = coverage_percent(per)
    assert (pct, cov, tot) == (50.0, 2, 4), (pct, cov, tot)

    # an unrelated file's coverage must not leak into the changed file
    assert "internal/other/other.go" not in per

    ok = parse_coverprofile("mode: count\n", ["a.go"])
    assert ok == {"a.go": {"covered": 0, "total": 0}}, ok
    assert coverage_percent(ok) == (0.0, 0, 0)

    assert go_package_dirs(["internal/a/x.go", "internal/a/y_test.go", "internal/b/z.go"]) == \
        ["./internal/a", "./internal/b"]

    assert is_test_file("internal/a/x_test.go") and not is_test_file("internal/a/x.go")
    assert is_doc_file("docs/units/F1.md") and not is_doc_file("internal/a/x.go")
    impl, tests = split_changes(["internal/a/x.go", "internal/a/x_test.go", "docs/units/F1.md"])
    assert impl == ["internal/a/x.go"] and tests == ["internal/a/x_test.go"], (impl, tests)

    assert _packages_from_cmds(["go test ./internal/a/...", "bash scripts/check.sh"]) == \
        ["./internal/a/..."]
    assert COVERAGE_EXEMPT_RE.search("coverage-exempt: pure wiring, no branches")
    assert not COVERAGE_EXEMPT_RE.search("some prose about coverage")
    assert GUESSED_RE.search("fidelity: guessed")

    # evaluate() aggregate: a failing removal check names the reason and builds
    # a detail string without crashing on the three checks.
    import tempfile as _tf
    from pathlib import Path as _P
    wt = _P(_tf.mkdtemp(prefix="q-selftest-"))
    (wt / "internal").mkdir()
    (wt / "internal" / "x.go").write_text("package x\n")
    (wt / "internal" / "x_test.go").write_text("package x\n")
    (wt / "docs" / "units").mkdir(parents=True)
    (wt / "docs" / "units" / "F1.md").write_text("# F1\n")
    import subprocess as _sp
    _sp.run(["git", "init", "-q"], cwd=wt)
    _sp.run(["git", "add", "-A"], cwd=wt)
    _sp.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "b"], cwd=wt)
    # no changed files vs HEAD => no implementation, checks pass trivially
    res = evaluate(wt, "HEAD", {"id": "F1", "tests": ["go test ./internal/..."]})
    assert res["ok"] is True, res
    assert res["fidelity"] == "evidence", res
    print("quality selftest OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="quality safeguards for a unit attempt")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    ap.error("nothing to do (try --selftest)")
    return 2


if __name__ == "__main__":
    sys.exit(main())

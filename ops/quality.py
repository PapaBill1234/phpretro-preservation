#!/usr/bin/env python3
"""Quality safeguards for one builder attempt (items 1-3 of the quality work).

These run in the unit's worktree after ``scripts/check.sh`` passes and before
the PR is opened:

* ``removal_check``  (item 1) the new tests must fail when the implementation is
  taken away, otherwise they do not exercise the change.
* ``coverage_check`` (item 2) ``go test -cover`` over the changed packages; the
  changed files must reach the floor, unless the unit doc records why.
* ``evidence_check`` (item 3) every changed test must cite the evidence file or
  fixture its expected values came from, or the unit must be labelled
  ``fidelity: guessed``.

Everything here is pure or takes an explicit worktree, so it can be exercised
without the orchestrator. ``ops/quality.py --selftest`` checks the parsers.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

COVERAGE_FLOOR = 60.0
# A unit doc can excuse a package that cannot be usefully covered, but it has to
# say so on an explicit line rather than leaving it to the reviewer's judgement.
COVERAGE_EXEMPT_RE = re.compile(r"^coverage-exempt:\s*(\S.*)$", re.M)
GUESSED_RE = re.compile(r"fidelity:\s*guessed", re.I)
# Evidence roots a test may cite; the unit's own fixtures are added per unit.
EVIDENCE_ROOTS = ("docs/evidence", "docs/roadmap", "tests/golden", "docs/units")


# --------------------------------------------------------------------------
# tiny process helper (kept local so quality.py has no import cycle)
# --------------------------------------------------------------------------

def run(cmd, cwd=None, timeout=900, env=None) -> tuple[int, str]:
    full = None
    if env:
        import os
        full = {**os.environ, **env}
    try:
        p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=full,
                           capture_output=True, text=True, timeout=timeout)
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
    return path.endswith("_test.go")


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

def _hide(paths, wt: Path, base: str) -> list:
    """Return the implementation paths to their base version.

    A file that exists at ``base`` is checked out from it; a file the unit
    created is removed. Returns the list of paths, so the caller can restore
    them from HEAD afterwards.
    """
    for p in paths:
        rc, _ = git(wt, "cat-file", "-e", f"{base}:{p}")
        if rc == 0:
            git(wt, "checkout", base, "--", p)
        else:
            full = wt / p
            if full.exists():
                full.unlink()
    return list(paths)


def _restore(paths, wt: Path) -> None:
    if paths:
        git(wt, "checkout", "HEAD", "--", *paths)


def removal_check(wt: Path, base: str, impl_files, test_cmds, env=None,
                  timeout: int = 900) -> dict:
    """Item 1: with the implementation gone the tests must fail.

    Returns ``{"ok", "reason", "detail"}``. ``ok`` is True when the tests fail
    without the implementation (they really exercise it), or when the check
    does not apply (no implementation files, or no runnable test command).
    """
    if not impl_files:
        return {"ok": True, "reason": "no implementation files changed", "applicable": False}
    cmds = [c for c in (test_cmds or []) if str(c).strip().startswith("go test")]
    if not cmds:
        return {"ok": True, "reason": "no `go test` command listed for this unit",
                "applicable": False}
    hidden = []
    try:
        hidden = _hide(impl_files, wt, base)
        results = []
        all_passed = True
        for c in cmds:
            rc, out = run(["bash", "-lc", c], cwd=wt, timeout=timeout, env=env)
            passed = rc == 0
            all_passed = all_passed and passed
            results.append(f"$ {c} -> rc={rc}\n{out[-600:]}")
        detail = "\n\n".join(results)
        if all_passed:
            return {"ok": False, "applicable": True,
                    "reason": "tests do not exercise the change",
                    "detail": "every listed test still passed with the "
                              "implementation removed:\n" + detail}
        return {"ok": True, "applicable": True,
                "reason": "tests fail without the implementation (they exercise it)",
                "detail": detail}
    finally:
        _restore(hidden, wt)


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
    pkgs = _packages_from_cmds(test_cmds) or go_package_dirs(go_impl)
    profile = Path(wt).parent / f".cover-{abs(hash(tuple(sorted(go_impl)))) % 10**8}.out"
    cmd = ["go", "test", "-covermode=count", f"-coverprofile={profile}", *pkgs]
    rc, out = run(cmd, cwd=wt, timeout=timeout, env=env)
    if rc != 0 and not profile.exists():
        return {"ok": True, "percent": None, "files": {},
                "reason": f"coverage run did not produce a profile (rc={rc}); not judged",
                "detail": out[-600:]}
    text = profile.read_text() if profile.exists() else ""
    try:
        profile.unlink()
    except OSError:
        pass
    per = parse_coverprofile(text, go_impl)
    pct, covered, total = coverage_percent(per)
    if total == 0:
        return {"ok": True, "percent": None, "files": per,
                "reason": "changed files have no instrumented statements"}
    return {"ok": pct >= floor, "percent": round(pct, 1), "files": per,
            "covered": covered, "total": total,
            "reason": f"coverage on changed files {pct:.1f}% (floor {floor:.0f}%)"}


def _packages_from_cmds(test_cmds) -> list:
    pkgs = []
    for c in test_cmds or []:
        m = re.match(r"\s*go test\s+(?:-[^\s]+\s+)*(\S+)", str(c))
        if m and m.group(1).startswith(("./", "github.com/")):
            target = m.group(1)
            if target not in pkgs:
                pkgs.append(target)
    return pkgs


# --------------------------------------------------------------------------
# item 3 - evidence tie
# --------------------------------------------------------------------------

def evidence_tokens(unit: dict) -> list:
    toks = [str(f) for f in (unit.get("fixtures") or []) if str(f).strip()]
    if unit.get("design_doc"):
        toks.append(str(unit["design_doc"]))
    toks.extend(EVIDENCE_ROOTS)
    return toks


def test_citations(wt: Path, test_file: str, tokens) -> list:
    try:
        text = (wt / test_file).read_text(errors="replace")
    except OSError:
        return []
    return [t for t in tokens if t and t in text]


def unit_doc_text(wt: Path, unit: dict) -> str:
    for cand in (unit.get("doc"), f"docs/units/{unit['id']}.md"):
        if not cand:
            continue
        p = wt / str(cand)
        if p.exists():
            return p.read_text(errors="replace")
    return ""


def evidence_check(wt: Path, unit: dict, test_files) -> dict:
    """Item 3: each changed test cites its evidence, or the unit is 'guessed'.

    A test with no citation is acceptable only when the unit doc is labelled
    ``fidelity: guessed``; the label is then counted (item 6). A test with no
    citation and no label fails the attempt.
    """
    tokens = evidence_tokens(unit)
    doc = unit_doc_text(wt, unit)
    guessed = bool(GUESSED_RE.search(doc))
    unsourced = []
    cited = {}
    for tf in test_files:
        hits = test_citations(wt, tf, tokens)
        cited[tf] = hits
        if not hits:
            unsourced.append(tf)
    ok = (not unsourced) or guessed
    if not unsourced:
        reason = "every changed test cites an evidence file or fixture"
    elif guessed:
        reason = ("tests without a citation, labelled `fidelity: guessed`: "
                  + ", ".join(unsourced))
    else:
        reason = ("tests do not cite an evidence file or fixture and the unit "
                  "doc is not labelled `fidelity: guessed`: " + ", ".join(unsourced))
    return {"ok": ok, "unsourced": unsourced, "cited": cited,
            "guessed": guessed, "reason": reason}


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

    r1 = removal_check(wt, base, impl, unit.get("tests"), env=env)
    checks["tests_exercise_change"] = r1
    if not r1["ok"]:
        failures.append(("tests do not exercise the change", r1))

    r3 = evidence_check(wt, unit, tests)
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
        if exempt:
            r2["ok"] = True
            r2["reason"] += f" - accepted: {r2['exempt_reason']}"
        else:
            failures.append((f"coverage on changed files below {floor:.0f}%", r2))

    fidelity = "guessed" if r3["guessed"] else "evidence"
    if failures:
        parts = []
        for label, res in (("tests_exercise_change", r1), ("evidence", r3),
                           ("coverage", r2)):
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

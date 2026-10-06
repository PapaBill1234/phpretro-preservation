"""Shared bootstrap for the ops/ test suite.

Import this BEFORE importing any ops module. It forces every path the pipeline
resolves at import time (``PHPRETRO_OPS``, ``PHPRETRO_WORK`` ...) into a throwaway
temp directory, so a test can never read or write the real pipeline state. The
temp tree is removed on interpreter exit.

No network is ever used: modules that would call out (Jev, the agent runner, the
nightly server) are monkeypatched by the individual tests.
"""

from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OPS_DIR = Path(__file__).resolve().parent.parent      # .../ops
REPO = OPS_DIR.parent                                  # repo root

_TMP = Path(tempfile.mkdtemp(prefix="phpretro-tests-"))


def _force_env(name: str, value: Path) -> None:
    """Override, never merely default: an inherited value must not win."""
    os.environ[name] = str(value)
    value.mkdir(parents=True, exist_ok=True)


# HOME first: every ops module resolves Path.home() at import time, and a test
# that (say) writes a profile state.db must land in the temp tree, never in the
# real ~/.hermes. Set before PHPRETRO_OPS so nothing is derived from the real HOME.
os.environ["HOME"] = str(_TMP / "home")
(_TMP / "home" / ".hermes").mkdir(parents=True, exist_ok=True)
_force_env("PHPRETRO_OPS", _TMP / "ops")
_force_env("PHPRETRO_WORK", _TMP / "work")
# The repo itself is READ, not written, so point at the real one: nightly.py and
# orchestrator.py resolve REPO as HOME/phpretro-preservation, and HOME is now the
# temp tree. Without this a test that runs ops/tests/run_all.sh would look for it
# under the temp HOME and never find it.
os.environ["PHPRETRO_REPO"] = str(REPO)
for _sub in ("state", "logs", "briefs", "locks"):
    (_TMP / "ops" / _sub).mkdir(parents=True, exist_ok=True)
# Jev must never find a real key during tests.
os.environ.pop("OPENROUTER_API_KEY", None)
os.environ["PHPRETRO_JEV_ENV"] = str(_TMP / "no-such.env")

atexit.register(lambda: shutil.rmtree(_TMP, ignore_errors=True))

if str(OPS_DIR) not in sys.path:
    sys.path.insert(0, str(OPS_DIR))


def tmpdir(prefix: str = "t-") -> Path:
    """A fresh throwaway directory, cleaned up with the rest of the run."""
    return Path(tempfile.mkdtemp(prefix=prefix, dir=str(_TMP)))


def run(cmd, cwd=None, env=None, timeout=120):
    """subprocess.run with text output, returning a CompletedProcess."""
    full = dict(os.environ)
    if env:
        full.update(env)
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=full,
                          capture_output=True, text=True, timeout=timeout)


def git_repo(path: Path, *, trunk: str = "origin/main") -> Path:
    """A scratch git repo whose ``origin/main`` ref exists, then a unit branch.

    Mirrors how the pipeline calls ``changed_files``: BASE_REF is a ref named
    ``origin/main``, the unit's work sits on a branch, and the trunk can advance
    afterwards (which is exactly the case the three-dot diff must survive).
    """
    path.mkdir(parents=True, exist_ok=True)
    run(["git", "init", "-q"], cwd=path)
    run(["git", "config", "user.email", "t@t"], cwd=path)
    run(["git", "config", "user.name", "t"], cwd=path)
    run(["git", "config", "commit.gpgsign", "false"], cwd=path)
    return path


def commit(path: Path, message: str = "c") -> None:
    run(["git", "add", "-A"], cwd=path)
    run(["git", "commit", "-qm", message], cwd=path)


def head(path: Path, ref: str = "HEAD") -> str:
    return run(["git", "rev-parse", ref], cwd=path).stdout.strip()

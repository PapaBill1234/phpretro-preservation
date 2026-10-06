#!/usr/bin/env bash
# ops/tests/run_all.sh -- the ops/ regression suite.
#
# Plain unittest, stdlib only, no network. Every test runs with PHPRETRO_OPS and
# PHPRETRO_WORK forced into a throwaway temp tree (see harness.py), so the real
# pipeline state is never read or written.
#
# Exit status: 0 only when every test module passes. The orchestrator --selftest
# and the nightly self-check both call this, and a non-zero exit is a failed
# self-check for alerting.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ops="$(cd "$here/.." && pwd)"

PY="${PHPRETRO_TEST_PYTHON:-python3}"

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "ops/tests: no python3 on PATH" >&2
  exit 2
fi

echo "ops/tests: running (python: $($PY -V 2>&1))"
# -t so `import harness` resolves to this directory, -b so a failure prints its
# own traceback, -v so the transcript names every test.
"$PY" -m unittest discover -s "$here" -t "$here" -p 'test_*.py' -b -v
rc=$?
if [ "$rc" -eq 0 ]; then
  echo "ops/tests: PASS"
else
  echo "ops/tests: FAIL (rc=$rc)" >&2
fi
exit "$rc"

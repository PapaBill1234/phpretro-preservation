#!/usr/bin/env bash
# scripts/check.sh -- the ONLY merge gate for this repository.
#
# Runs the same checks as .github/workflows/go-security.yml (the `foundation`
# job) plus the static analysis the pipeline requires. Any failure exits
# non-zero; nothing else decides whether a unit may merge.
#
# Toolchain is pinned to .go-version, the same pin CI uses, so a local pass
# means the same thing as a CI pass.
#
# Usage: scripts/check.sh
set -uo pipefail

cd "$(dirname "$0")/.." || exit 2
ROOT="$(pwd)"

GO_PIN="$(tr -d '[:space:]' < "$ROOT/.go-version" 2>/dev/null || true)"
[ -n "$GO_PIN" ] && export GOTOOLCHAIN="${GOTOOLCHAIN:-go$GO_PIN}"

TOOLBIN="${PHPRETRO_TOOLBIN:-$HOME/.local/go-bin}"
export PATH="$TOOLBIN:$PATH"

fail=0
note() { printf '\n== %s\n' "$1"; }
bad()  { printf 'FAIL: %s\n' "$1"; fail=1; }

ensure_tool() { # name version module-path
  command -v "$1" >/dev/null 2>&1 && return 0
  note "installing $1@$2"
  mkdir -p "$TOOLBIN"
  GOBIN="$TOOLBIN" go install "$3@$2" >/dev/null 2>&1 && return 0
  bad "cannot install $1@$2 (need it on PATH or a working module proxy)"
}

ensure_tool staticcheck v0.6.1 honnef.co/go/tools/cmd/staticcheck
ensure_tool gosec v2.21.4 github.com/securego/gosec/v2/cmd/gosec
ensure_tool govulncheck v1.1.4 golang.org/x/vuln/cmd/govulncheck

# --- foundation checks (mirror the `foundation` CI job) ---------------------
note "gofmt"
unformatted="$(git ls-files -z -- '*.go' | xargs -0 -r gofmt -l)"
[ -z "$unformatted" ] || { printf '%s\n' "$unformatted"; bad "gofmt: unformatted files"; }

note "go build ./..."
go build ./... || bad "go build"

note "go vet ./..."
go vet ./... || bad "go vet"

note "go test ./..."
go test ./... || bad "go test"

note "go test -race ./..."
go test -race ./... || bad "go test -race"

# --- required static analysis ----------------------------------------------
note "staticcheck ./..."
staticcheck ./... || bad "staticcheck"

note "gosec ./..."
gosec -quiet -fmt=text ./... || bad "gosec"

note "govulncheck ./..."
govulncheck ./... || bad "govulncheck"

if [ "$fail" -ne 0 ]; then
  printf '\nCHECK FAILED\n'
  exit 1
fi
printf '\nCHECK PASSED\n'
exit 0

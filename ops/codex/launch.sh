#!/bin/bash
set -euo pipefail
export CODEX_HOME=/home/ubuntu/phpretro-codex/private
exec /home/ubuntu/phpretro-codex/cli/node_modules/.bin/codex "$@"

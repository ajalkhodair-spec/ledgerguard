#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)

"$SCRIPT_DIR/run_foundry_invariants.sh"

if [ ! -f "$ROOT_DIR/results/security/foundry_coverage.txt" ]; then
  printf 'forge coverage not run: requires accessible Docker/Foundry environment\n' > "$ROOT_DIR/results/security/foundry_coverage.txt"
fi

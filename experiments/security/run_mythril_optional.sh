#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"
mkdir -p results/security

if ! command -v myth >/dev/null 2>&1; then
  printf 'mythril not run: tool is not installed\n' > results/security/mythril_report.txt
  exit 0
fi

myth analyze contracts/src/FirmwareRegistry.sol > results/security/mythril_report.txt 2>&1 || true

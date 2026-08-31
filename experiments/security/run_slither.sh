#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"
mkdir -p results/security

if ! command -v slither >/dev/null 2>&1; then
  printf 'slither not run: tool is not installed\n' > results/security/slither_report.txt
  exit 0
fi

slither contracts > results/security/slither_report.txt 2>&1 || true

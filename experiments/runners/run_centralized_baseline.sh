#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

source experiments/runners/common.sh
ensure_result_dirs

PYTHON_BIN=${PYTHON_BIN:-python3}
REPETITIONS=${LEDGERGUARD_STRONG_REPETITIONS:-30}

"$PYTHON_BIN" experiments/baseline/centralized_ota_controller/controller.py \
  --repetitions "$REPETITIONS" \
  --csv results/csv/centralized_baseline.csv \
  --raw results/raw/centralized_baseline

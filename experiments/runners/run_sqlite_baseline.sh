#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

source experiments/runners/common.sh
ensure_result_dirs

PYTHON_BIN=${PYTHON_BIN:-python3}
REPETITIONS=${LEDGERGUARD_STRONG_REPETITIONS:-30}

mkdir -p results/raw/sqlite_baseline results/csv results/validation

set +e
"$PYTHON_BIN" experiments/baseline/sqlite_ota_controller/controller.py \
  --repetitions "$REPETITIONS" \
  --csv results/csv/sqlite_baseline_timing.csv \
  --raw results/raw/sqlite_baseline
RC=$?
set -e

if [ "$RC" -eq 0 ]; then
  write_status_json results/validation/sqlite_baseline_status.json executed "SQLite baseline completed with durable database and raw JSONL evidence."
else
  write_status_json results/validation/sqlite_baseline_status.json failed "SQLite baseline exited with code $RC."
fi

exit "$RC"

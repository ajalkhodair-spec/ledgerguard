#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3}

# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

cd "$ROOT_DIR"

copy_existing_results_to_archive

"$PYTHON_BIN" "$ROOT_DIR/experiments/analysis/audit_repo.py"
"$SCRIPT_DIR/run_sqlite_baseline.sh"
"$SCRIPT_DIR/run_governance_repetitions.sh"
"$SCRIPT_DIR/run_distributed_besu.sh"
"$SCRIPT_DIR/run_network_profiles.sh"
"$SCRIPT_DIR/run_edge_cache.sh"
"$SCRIPT_DIR/run_accountability_ablation.sh"
"$SCRIPT_DIR/run_resource_monitoring.sh"
"$SCRIPT_DIR/run_hil_optional.sh"

"$SCRIPT_DIR/run_security_checks.sh"
"$SCRIPT_DIR/run_adversarial_suite.sh"

"$PYTHON_BIN" "$ROOT_DIR/experiments/analysis/aggregate_results.py" --results-dir "$ROOT_DIR/results"
"$PYTHON_BIN" "$ROOT_DIR/experiments/analysis/make_workbook.py" --results-dir "$ROOT_DIR/results"
"$PYTHON_BIN" "$ROOT_DIR/experiments/analysis/make_tables.py" --results-dir "$ROOT_DIR/results" --out-dir "$ROOT_DIR/paper_assets/tables"
"$PYTHON_BIN" "$ROOT_DIR/experiments/analysis/make_figures.py" --results-dir "$ROOT_DIR/results" --out-dir "$ROOT_DIR/paper_assets/figures"
"$PYTHON_BIN" "$ROOT_DIR/experiments/analysis/write_text_outputs.py" --results-dir "$ROOT_DIR/results"
"$PYTHON_BIN" "$ROOT_DIR/experiments/analysis/validate_results.py" --results-dir "$ROOT_DIR/results"

echo "Strong evaluation outputs are available under $ROOT_DIR/results and $ROOT_DIR/paper_assets."

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

MODE=""
RESUME=false
for arg in "$@"; do
  case "$arg" in
    --smoke|--full|--analysis-only) MODE=${arg#--} ;;
    --resume) RESUME=true ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done
if [ -z "$MODE" ]; then
  echo "usage: $0 --smoke|--full|--analysis-only [--resume]" >&2
  exit 2
fi

PYTHON_BIN=${PYTHON_BIN:-python3}
FORGE_BIN=${FORGE_BIN:-forge}
CAST_BIN=${CAST_BIN:-cast}
BESU_NATIVE_BIN=${BESU_NATIVE_BIN:-besu}
SOLC_BIN=${SOLC_BIN:-solc}
SLITHER_BIN=${SLITHER_BIN:-slither}
export PYTHONPATH="${PYTHONPATH:-}:$ROOT_DIR"

require_command() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing required command: $1" >&2; exit 1; }
}

environment_doctor() {
  require_command "$PYTHON_BIN"
  require_command git
  require_command "$FORGE_BIN"
  require_command "$CAST_BIN"
  require_command "$SOLC_BIN"
  if [ "$MODE" = full ]; then
    require_command docker
    require_command jq
    require_command "$BESU_NATIVE_BIN"
    require_command "$SLITHER_BIN"
    docker compose version >/dev/null
  fi
  mkdir -p results/reviewer_revision/validation
  {
    echo "generated_at_utc=$($PYTHON_BIN -c 'from datetime import datetime,timezone; print(datetime.now(timezone.utc).isoformat())')"
    echo "python=$($PYTHON_BIN --version 2>&1)"
    echo "forge=$($FORGE_BIN --version | head -1)"
    echo "cast=$($CAST_BIN --version | head -1)"
    if [ "$MODE" = full ]; then
      echo "besu=$($BESU_NATIVE_BIN --version 2>&1 | head -1)"
      echo "docker=$(docker --version)"
    fi
  } > results/reviewer_revision/validation/reproduction_environment.txt
}

run_smoke() {
  find experiments runner scripts -name '*.py' -print0 | xargs -0 "$PYTHON_BIN" -m py_compile
  bash -n poc
  find experiments scripts -name '*.sh' -print0 | xargs -0 -n1 bash -n
  "$PYTHON_BIN" experiments/reviewer_revision/run_python_security.py
  "$FORGE_BIN" test --root contracts --offline --use "$SOLC_BIN" -vv
  if [ -d results_sample ]; then
    "$PYTHON_BIN" experiments/reviewer_revision/validate_public_sample.py
  fi
}

run_analysis() {
  "$PYTHON_BIN" experiments/reviewer_revision/analyze_timing.py
  "$PYTHON_BIN" experiments/reviewer_revision/analyze_fleet.py
  "$PYTHON_BIN" experiments/reviewer_revision/analyze_receipt_size.py
  "$PYTHON_BIN" experiments/reviewer_revision/analyze_block_period.py
  "$PYTHON_BIN" experiments/reviewer_revision/summarize_final_distributions.py
  "$PYTHON_BIN" experiments/reviewer_revision/run_python_security.py
  "$PYTHON_BIN" experiments/reviewer_revision/sanitize_evidence.py
  "$PYTHON_BIN" experiments/reviewer_revision/analyze_coverage.py
  "$PYTHON_BIN" experiments/reviewer_revision/summarize_slither.py
  "$PYTHON_BIN" experiments/reviewer_revision/build_revision_closures.py
  if [ -f results/reviewer_revision/raw/concurrency/rpc_races.jsonl ] && "$CAST_BIN" block-number --rpc-url http://127.0.0.1:8545 >/dev/null 2>&1; then
    "$PYTHON_BIN" experiments/reviewer_revision/analyze_concurrency.py --cast "$CAST_BIN"
  fi
  MPLBACKEND=Agg "$PYTHON_BIN" experiments/reviewer_revision/generate_figures.py
  "$PYTHON_BIN" experiments/reviewer_revision/update_revision_metadata.py
  "$PYTHON_BIN" experiments/reviewer_revision/validate_reviewer_revision.py
  "$PYTHON_BIN" experiments/reviewer_revision/sanitize_evidence.py
  "$PYTHON_BIN" experiments/reviewer_revision/validate_evidence_freeze.py
  "$PYTHON_BIN" experiments/reviewer_revision/update_revision_metadata.py
  "$PYTHON_BIN" experiments/reviewer_revision/generate_evidence_package.py
  "$PYTHON_BIN" experiments/reviewer_revision/validate_public_sample.py
}

run_full() {
  if [ -e results/reviewer_revision/raw/besu_v2_final/deployment.json ] && [ "$RESUME" != true ]; then
    echo "reviewer-revision output exists; use --resume or archive it before a full rerun" >&2
    exit 1
  fi
  if [ ! -f .env ]; then
    cp .env.example .env
  fi
  if [ "$RESUME" != true ] || [ ! -f out/release_metadata.json ]; then
    ./poc run
  fi
  set -a
  source .env
  set +a
  export LEDGERGUARD_DEPLOYER_PRIVATE_KEY="$VENDOR_PRIVATE_KEY"
  export LEDGERGUARD_SECURITY_PRIVATE_KEY="$SECURITY_PRIVATE_KEY"
  export LEDGERGUARD_REGULATOR_PRIVATE_KEY="$REGULATOR_PRIVATE_KEY"
  export LEDGERGUARD_OPERATOR_PRIVATE_KEY="$OPERATOR_PRIVATE_KEY"
  export LEDGERGUARD_AUDITOR_PRIVATE_KEY="$AUDITOR_PRIVATE_KEY"
  export FORGE_BIN CAST_BIN

  [ -f results/reviewer_revision/raw/besu_v2_final/deployment.json ] || "$PYTHON_BIN" experiments/reviewer_revision/deploy_v2.py
  if [ -f results/reviewer_revision/csv/besu_v2_final_timing.csv ]; then
    "$PYTHON_BIN" experiments/reviewer_revision/run_besu_v2_repetitions.py --resume
  else
    "$PYTHON_BIN" experiments/reviewer_revision/run_besu_v2_repetitions.py
  fi
  [ -f results/reviewer_revision/csv/http_sqlite_v2_timing.csv ] || "$PYTHON_BIN" experiments/reviewer_revision/baseline/http_sqlite_controller.py
  [ -f results/reviewer_revision/csv/aggregation_completeness_tests.csv ] || "$PYTHON_BIN" experiments/reviewer_revision/run_receipt_evaluation.py
  [ -f results/reviewer_revision/csv/independent_witness_tests.csv ] || "$PYTHON_BIN" experiments/reviewer_revision/run_independent_witness.py
  [ -f results/reviewer_revision/csv/fleet_multiseed_runs.csv ] || "$PYTHON_BIN" experiments/reviewer_revision/run_fleet_multiseed.py
  [ -f results/reviewer_revision/csv/protocol_compatibility_tests.csv ] || "$PYTHON_BIN" experiments/reviewer_revision/generate_protocol_compatibility.py
  [ -f results/reviewer_revision/csv/concurrency_and_replay_tests.csv ] || "$PYTHON_BIN" experiments/reviewer_revision/run_concurrency_rpc.py
  if [ ! -f results/reviewer_revision/csv/accountability_measured.csv ] || \
     [ ! -f results/reviewer_revision/csv/accountability_path_totals.csv ] || \
     [ ! -f results/reviewer_revision/csv/accountability_path_statistics.csv ]; then
    "$PYTHON_BIN" experiments/reviewer_revision/run_accountability_v2.py
  fi
  [ -f results/reviewer_revision/raw/besu_v2_final/governance_lifecycle_transactions.jsonl ] || \
    "$PYTHON_BIN" experiments/reviewer_revision/run_governance_gas_extensions.py
  "$PYTHON_BIN" experiments/reviewer_revision/collect_gas.py
  [ -f results/reviewer_revision/csv/network_sensitivity.csv ] || "$PYTHON_BIN" experiments/reviewer_revision/run_data_plane_v2.py
  [ -f results/reviewer_revision/csv/block_period_sensitivity.csv ] || "$PYTHON_BIN" experiments/reviewer_revision/run_block_period_sensitivity.py --besu "$BESU_NATIVE_BIN"
  [ -f results/reviewer_revision/csv/validator_faults.csv ] || "$PYTHON_BIN" experiments/reviewer_revision/run_validator_faults.py --besu "$BESU_NATIVE_BIN" --cast "$CAST_BIN" --trials 5
  "$PYTHON_BIN" experiments/reviewer_revision/run_foundry_security.py --forge "$FORGE_BIN" --solc "$SOLC_BIN"
  if [ ! -f results/reviewer_revision/raw/security/slither_final.json ]; then
    (cd contracts && "$SLITHER_BIN" . --foundry-out-directory out \
      --json ../results/reviewer_revision/raw/security/slither_final.json \
      > ../results/reviewer_revision/raw/security/slither_final.txt 2>&1) || true
  fi
  "$PYTHON_BIN" experiments/reviewer_revision/summarize_slither.py
  "$PYTHON_BIN" experiments/reviewer_revision/analyze_timing.py
  "$PYTHON_BIN" experiments/reviewer_revision/verify_protocol_fingerprint.py --solc "$SOLC_BIN"
  run_analysis
}

environment_doctor
case "$MODE" in
  smoke) run_smoke ;;
  analysis-only) run_analysis ;;
  full) run_full ;;
esac
echo "reviewer-revision mode '$MODE' completed"
echo "evidence package: $ROOT_DIR/release/LedgerGuard_Reviewer_Revision_Evidence.zip"

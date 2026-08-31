#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

source experiments/runners/common.sh
ensure_result_dirs

mkdir -p results/raw/accountability results/csv

cat > results/csv/accountability_formula.csv <<'CSV'
run_id,fleet_size,accountability_mode,onchain_records,tx_count,estimated_onchain_bytes,formula_used,metric_type,notes
CSV

python3 - <<'PY'
import csv, json, math
from datetime import datetime, timezone
rows = []
for fleet in [100, 500, 1000]:
    naive_bytes = fleet * 160
    merkle_bytes = 32 + 16 * 4 + 80
    rows.append({
        "run_id": f"accountability_formula_naive_{fleet}",
        "fleet_size": fleet,
        "accountability_mode": "naive",
        "onchain_records": fleet,
        "tx_count": fleet,
        "estimated_onchain_bytes": naive_bytes,
        "formula_used": "fleet_size * 160 bytes per per-device commitment",
        "metric_type": "formula_estimate",
        "notes": "Formula-derived comparison, not measured chain growth.",
    })
    rows.append({
        "run_id": f"accountability_formula_merkle_{fleet}",
        "fleet_size": fleet,
        "accountability_mode": "merkle",
        "onchain_records": 1,
        "tx_count": 1,
        "estimated_onchain_bytes": merkle_bytes,
        "formula_used": "32-byte root + aggregate counters + metadata",
        "metric_type": "formula_estimate",
        "notes": "Formula-derived comparison, not measured chain growth.",
    })
with open("results/csv/accountability_formula.csv", "a", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writerows(rows)
with open("results/raw/accountability/accountability_formula.jsonl", "w", encoding="utf-8") as f:
    for row in rows:
        f.write(json.dumps({**row, "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}, sort_keys=True) + "\n")
PY

cat > results/csv/accountability_measured.csv <<'CSV'
run_id,fleet_size,accountability_mode,tx_count,gas_used,validator_database_size_before,validator_database_size_after,measurement_status,evidence_path,notes
accountability_measured_status,0,not_run,,,,,not_run,results/raw/accountability/accountability_measured_status.jsonl,Requires Besu/Foundry run with NaiveDeviceReporting and DeviceAttestation transactions.
CSV

python3 - <<'PY'
import json
from datetime import datetime, timezone
with open("results/raw/accountability/accountability_measured_status.jsonl", "w", encoding="utf-8") as f:
    f.write(json.dumps({
        "status": "not_run",
        "reason": "Measured accountability requires a chain run that submits naive per-device outcomes and Merkle roots.",
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }, sort_keys=True) + "\n")
PY

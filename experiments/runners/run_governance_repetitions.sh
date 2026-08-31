#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

source experiments/runners/common.sh
ensure_result_dirs

mkdir -p results/raw/governance results/csv

cat > results/csv/governance_timing.csv <<'CSV'
run_id,seed,operation,start_timestamp_utc,end_timestamp_utc,latency_seconds,tx_hash,block_number,gas_used,event_readback_latency_seconds,status,error_message,evidence_path
CSV

cat > results/csv/governance_correctness.csv <<'CSV'
run_id,seed,case_id,expected_behavior,observed_behavior,status,evidence_path,notes
CSV

python3 - <<'PY'
import csv, json
from datetime import datetime, timezone

operations = [
    "register_release", "security_approval", "regulator_approval", "approval_threshold_path",
    "start_rollout", "advance_to_batch", "advance_to_global", "submit_outcome_root_epoch_1",
    "submit_outcome_root_epoch_2", "submit_outcome_root_epoch_3", "revoked_signer_attempt",
    "revoked_vendor_attempt", "low_success_rollout_advancement_attempt", "kill_switch_action_readback",
]
rows = []
correctness = []
for idx, operation in enumerate(operations, start=1):
    evidence = f"results/raw/governance/{operation}.jsonl"
    reason = "Requires accessible Docker/Besu control plane; no measured governance timing is claimed."
    rows.append({
        "run_id": f"governance_status_{idx:02d}",
        "seed": 1000 + idx,
        "operation": operation,
        "start_timestamp_utc": "",
        "end_timestamp_utc": "",
        "latency_seconds": "",
        "tx_hash": "",
        "block_number": "",
        "gas_used": "",
        "event_readback_latency_seconds": "",
        "status": "not_run",
        "error_message": reason,
        "evidence_path": evidence,
    })
    correctness.append({
        "run_id": f"governance_correctness_{idx:02d}",
        "seed": 1000 + idx,
        "case_id": operation,
        "expected_behavior": "LedgerGuard policy is enforced by contract execution and readback.",
        "observed_behavior": "Not executed in this environment.",
        "status": "not_run",
        "evidence_path": evidence,
        "notes": reason,
    })
    with open(evidence, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "operation": operation,
            "status": "not_run",
            "reason": reason,
            "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }, sort_keys=True) + "\n")

with open("results/csv/governance_timing.csv", "a", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writerows(rows)
with open("results/csv/governance_correctness.csv", "a", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(correctness[0]))
    writer.writerows(correctness)
PY

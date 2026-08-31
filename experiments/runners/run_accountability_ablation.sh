#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

source experiments/runners/common.sh
ensure_result_dirs

mkdir -p results/raw/accountability results/csv

cat > results/csv/accountability_ablation.csv <<'CSV'
fleet_size,batch_size,reporting_mode,on_chain_equivalent_records,computed_bytes,transaction_count,gas_used,validator_db_size_before,validator_db_size_after,evidence_type,status,evidence_path
CSV

python3 - <<'PY'
import csv, json
from datetime import datetime, timezone

rows = []
for fleet in [100, 500, 1000]:
    for batch in [25, 50, 100, 200]:
        for mode in ["naïve", "merkle"]:
            if mode == "naïve":
                records = fleet
                bytes_used = fleet * 160
                tx_count = ""
            else:
                batches = (fleet + batch - 1) // batch
                records = batches
                bytes_used = batches * (32 + 16 * 4 + 80)
                tx_count = ""
            evidence = f"results/raw/accountability/{mode}_{fleet}_{batch}.jsonl"
            row = {
                "fleet_size": fleet,
                "batch_size": batch,
                "reporting_mode": mode,
                "on_chain_equivalent_records": records,
                "computed_bytes": bytes_used,
                "transaction_count": tx_count,
                "gas_used": "",
                "validator_db_size_before": "",
                "validator_db_size_after": "",
                "evidence_type": "formula",
                "status": "recorded",
                "evidence_path": evidence,
            }
            rows.append(row)
            with open(evidence, "w", encoding="utf-8") as f:
                f.write(json.dumps({
                    **row,
                    "note": "Formula-derived accountability comparison. Validator database growth is not claimed.",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }, ensure_ascii=False, sort_keys=True) + "\n")

with open("results/csv/accountability_ablation.csv", "a", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writerows(rows)
PY

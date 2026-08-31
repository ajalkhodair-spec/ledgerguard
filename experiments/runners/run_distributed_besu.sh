#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

source experiments/runners/common.sh
ensure_result_dirs

mkdir -p results/raw/distributed_besu results/csv

DOCKER_BIN=${DOCKER_BIN:-docker}
if [ -x /Applications/Docker.app/Contents/Resources/bin/docker ]; then
  DOCKER_BIN=/Applications/Docker.app/Contents/Resources/bin/docker
fi

cat > results/csv/distributed_besu_timing.csv <<'CSV'
run_id,topology,validator_count,operation,tx_hash,block_number,gas_used,tx_status,timestamp_submit_utc,timestamp_receipt_utc,event_readback_latency_ms,measurement_status,evidence_path,notes
local_4_validators_status,local_4_validators,4,status,,,,,,,,not_run,results/raw/distributed_besu/local_4_validators_status.jsonl,Run the Besu-backed timing workflow to populate measured rows.
distributed_4_validators_status,distributed_4_validators,4,status,,,,,,,,not_run,results/raw/distributed_besu/distributed_4_validators_status.jsonl,Requires LEDGERGUARD_DISTRIBUTED_HOSTS or Docker contexts.
distributed_7_validators_status,distributed_7_validators,7,status,,,,,,,,not_run,results/raw/distributed_besu/distributed_7_validators_status.jsonl,Requires LEDGERGUARD_DISTRIBUTED_HOSTS or Docker contexts.
CSV

cat > results/csv/chain_growth.csv <<'CSV'
run_id,topology,validator_count,database_size_before_bytes,database_size_after_bytes,gas_total,measurement_status,evidence_path,notes
CSV

if "$DOCKER_BIN" info >/dev/null 2>&1 && "$DOCKER_BIN" inspect ledgerguard-besu-node1 >/dev/null 2>&1; then
  python3 - <<'PY'
import json, os
from datetime import datetime, timezone
paths = [f"network/Node-{idx}/data" for idx in range(1, 5)]
sizes = {}
for path in paths:
    total = 0
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for name in files:
                fp = os.path.join(root, name)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    sizes[path] = total
after = sum(sizes.values())
payload = {
    "status": "measured_snapshot",
    "database_size_after_bytes": after,
    "node_data_sizes": sizes,
    "note": "Current validator data-directory snapshot. database_size_before_bytes is blank because this run did not capture a pre-run snapshot.",
    "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}
with open("results/raw/distributed_besu/chain_growth_status.jsonl", "w", encoding="utf-8") as f:
    f.write(json.dumps(payload, sort_keys=True) + "\n")
with open("results/csv/chain_growth.csv", "a", encoding="utf-8") as f:
    f.write(f"chain_growth_snapshot,local_4_validators,4,,{after},,measured_snapshot,results/raw/distributed_besu/chain_growth_status.jsonl,Current validator data-directory snapshot; pre-run baseline was not captured.\n")
PY
else
  cat >> results/csv/chain_growth.csv <<'CSV'
chain_growth_status,local_4_validators,4,,,,not_run,results/raw/distributed_besu/chain_growth_status.jsonl,Requires validator database size and gas evidence from a chain run.
CSV
fi

python3 - <<'PY'
import json
from datetime import datetime, timezone
for name in ["local_4_validators_status", "distributed_4_validators_status", "distributed_7_validators_status"]:
    with open(f"results/raw/distributed_besu/{name}.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "status": "not_run",
            "reason": "Distributed/local Besu strong timing runner is scaffolded; measured rows require running Docker/Besu.",
            "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }, sort_keys=True) + "\n")
PY

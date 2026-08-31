#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

source experiments/runners/common.sh
ensure_result_dirs

mkdir -p results/raw/network results/csv

TC_AVAILABLE=false
if command -v tc >/dev/null 2>&1; then
  TC_AVAILABLE=true
fi

cat > results/csv/network_sensitivity.csv <<'CSV'
profile,RTT,bandwidth,artifact_size_bytes,retrieval_time_s,end_to_end_time_s,bytes_transferred,cache_hit_rate,success_rate,evidence_type,status,evidence_path,notes
CSV

python3 - "$TC_AVAILABLE" <<'PY'
import csv, json, sys
from datetime import datetime, timezone
tc_available = sys.argv[1] == "true"
profiles = [
    ("P1", 20, 5.0, 0, 0),
    ("P2", 80, 5.0, 0, 0),
    ("P3", 200, 0.256, 0, 0),
]
rows = []
for pid, rtt, bw, jitter, loss in profiles:
    status = "scenario" if not tc_available else "configured"
    evidence_type = "scenario" if not tc_available else "configured"
    notes = "tc/netem not available; deterministic scenario placeholder only." if not tc_available else "tc/netem is available; run retrieval workflow to populate collected timings."
    evidence = f"results/raw/network/{pid}.jsonl"
    row = {
        "profile": pid,
        "RTT": rtt,
        "bandwidth": bw,
        "artifact_size_bytes": 524288,
        "retrieval_time_s": "",
        "end_to_end_time_s": "",
        "bytes_transferred": "",
        "cache_hit_rate": "",
        "success_rate": "",
        "evidence_type": evidence_type,
        "status": status,
        "evidence_path": evidence,
        "notes": notes,
    }
    rows.append(row)
    with open(evidence, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "profile_id": pid,
            "tc_available": tc_available,
            "status": status,
            "evidence_type": evidence_type,
            "notes": notes,
            "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }, sort_keys=True) + "\n")

with open("results/csv/network_sensitivity.csv", "a", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writerows(rows)
PY

if [ "$TC_AVAILABLE" = true ]; then
  write_status_json results/validation/network_status.json configured "tc/netem is available; run the retrieval workflow to collect timings."
else
  write_status_json results/validation/network_status.json scenario "tc/netem is unavailable; only scenario placeholders were written."
fi

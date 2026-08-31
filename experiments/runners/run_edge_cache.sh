#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

source experiments/runners/common.sh
ensure_result_dirs

mkdir -p results/raw/cache results/csv

cat > results/csv/edge_cache_ablation.csv <<'CSV'
cache_mode,RTT,bandwidth,artifact_size_bytes,retrieval_time_s,end_to_end_time_s,bytes_transferred,cache_hit_rate,success_rate,evidence_type,status,evidence_path,notes
CSV

python3 - <<'PY'
import csv, json
from datetime import datetime, timezone
rows = []
for mode in ["OFF", "ON"]:
    evidence = f"results/raw/cache/cache_{mode.lower()}.jsonl"
    notes = "Scenario row only. Run with a real gateway/cache workflow to populate measured timings."
    row = {
        "cache_mode": mode,
        "RTT": 80,
        "bandwidth": 5.0,
        "artifact_size_bytes": 524288,
        "retrieval_time_s": "",
        "end_to_end_time_s": "",
        "bytes_transferred": "",
        "cache_hit_rate": "",
        "success_rate": "",
        "evidence_type": "scenario",
        "status": "scenario",
        "evidence_path": evidence,
        "notes": notes,
    }
    rows.append(row)
    with open(evidence, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "cache_mode": mode,
            "status": "scenario",
            "notes": notes,
            "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }, sort_keys=True) + "\n")
with open("results/csv/edge_cache_ablation.csv", "a", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writerows(rows)
PY

if [ -f out/release_metadata.json ] && command -v curl >/dev/null 2>&1; then
  CID=$(python3 - <<'PY'
import json
meta = json.load(open("out/release_metadata.json", encoding="utf-8"))
print(meta["cid"])
PY
)
  size=$(python3 - <<'PY'
import json
meta = json.load(open("out/release_metadata.json", encoding="utf-8"))
print(meta.get("size_bytes", ""))
PY
)
  raw="results/raw/cache/local_ipfs_gateway.jsonl"
  tmp=$(mktemp)
  set +e
  metrics=$(curl -L -sS -o "$tmp" -w '%{time_total},%{size_download},%{http_code}' "http://localhost:8080/ipfs/$CID")
  rc=$?
  set -e
  bytes=$(printf '%s' "$metrics" | cut -d, -f2)
  time_total=$(printf '%s' "$metrics" | cut -d, -f1)
  http_code=$(printf '%s' "$metrics" | cut -d, -f3)
  rm -f "$tmp"
  python3 - "$CID" "$size" "$time_total" "$bytes" "$http_code" "$rc" <<'PY'
import json, sys
from datetime import datetime, timezone
cid, size, time_total, bytes_downloaded, http_code, rc = sys.argv[1:7]
status = "measured" if rc == "0" and http_code == "200" else "failed"
payload = {
    "cid": cid,
    "artifact_size_bytes": size,
    "retrieval_time_s": time_total,
    "bytes_transferred": bytes_downloaded,
    "http_code": http_code,
    "return_code": int(rc),
    "evidence_type": "local_benchmark",
    "status": status,
    "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}
with open("results/raw/cache/local_ipfs_gateway.jsonl", "w", encoding="utf-8") as f:
    f.write(json.dumps(payload, sort_keys=True) + "\n")
if status == "measured":
    with open("results/csv/edge_cache_ablation.csv", "a", encoding="utf-8") as f:
        f.write(f"LOCAL_IPFS,0,local,{size},{time_total},{time_total},{bytes_downloaded},,1.0,local_benchmark,measured,results/raw/cache/local_ipfs_gateway.jsonl,Local IPFS gateway retrieval benchmark; not a WAN traffic-shaping result.\n")
PY
  if [ "$rc" -eq 0 ] && [ "$http_code" = "200" ]; then
    write_status_json results/validation/cache_status.json measured "Collected local IPFS gateway retrieval benchmark; WAN/cache scenario rows remain labeled separately."
  else
    write_status_json results/validation/cache_status.json scenario "Local IPFS gateway benchmark failed; scenario rows remain."
  fi
else
  write_status_json results/validation/cache_status.json scenario "Cache rows are scenario placeholders until a real gateway/cache workflow is executed."
fi

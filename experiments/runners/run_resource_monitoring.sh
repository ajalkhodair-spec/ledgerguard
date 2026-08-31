#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

source experiments/runners/common.sh
ensure_result_dirs

DOCKER_BIN=${DOCKER_BIN:-docker}
if [ -x /Applications/Docker.app/Contents/Resources/bin/docker ]; then
  DOCKER_BIN=/Applications/Docker.app/Contents/Resources/bin/docker
fi

mkdir -p results/raw/resources

cat > results/csv/validator_resource_usage.csv <<'CSV'
timestamp_utc,topology,validator,resource_collection_available,cpu_percent,memory_mb,network_rx_bytes,network_tx_bytes,status,reason
CSV

if ! "$DOCKER_BIN" info >/dev/null 2>&1; then
  printf '%s,local_4_validators,all,false,,,,,not_run,Docker daemon is not reachable.\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> results/csv/validator_resource_usage.csv
  write_status_json results/validation/resource_monitoring_status.json not_run "Docker daemon is not reachable."
  exit 0
fi

found=false
for validator in ledgerguard-besu-node1 ledgerguard-besu-node2 ledgerguard-besu-node3 ledgerguard-besu-node4; do
  if ! "$DOCKER_BIN" inspect "$validator" >/dev/null 2>&1; then
    continue
  fi
  found=true
  raw="results/raw/resources/${validator}.json"
  "$DOCKER_BIN" stats --no-stream --format '{{json .}}' "$validator" > "$raw"
  python3 - "$validator" "$raw" <<'PY' >> results/csv/validator_resource_usage.csv
import json, re, sys
from datetime import datetime, timezone
name, raw = sys.argv[1], sys.argv[2]
data = json.load(open(raw, encoding="utf-8"))
def mb(value):
    value = value.strip()
    m = re.match(r"([0-9.]+)([KMG]i?B)", value)
    if not m:
        return ""
    num, unit = float(m.group(1)), m.group(2)
    scale = {"KiB": 1/1024, "kB": 1/1024, "MiB": 1, "MB": 1, "GiB": 1024, "GB": 1024}.get(unit, 1)
    return f"{num * scale:.3f}"
def bytes_value(value):
    value = value.strip()
    m = re.match(r"([0-9.]+)([kKmMgG]?B)", value)
    if not m:
        return ""
    num, unit = float(m.group(1)), m.group(2).lower()
    scale = {"b": 1, "kb": 1000, "mb": 1000**2, "gb": 1000**3}.get(unit, 1)
    return str(int(num * scale))
cpu = data.get("CPUPerc", "").replace("%", "")
mem = data.get("MemUsage", "").split("/")[0].strip()
net = data.get("NetIO", " / ").split("/")
rx = bytes_value(net[0]) if net else ""
tx = bytes_value(net[1]) if len(net) > 1 else ""
print(",".join([
    datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "local_4_validators",
    name,
    "true",
    cpu,
    mb(mem),
    rx,
    tx,
    "measured",
    "Collected with docker stats --no-stream."
]))
PY
done

if [ "$found" = true ]; then
  write_status_json results/validation/resource_monitoring_status.json measured "Collected live Docker stats for running Besu validators."
else
  printf '%s,local_4_validators,all,false,,,,,not_run,No ledgerguard-besu-node containers were found.\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> results/csv/validator_resource_usage.csv
  write_status_json results/validation/resource_monitoring_status.json not_run "No ledgerguard-besu-node containers were found."
fi

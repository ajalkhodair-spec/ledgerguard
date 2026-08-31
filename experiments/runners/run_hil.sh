#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

source experiments/runners/common.sh
ensure_result_dirs

STATUS_JSON="results/validation/hil_status.json"
RAW_DIR="results/raw/hil"
mkdir -p "$RAW_DIR"

if [ -z "${LEDGERGUARD_HIL_DEVICE_CONFIG:-}" ]; then
  write_status_json "$STATUS_JSON" "not_run" "LEDGERGUARD_HIL_DEVICE_CONFIG is not set; no real hardware logs were collected."
  exit 0
fi

if [ ! -f "$LEDGERGUARD_HIL_DEVICE_CONFIG" ]; then
  write_status_json "$STATUS_JSON" "not_run" "LEDGERGUARD_HIL_DEVICE_CONFIG points to a missing file."
  exit 0
fi

cp "$LEDGERGUARD_HIL_DEVICE_CONFIG" "$RAW_DIR/device_config.json"
write_status_json "$STATUS_JSON" "configured" "HIL config is present. Run the device agent on the hardware and save raw logs under results/raw/hil/."

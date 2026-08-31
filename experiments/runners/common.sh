#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
RESULTS_DIR="$ROOT_DIR/results"

timestamp_utc() {
  date -u +"%Y%m%dT%H%M%SZ"
}

ensure_result_dirs() {
  mkdir -p \
    "$RESULTS_DIR/raw" \
    "$RESULTS_DIR/csv" \
    "$RESULTS_DIR/figures" \
    "$RESULTS_DIR/workbook" \
    "$RESULTS_DIR/validation" \
    "$RESULTS_DIR/archive" \
    "$RESULTS_DIR/security" \
    "$ROOT_DIR/paper_assets/tables" \
    "$ROOT_DIR/paper_assets/figures"
}

archive_existing_results() {
  ensure_result_dirs
  local stamp archive
  stamp=$(timestamp_utc)
  archive="$RESULTS_DIR/archive/$stamp"
  mkdir -p "$archive"
  for name in raw csv figures workbook validation security; do
    if [ -d "$RESULTS_DIR/$name" ] && find "$RESULTS_DIR/$name" -mindepth 1 -print -quit | grep -q .; then
      mkdir -p "$archive"
      cp -a "$RESULTS_DIR/$name" "$archive/$name"
      find "$RESULTS_DIR/$name" -mindepth 1 -maxdepth 1 ! -name .gitkeep -exec rm -rf {} +
    fi
    mkdir -p "$RESULTS_DIR/$name"
  done
  printf '{"archived_at_utc":"%s","archive_path":"%s"}\n' "$stamp" "$archive" > "$RESULTS_DIR/validation/archive_status.json"
}

copy_existing_results_to_archive() {
  ensure_result_dirs
  local stamp archive
  stamp=$(timestamp_utc)
  archive="$RESULTS_DIR/archive/$stamp"
  mkdir -p "$archive"
  for name in raw csv figures workbook validation security; do
    if [ -d "$RESULTS_DIR/$name" ]; then
      cp -a "$RESULTS_DIR/$name" "$archive/$name"
    fi
  done
  if [ -d "$ROOT_DIR/paper_assets" ]; then
    cp -a "$ROOT_DIR/paper_assets" "$archive/paper_assets"
  fi
  printf '{"archived_at_utc":"%s","mode":"copy_only","archive_path":"%s"}\n' "$stamp" "$archive" > "$RESULTS_DIR/validation/archive_status.json"
}

write_status_json() {
  local path="$1"
  local status="$2"
  local reason="$3"
  mkdir -p "$(dirname "$path")"
  python3 - "$path" "$status" "$reason" <<'PY'
import json, sys
from datetime import datetime, timezone
path, status, reason = sys.argv[1:4]
with open(path, "w", encoding="utf-8") as f:
    json.dump({
        "status": status,
        "reason": reason,
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }, f, indent=2, sort_keys=True)
PY
}

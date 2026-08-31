#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

mkdir -p results/security results/validation

if ! command -v docker >/dev/null 2>&1; then
  printf 'forge test not run: docker is not available\n' > results/security/foundry_test_report.txt
  printf '{"tool":"foundry","status":"not_run","reason":"docker is not available"}\n' > results/security/security_summary.json
  exit 0
fi

if ! docker info >/dev/null 2>&1; then
  printf 'forge test not run: docker daemon is not accessible\n' > results/security/foundry_test_report.txt
  printf '{"tool":"foundry","status":"not_run","reason":"docker daemon is not accessible"}\n' > results/security/security_summary.json
  exit 0
fi

set +e
docker compose run --rm foundry "forge test -vvv" > results/security/foundry_test_report.txt 2>&1
RC=$?
set -e

if [ "$RC" -eq 0 ]; then
  STATUS=passed
else
  STATUS=failed
fi

python3 - "$STATUS" "$RC" <<'PY'
import json, sys
from datetime import datetime, timezone
status, rc = sys.argv[1], int(sys.argv[2])
with open("results/security/security_summary.json", "w", encoding="utf-8") as f:
    json.dump({
        "foundry": {"status": status, "exit_code": rc},
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }, f, indent=2, sort_keys=True)
PY

exit "$RC"

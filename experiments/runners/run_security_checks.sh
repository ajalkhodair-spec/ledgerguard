#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

source experiments/runners/common.sh
ensure_result_dirs

experiments/security/run_foundry_tests.sh
experiments/security/run_slither.sh
experiments/security/run_mythril_optional.sh

cat > results/csv/security_checks.csv <<'CSV'
tool,status,report_path,notes
CSV

python3 - <<'PY'
import csv, json
from pathlib import Path

rows = []
summary = Path("results/security/security_summary.json")
foundry_status = "not_run"
if summary.exists():
    try:
        data = json.loads(summary.read_text(encoding="utf-8"))
        if "foundry" in data:
            foundry_status = data["foundry"].get("status", "not_run")
        else:
            foundry_status = data.get("status", "not_run")
    except Exception:
        foundry_status = "unknown"
rows.append({"tool": "foundry", "status": foundry_status, "report_path": "results/security/foundry_test_report.txt", "notes": "Contract tests if Foundry/Docker is accessible."})
for tool, path in [("slither", "results/security/slither_report.txt"), ("mythril", "results/security/mythril_report.txt")]:
    text = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
    status = "unavailable" if "not installed" in text or "not run" in text else "executed"
    rows.append({"tool": tool, "status": status, "report_path": path, "notes": "Optional static/security analysis."})
with open("results/csv/security_checks.csv", "a", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writerows(rows)
PY

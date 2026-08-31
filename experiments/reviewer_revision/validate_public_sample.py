#!/usr/bin/env python3
"""Validate the compact public evidence sample and its provenance records."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "results_sample"
REQUIRED = {
    "besu/control_plane_run.csv": 7,
    "baseline/http_sqlite_run.csv": 7,
    "fleet/fleet_run.csv": 1,
    "fleet/receipts.jsonl": 1,
    "completeness/aggregation_cases.csv": 9,
    "completeness/selective_omission_denominator.json": 1,
    "gas/gas_examples.csv": 2,
    "validation/validation_report.json": 1,
    "manifest.json": 1,
}
PRIVATE_PATH = re.compile(
    r"/" + r"Users/|/" + r"home/[A-Za-z0-9._-]+|/" + r"private/(?:tmp|var)/|/" + r"var/folders/"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_rows(relative: str) -> list[dict[str, str]]:
    with (SAMPLE / relative).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (SAMPLE / relative).is_file():
            errors.append(f"missing required sample file: {relative}")

    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, indent=2))
        return 1

    if len(csv_rows("besu/control_plane_run.csv")) != 7:
        errors.append("Besu sample must contain one seven-operation control-plane run")
    if any(row.get("tx_status") != "success" for row in csv_rows("besu/control_plane_run.csv")):
        errors.append("Besu sample contains a non-success transaction")
    if len(csv_rows("baseline/http_sqlite_run.csv")) != 7:
        errors.append("HTTP/SQLite sample must contain one seven-operation run")
    if len(csv_rows("fleet/fleet_run.csv")) != 1:
        errors.append("fleet sample must contain exactly one run summary")
    receipts = [
        json.loads(line)
        for line in (SAMPLE / "fleet/receipts.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    fleet_row = csv_rows("fleet/fleet_run.csv")[0]
    if len(receipts) != int(fleet_row["received_valid_count"]):
        errors.append("fleet receipt count does not match the sampled run summary")
    if len(csv_rows("completeness/aggregation_cases.csv")) != 9:
        errors.append("all nine completeness cases must be represented")
    if any(row.get("status") != "passed" for row in csv_rows("completeness/aggregation_cases.csv")):
        errors.append("completeness sample contains a failed case")
    report = json.loads((SAMPLE / "validation/validation_report.json").read_text(encoding="utf-8"))
    if report.get("status") != "PASS" or report.get("error_count") != 0:
        errors.append("sampled validation report is not PASS")

    manifest = json.loads((SAMPLE / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest.get("files", [])
    for entry in entries:
        path = SAMPLE / entry["path"]
        if not path.is_file():
            errors.append(f"manifest path missing: {entry['path']}")
        elif sha256(path) != entry["sha256"]:
            errors.append(f"checksum mismatch: {entry['path']}")

    for path in SAMPLE.rglob("*"):
        if path.is_file() and path.suffix.lower() not in {".pdf", ".png"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            if PRIVATE_PATH.search(text):
                errors.append(f"private host path in {path.relative_to(SAMPLE)}")

    status = "PASS" if not errors else "FAIL"
    print(json.dumps({"status": status, "files": len(entries), "receipts": len(receipts), "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

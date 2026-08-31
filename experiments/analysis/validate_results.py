#!/usr/bin/env python3
"""Validate LedgerGuard strong-evaluation outputs without promoting placeholders."""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_CSVS = [
    "sqlite_baseline_timing.csv",
    "governance_timing.csv",
    "governance_correctness.csv",
    "distributed_besu_timing.csv",
    "validator_resource_usage.csv",
    "chain_growth.csv",
    "network_sensitivity.csv",
    "edge_cache_ablation.csv",
    "accountability_ablation.csv",
    "adversarial_validation.csv",
    "security_checks.csv",
]

FORBIDDEN_PHRASES = [
    "sub-millisecond dlt",
    "enterprise-grade readiness",
    "100% attack detection",
    "hardware validation completed",
    "sentivity",
    "attestaion",
    "sizes.the",
    "figure ??",
    "fall receipt",
    "aggregate receipt",
    "anchor root",
    "9a success",
    "9b failure",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def is_bad_number(value: str) -> bool:
    text = value.strip().lower()
    if text in {"nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}:
        return True
    try:
        number = float(text)
    except ValueError:
        return False
    return math.isnan(number) or math.isinf(number)


def scan_csv(path: Path, findings: list[str]) -> int:
    rows = read_csv(path)
    if not rows:
        findings.append(f"{path.name}: no rows")
        return 0
    for idx, row in enumerate(rows, start=2):
        for key, value in row.items():
            if value is not None and is_bad_number(value):
                findings.append(f"{path.name}:{idx}: invalid numeric value in {key}")
    return len(rows)


def scan_text_outputs(root: Path, findings: list[str]) -> None:
    allowed_suffixes = {".md", ".tex", ".csv", ".json", ".txt"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in allowed_suffixes:
            continue
        if path.name in {"validation_report.md", "validation_report.json"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for phrase in FORBIDDEN_PHRASES:
            if phrase in text:
                findings.append(f"{path}: contains forbidden phrase '{phrase}'")
        if "naive" in text and "naïve" in text:
            findings.append(f"{path}: mixes 'naive' and 'naïve'; standardize to 'naïve'")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    csv_dir = results_dir / "csv"
    validation_dir = results_dir / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)

    findings: list[str] = []
    row_counts: dict[str, int] = {}
    for name in REQUIRED_CSVS:
        path = csv_dir / name
        if not path.exists():
            findings.append(f"missing required CSV: {path}")
            continue
        row_counts[name] = scan_csv(path, findings)

    hil = load_json(validation_dir / "hil_status.json")
    if hil and hil.get("status") == "pass" and not hil.get("device_config"):
        findings.append("HIL marked pass without a device_config reference")

    scan_text_outputs(results_dir, findings)
    scan_text_outputs(Path("paper_assets"), findings)

    network_csv = csv_dir / "network_sensitivity.csv"
    if network_csv.exists():
        for idx, row in enumerate(read_csv(network_csv), start=2):
            if row.get("evidence_type") == "measured" and not row.get("retrieval_time_s"):
                findings.append(f"network_sensitivity.csv:{idx}: measured network row lacks retrieval evidence")

    accountability_csv = csv_dir / "accountability_ablation.csv"
    if accountability_csv.exists():
        for idx, row in enumerate(read_csv(accountability_csv), start=2):
            if row.get("evidence_type") in {"measured_gas", "measured_db"}:
                if not (row.get("gas_used") or row.get("validator_db_size_after")):
                    findings.append(f"accountability_ablation.csv:{idx}: measured storage/gas row lacks evidence")

    status = "PASS" if not findings else "FAIL"
    report = [
        f"# LedgerGuard Strong Evaluation Validation",
        "",
        f"- status: {status}",
        f"- generated_at_utc: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}",
        f"- results_dir: {results_dir}",
        "",
        "## CSV Row Counts",
        "",
    ]
    for name in REQUIRED_CSVS:
        report.append(f"- {name}: {row_counts.get(name, 0)}")
    report.extend(["", "## Findings", ""])
    if findings:
        report.extend(f"- {item}" for item in findings)
    else:
        report.append("- No validation findings.")

    out_path = validation_dir / "validation_report.md"
    out_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    json_path = validation_dir / "validation_report.json"
    json_path.write_text(json.dumps({
        "status": status,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "required_csvs": REQUIRED_CSVS,
        "row_counts": row_counts,
        "findings": findings,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{status}: {out_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

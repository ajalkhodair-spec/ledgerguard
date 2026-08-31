#!/usr/bin/env python3
"""Aggregate strong-evaluation outputs into a compact status summary."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


CSV_FILES = [
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


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def status_for_rows(rows: list[dict[str, str]]) -> Counter:
    counts: Counter = Counter()
    for row in rows:
        status = (row.get("status") or row.get("evidence_status") or row.get("measurement_status") or "recorded").strip()
        counts[status or "recorded"] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    csv_dir = results_dir / "csv"
    validation_dir = results_dir / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)

    datasets = {}
    overall_status = Counter()
    for name in CSV_FILES:
        rows = read_csv(csv_dir / name)
        counts = status_for_rows(rows)
        datasets[name] = {
            "exists": (csv_dir / name).exists(),
            "rows": len(rows),
            "statuses": dict(counts),
        }
        overall_status.update(counts)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "results_dir": str(results_dir),
        "datasets": datasets,
        "overall_statuses": dict(overall_status),
    }
    out_path = validation_dir / "strong_eval_summary.json"
    out_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

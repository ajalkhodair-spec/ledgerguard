#!/usr/bin/env python3
"""Generate compact paper-facing LaTeX tables from strong-evaluation outputs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

STRONG_EVAL_CSVS = [
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

def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def escape_latex(value: str) -> str:
    return (
        value.replace("\\", "\\textbackslash{}")
        .replace("&", "\\&")
        .replace("%", "\\%")
        .replace("_", "\\_")
        .replace("#", "\\#")
    )


def table_status(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = row.get("status") or row.get("evidence_status") or row.get("measurement_status") or "recorded"
        counts[status] = counts.get(status, 0) + 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--out-dir", default="paper_assets/tables")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for name in STRONG_EVAL_CSVS:
        path = results_dir / "csv" / name
        if not path.exists():
            continue
        counts = table_status(read_rows(path))
        rows.append((path.stem, sum(counts.values()), ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))))

    lines = [
        "\\begin{tabular}{lrl}",
        "\\toprule",
        "Dataset & Rows & Evidence status \\\\",
        "\\midrule",
    ]
    for dataset, count, status in rows:
        lines.append(f"{escape_latex(dataset)} & {count} & {escape_latex(status)} \\\\")
    lines.extend(["\\bottomrule", "\\end{tabular}", ""])
    out_path = out_dir / "strong_eval_dataset_status.tex"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

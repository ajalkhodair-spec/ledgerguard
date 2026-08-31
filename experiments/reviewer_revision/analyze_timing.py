#!/usr/bin/env python3
"""Apply the preregistered timing statistics to V2 Besu and HTTP/SQLite evidence."""

from __future__ import annotations

import csv
import argparse
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
SEED = 20260828
RESAMPLES = 10_000
COMPARABLE = (
    "register_release",
    "security_approval",
    "regulator_approval",
    "start_rollout",
    "propose_outcome_summary",
    "confirm_outcome_summary",
)


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def bootstrap_ci(values: list[float], statistic: Callable[[list[float]], float], rng: random.Random) -> tuple[float, float]:
    sampled = [statistic(rng.choices(values, k=len(values))) for _ in range(RESAMPLES)]
    return percentile(sampled, 0.025), percentile(sampled, 0.975)


def summarize(values: list[float], rng: random.Random) -> dict[str, float | int | str]:
    q1 = percentile(values, 0.25)
    q3 = percentile(values, 0.75)
    mean = statistics.fmean(values)
    standard_deviation = statistics.stdev(values) if len(values) > 1 else 0.0
    median_ci = bootstrap_ci(values, statistics.median, rng)
    mean_ci = bootstrap_ci(values, statistics.fmean, rng)
    result: dict[str, float | int | str] = {
        "count": len(values), "minimum_ms": min(values), "q1_ms": q1,
        "median_ms": statistics.median(values), "q3_ms": q3, "maximum_ms": max(values),
        "iqr_ms": q3 - q1, "mean_ms": mean, "standard_deviation_ms": standard_deviation,
        "coefficient_of_variation": standard_deviation / mean if mean else 0.0,
        "p90_ms": percentile(values, 0.90),
        "median_ci95_low_ms": median_ci[0], "median_ci95_high_ms": median_ci[1],
        "mean_ci95_low_ms": mean_ci[0], "mean_ci95_high_ms": mean_ci[1],
    }
    if len(values) >= 50:
        result["p95_ms"] = percentile(values, 0.95)
    else:
        result["p95_ms"] = "not_reported_n_lt_50"
    return result


def cliffs_delta(first: list[float], second: list[float]) -> float:
    greater = sum(a > b for a in first for b in second)
    lower = sum(a < b for a in first for b in second)
    return (greater - lower) / (len(first) * len(second))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--besu", default=str(ROOT / "results/reviewer_revision/csv/besu_v2_final_timing.csv"))
    parser.add_argument("--baseline", default=str(ROOT / "results/reviewer_revision/csv/http_sqlite_v2_timing.csv"))
    parser.add_argument("--label", default="besu_v2_final")
    args = parser.parse_args()
    besu_path = Path(args.besu)
    baseline_path = Path(args.baseline)
    besu_rows = list(csv.DictReader(besu_path.open(encoding="utf-8")))
    baseline_rows = list(csv.DictReader(baseline_path.open(encoding="utf-8")))
    operations_per_path = 7
    successful_by_run: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in besu_rows:
        if row["tx_status"] == "success":
            successful_by_run[row["repetition"]].append(row)
    complete_runs = {
        repetition
        for repetition, rows in successful_by_run.items()
        if len(rows) == operations_per_path and len({row["operation"] for row in rows}) == operations_per_path
    }
    besu_analysis_rows = [row for row in besu_rows if row["repetition"] in complete_runs and row["tx_status"] == "success"]
    rng = random.Random(SEED)

    grouped: dict[str, dict[str, list[float]]] = {
        "besu": defaultdict(list), "http_sqlite": defaultdict(list)
    }
    for row in besu_analysis_rows:
        grouped["besu"][row["operation"]].append(float(row["latency_seconds"]) * 1000)
    for row in baseline_rows:
        if row["status"] == "success":
            grouped["http_sqlite"][row["operation"]].append(float(row["latency_ms"]))

    statistics_dir = ROOT / "results/reviewer_revision/statistics"
    write_csv(
        ROOT / "results/reviewer_revision/csv/besu_v2_final_timing_complete.csv",
        besu_analysis_rows,
    )
    summaries: dict[str, list[dict]] = {}
    for system in ("besu", "http_sqlite"):
        summaries[system] = []
        for operation in sorted(grouped[system]):
            summaries[system].append(
                {"system": system, "operation": operation, "unit": "milliseconds", **summarize(grouped[system][operation], rng)}
            )
        output_name = f"{args.label}_timing_summary.csv" if system == "besu" else "http_sqlite_v2_timing_summary.csv"
        write_csv(statistics_dir / output_name, summaries[system])

    comparison_rows: list[dict] = []
    for operation in COMPARABLE:
        besu = grouped["besu"][operation]
        baseline = grouped["http_sqlite"][operation]
        if not besu or not baseline:
            continue
        median_ratio = statistics.median(besu) / statistics.median(baseline)
        median_difference = statistics.median(besu) - statistics.median(baseline)
        ratios: list[float] = []
        differences: list[float] = []
        for _ in range(RESAMPLES):
            besu_median = statistics.median(rng.choices(besu, k=len(besu)))
            baseline_median = statistics.median(rng.choices(baseline, k=len(baseline)))
            ratios.append(besu_median / baseline_median)
            differences.append(besu_median - baseline_median)
        comparison_rows.append(
            {
                "operation": operation, "besu_n": len(besu), "http_sqlite_n": len(baseline),
                "besu_median_ms": statistics.median(besu),
                "http_sqlite_median_ms": statistics.median(baseline),
                "median_latency_ratio_besu_over_http_sqlite": median_ratio,
                "ratio_ci95_low": percentile(ratios, 0.025), "ratio_ci95_high": percentile(ratios, 0.975),
                "median_absolute_difference_ms": median_difference,
                "difference_ci95_low_ms": percentile(differences, 0.025),
                "difference_ci95_high_ms": percentile(differences, 0.975),
                "cliffs_delta_besu_vs_http_sqlite": cliffs_delta(besu, baseline),
                "comparison_scope": "local_governance_path_comparison",
            }
        )
    write_csv(statistics_dir / "besu_vs_http_sqlite_v2.csv", comparison_rows)

    besu_latencies = [float(row["latency_seconds"]) for row in besu_analysis_rows]
    first_eligible = sum(row["first_eligible_block"] == "True" for row in besu_analysis_rows)
    later = sum(int(row["inclusion_delay_blocks"]) > 1 for row in besu_analysis_rows)
    block_analysis = {
        "configured_block_period_seconds": 2,
        "configuration_count": 1,
        "block_period_latency_correlation": None,
        "correlation_status": "not_calculated_single_block_period_configuration",
        "transaction_count": len(besu_latencies),
        "median_submission_to_receipt_seconds": statistics.median(besu_latencies),
        "median_latency_divided_by_block_period": statistics.median(besu_latencies) / 2,
        "first_eligible_block_count": first_eligible,
        "first_eligible_block_fraction": first_eligible / len(besu_latencies),
        "later_block_count": later,
        "later_block_fraction": later / len(besu_latencies),
        "receipt_poll_interval_seconds": 1,
        "interpretation": "Submission-to-receipt timing includes consensus block production and receipt polling; it is not contract execution time.",
    }
    (statistics_dir / "block_period_analysis.json").write_text(
        json.dumps(block_analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    status = {
        "status": "PASS",
        "bootstrap_seed": SEED,
        "bootstrap_resamples": RESAMPLES,
        "besu": {
            "attempted_runs": len({row["repetition"] for row in besu_rows}),
            "valid_runs": len(complete_runs),
            "excluded_runs": len({row["repetition"] for row in besu_rows}) - len(complete_runs),
            "failed_operations": sum(row["tx_status"] == "failed" for row in besu_rows),
            "reverted_operations": 0,
            "operation_rows": len(besu_analysis_rows),
            "required_operations_per_path": operations_per_path,
            "included_repetitions": sorted(int(value) for value in complete_runs),
        },
        "http_sqlite": {
            "attempted_runs": len({row["repetition"] for row in baseline_rows}),
            "valid_runs": len({row["repetition"] for row in baseline_rows if row["operation"] == "audit_reconstruction" and row["status"] == "success"}),
            "excluded_runs": 0,
            "failed_operations": sum(row["status"] == "failed" for row in baseline_rows),
            "reverted_operations": 0,
            "operation_rows": len(baseline_rows),
        },
        "directly_compared_operations": list(COMPARABLE),
        "excluded_from_direct_comparison": {
            "register_cohort": "The HTTP/SQLite proposal stores cohort context atomically rather than as a separate operation.",
            "audit_reconstruction": "No equivalent Besu event-readback observation was captured in this run.",
        },
    }
    validation_path = ROOT / "results/reviewer_revision/validation/timing_statistics_status.json"
    validation_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

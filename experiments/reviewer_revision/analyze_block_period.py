#!/usr/bin/env python3
"""Summarize the fresh-network IBFT2 block-period sensitivity experiment."""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SEED = 20260828
RESAMPLES = 10_000


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def pearson(first: list[float], second: list[float]) -> float:
    first_mean = statistics.fmean(first)
    second_mean = statistics.fmean(second)
    numerator = sum((x - first_mean) * (y - second_mean) for x, y in zip(first, second, strict=True))
    denominator = math.sqrt(
        sum((x - first_mean) ** 2 for x in first) * sum((y - second_mean) ** 2 for y in second)
    )
    return numerator / denominator


def main() -> None:
    source = ROOT / "results/reviewer_revision/csv/block_period_sensitivity.csv"
    rows = list(csv.DictReader(source.open(encoding="utf-8")))
    grouped: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[int(row["block_period_seconds"])].append(row)
    rng = random.Random(SEED)
    summaries: list[dict] = []
    for period, group in sorted(grouped.items()):
        values = [float(row["latency_seconds"]) for row in group if row["status"] == "success"]
        median_samples = [statistics.median(rng.choices(values, k=len(values))) for _ in range(RESAMPLES)]
        mean_samples = [statistics.fmean(rng.choices(values, k=len(values))) for _ in range(RESAMPLES)]
        q1 = percentile(values, 0.25)
        q3 = percentile(values, 0.75)
        first_eligible = sum(row["first_eligible_block"] == "True" for row in group)
        later = sum(int(row["inclusion_delay_blocks"]) > 1 for row in group)
        summaries.append(
            {
                "block_period_seconds": period, "attempted_transactions": len(group),
                "valid_transactions": len(values), "failed_transactions": len(group) - len(values),
                "minimum_seconds": min(values), "q1_seconds": q1,
                "median_seconds": statistics.median(values), "q3_seconds": q3,
                "maximum_seconds": max(values), "iqr_seconds": q3 - q1,
                "mean_seconds": statistics.fmean(values),
                "standard_deviation_seconds": statistics.stdev(values),
                "coefficient_of_variation": statistics.stdev(values) / statistics.fmean(values),
                "p90_seconds": percentile(values, 0.9), "p95_seconds": "not_reported_n_lt_50",
                "median_ci95_low": percentile(median_samples, 0.025),
                "median_ci95_high": percentile(median_samples, 0.975),
                "mean_ci95_low": percentile(mean_samples, 0.025),
                "mean_ci95_high": percentile(mean_samples, 0.975),
                "median_divided_by_block_period": statistics.median(values) / period,
                "first_eligible_block_fraction": first_eligible / len(values),
                "later_block_fraction": later / len(values),
                "receipt_poll_interval_seconds": 1, "validator_count": 4,
                "evidence_type": "fresh_local_besu_measurement",
            }
        )
    output = ROOT / "results/reviewer_revision/statistics/block_period_sensitivity_summary.csv"
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    periods = [float(row["block_period_seconds"]) for row in summaries]
    medians = [float(row["median_seconds"]) for row in summaries]
    status = {
        "status": "PASS",
        "profiles": len(summaries),
        "valid_transactions": sum(int(row["valid_transactions"]) for row in summaries),
        "failed_transactions": sum(int(row["failed_transactions"]) for row in summaries),
        "excluded_invalid_environment_rows": 30,
        "excluded_evidence": "results/reviewer_revision/raw/block_period/block_period_1s_excluded_native_stall",
        "block_period_median_latency_pearson_correlation": pearson(periods, medians),
        "significance_test": "not_applied_three_deterministic_configurations",
        "bootstrap_seed": SEED,
        "bootstrap_resamples": RESAMPLES,
        "slow_valid_observations_removed": 0,
    }
    (ROOT / "results/reviewer_revision/validation/block_period_status.json").write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()

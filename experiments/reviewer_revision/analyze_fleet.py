#!/usr/bin/env python3
"""Summarize preregistered multi-seed software-fleet outcomes."""

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


def main() -> None:
    source = ROOT / "results/reviewer_revision/csv/fleet_multiseed_runs.csv"
    rows = list(csv.DictReader(source.open(encoding="utf-8")))
    grouped: dict[tuple[int, float], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(int(row["fleet_size"]), float(row["configured_failure_rate"]))].append(row)
    rng = random.Random(SEED)
    summary_rows: list[dict] = []
    for (fleet_size, failure_rate), group in sorted(grouped.items()):
        adoption = [float(row["final_adoption_rate"]) for row in group]
        aggregate_ms = [float(row["aggregation_ms"]) for row in group]
        bootstrap_means = [statistics.fmean(rng.choices(adoption, k=len(adoption))) for _ in range(RESAMPLES)]
        q1 = percentile(adoption, 0.25)
        q3 = percentile(adoption, 0.75)
        summary_rows.append(
            {
                "fleet_size": fleet_size, "configured_failure_rate": failure_rate,
                "seed_count": len(group), "seeds": ";".join(sorted(row["seed"] for row in group)),
                "minimum_adoption_rate": min(adoption), "q1_adoption_rate": q1,
                "median_adoption_rate": statistics.median(adoption), "q3_adoption_rate": q3,
                "maximum_adoption_rate": max(adoption), "iqr_adoption_rate": q3 - q1,
                "mean_adoption_rate": statistics.fmean(adoption),
                "standard_deviation_adoption_rate": statistics.stdev(adoption),
                "mean_ci95_low": percentile(bootstrap_means, 0.025),
                "mean_ci95_high": percentile(bootstrap_means, 0.975),
                "median_aggregation_ms": statistics.median(aggregate_ms),
                "evidence_type": "authenticated_software_emulation",
                "trend_claim": "none_from_fleet_size_alone",
            }
        )
    output = ROOT / "results/reviewer_revision/statistics/fleet_multiseed_summary.csv"
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)
    status = {
        "status": "PASS",
        "run_count": len(rows),
        "configuration_count": len(summary_rows),
        "seeds_per_configuration": min(len(group) for group in grouped.values()),
        "bootstrap_seed": SEED,
        "bootstrap_resamples": RESAMPLES,
        "failed_runs": sum(row["status"] != "success" for row in rows),
        "interpretation": "Dispersion is reported per configuration; no monotonic fleet-size trend is inferred.",
    }
    (ROOT / "results/reviewer_revision/validation/fleet_statistics_status.json").write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()

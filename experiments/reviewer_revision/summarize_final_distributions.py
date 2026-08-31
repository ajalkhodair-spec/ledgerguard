#!/usr/bin/env python3
"""Derive outcome categories and full retrieval distributions from preserved observations."""

import csv
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

from experiments.reviewer_revision.analyze_fleet import percentile

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results/reviewer_revision"
OUTCOME_FIELDS = {"SUCCESS": "success_count", "ROLLBACK": "rollback_count", "FAIL": "fail_count", "REJECTED": "rejected_count", "MISSING": "missing_count"}


def describe(values):
    q1, q3 = percentile(values, .25), percentile(values, .75)
    return {"n": len(values), "minimum": min(values), "q1": q1, "median": statistics.median(values),
            "q3": q3, "maximum": max(values), "iqr": q3 - q1,
            "mean": statistics.fmean(values), "sample_standard_deviation": statistics.stdev(values)}


def outcome_shares(row):
    expected = int(row["expected_count"])
    counts = {outcome: int(row[field]) for outcome, field in OUTCOME_FIELDS.items()}
    if expected <= 0 or sum(counts.values()) != expected:
        raise ValueError("outcome counts do not reconcile with the expected cohort")
    return {outcome: 100 * count / expected for outcome, count in counts.items()}


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    with (RESULTS / "csv/fleet_multiseed_runs.csv").open() as stream:
        fleet = list(csv.DictReader(stream))
    grouped = defaultdict(list)
    for row in fleet:
        for outcome, value in outcome_shares(row).items():
            grouped[(int(row["fleet_size"]), float(row["configured_failure_rate"]), outcome)].append(value)
    rng = random.Random(20260828)
    outcomes = []
    for (size, rate, outcome), values in sorted(grouped.items()):
        boot = [statistics.fmean(rng.choices(values, k=len(values))) for _ in range(10000)]
        outcomes.append({"fleet_size": size, "configured_failure_rate": rate, "outcome": outcome,
                         **describe(values), "mean_ci95_low": percentile(boot, .025), "mean_ci95_high": percentile(boot, .975),
                         "unit": "percent_of_expected_cohort", "evidence_type": "authenticated_software_emulation"})
    write_csv(RESULTS / "statistics/fleet_outcome_categories.csv", outcomes)
    source = RESULTS / "raw/network/application_shaped_fetches.jsonl"
    network = [json.loads(line) for line in source.read_text().splitlines() if line]
    groups = defaultdict(list)
    for row in network:
        groups[row["profile"]].append(float(row["retrieval_time_seconds"]))
    write_csv(RESULTS / "statistics/network_full_distribution.csv", [
        {"profile": profile, **describe(values), "unit": "seconds", "evidence_type": "application_shaped_local_ipfs_fetch"}
        for profile, values in sorted(groups.items())
    ])
    status = {"status": "PASS", "fleet_runs": len(fleet), "outcome_summary_rows": len(outcomes),
              "network_observations": len(network), "network_maximum_seconds": max(row["retrieval_time_seconds"] for row in network),
              "observations_removed": 0, "rollback_derived_from": "rollback_count / expected_count",
              "figure7_fleet_size": 500, "figure7_statistic": "mean and bootstrap 95% confidence interval across 20 seeds",
              "figure8_statistic": "all 20 observations per profile and quartile box plot on logarithmic time axis"}
    (RESULTS / "validation/distribution_status.json").write_text(json.dumps(status, indent=2) + "\n")
    print(json.dumps(status))


if __name__ == "__main__":
    main()

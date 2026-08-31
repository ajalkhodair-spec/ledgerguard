#!/usr/bin/env python3
"""Generate publication figures from validated reviewer-revision CSV files."""

from __future__ import annotations

import csv
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, Rectangle


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "paper_assets/reviewer_revision/figures"
BLUE = "#1F4E79"
GREEN = "#2E7D32"
ORANGE = "#C66A00"
PURPLE = "#6C4AB6"
RED = "#B33A3A"
TEAL = "#147D86"
GRAY = "#5F6670"


plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "Liberation Serif", "DejaVu Serif"],
    "font.size": 10,
    "axes.titlesize": 14,
    "axes.labelsize": 11,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "axes.linewidth": 0.8,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})


def rows(path: str) -> list[dict[str, str]]:
    return list(csv.DictReader((ROOT / path).open(encoding="utf-8")))


def finish(fig: plt.Figure, stem: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{stem}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def control_plane() -> None:
    data = rows("results/reviewer_revision/statistics/besu_v2_final_timing_summary.csv")
    order = [
        "register_release", "security_approval", "regulator_approval", "start_rollout",
        "register_cohort", "propose_outcome_summary", "confirm_outcome_summary",
    ]
    labels = ["Register release", "Security approval", "Regulator approval", "Start rollout", "Register cohort", "Propose summary", "Confirm summary"]
    by_op = {row["operation"]: row for row in data}
    med = np.array([float(by_op[op]["median_ms"]) / 1000 for op in order])
    low = np.array([float(by_op[op]["median_ci95_low_ms"]) / 1000 for op in order])
    high = np.array([float(by_op[op]["median_ci95_high_ms"]) / 1000 for op in order])
    y = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    ax.barh(y, med, color=BLUE, height=0.62)
    ax.errorbar(med, y, xerr=np.vstack((med - low, high - med)), fmt="none", ecolor="#111111", capsize=3, lw=1)
    for yi, value in zip(y, med, strict=True):
        ax.text(value + 0.012, yi, f"{value:.3f}", va="center")
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlabel("Submission-to-receipt latency (s)")
    ax.set_xlim(0, float(max(high)) * 1.14)
    ax.set_title("Control-Plane Timing in Local Besu")
    ax.grid(axis="x", alpha=0.22)
    ax.set_axisbelow(True)
    finish(fig, "fig5_control_plane_timing")


def fleet() -> None:
    data = rows("results/reviewer_revision/statistics/fleet_multiseed_summary.csv")
    fleets = [100, 500, 1000]
    rates = [0.01, 0.02, 0.05]
    colors = [GREEN, ORANGE, RED]
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    x = np.arange(len(fleets))
    width = 0.23
    for index, (rate, color) in enumerate(zip(rates, colors, strict=True)):
        selected = {int(row["fleet_size"]): row for row in data if float(row["configured_failure_rate"]) == rate}
        values = np.array([float(selected[f]["median_adoption_rate"]) * 100 for f in fleets])
        q1 = np.array([float(selected[f]["q1_adoption_rate"]) * 100 for f in fleets])
        q3 = np.array([float(selected[f]["q3_adoption_rate"]) * 100 for f in fleets])
        positions = x + (index - 1) * width
        ax.bar(positions, values, width, color=color, label=f"Failure setting {rate * 100:.0f}%")
        ax.errorbar(positions, values, yerr=np.vstack((values - q1, q3 - values)), fmt="none", ecolor="#111111", capsize=2, lw=0.9)
    ax.set_xticks(x, [str(value) for value in fleets])
    ax.set_xlabel("Fleet size (devices)")
    ax.set_ylabel("Final adoption (%)")
    ax.set_ylim(0, 104)
    ax.set_title("Fleet Outcome Distribution")
    ax.grid(axis="y", alpha=0.22)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.18))
    ax.set_axisbelow(True)
    finish(fig, "fig6_fleet_scaling_outcomes")


def failure_rate() -> None:
    data = rows("results/reviewer_revision/statistics/fleet_outcome_categories.csv")
    fig, axes = plt.subplots(1, 3, figsize=(9.0, 3.3), layout="constrained")
    for ax, outcome, color in zip(axes, ["SUCCESS", "ROLLBACK", "FAIL"], [GREEN, ORANGE, RED], strict=True):
        selected = sorted([row for row in data if int(row["fleet_size"]) == 500 and row["outcome"] == outcome], key=lambda row: float(row["configured_failure_rate"]))
        x = np.array([float(row["configured_failure_rate"]) * 100 for row in selected])
        mean = np.array([float(row["mean"]) for row in selected])
        low = np.array([float(row["mean_ci95_low"]) for row in selected])
        high = np.array([float(row["mean_ci95_high"]) for row in selected])
        ax.errorbar(x, mean, yerr=np.vstack((mean - low, high - mean)), color=color, marker="o", lw=1.6, capsize=4)
        ax.set_title(outcome.title(), fontsize=12)
        ax.set_xticks(x)
        ax.set_xlim(.6, 5.4)
        ax.set_ylim((93, 100) if outcome == "SUCCESS" else (0, 4.5))
        ax.set_xlabel("Configured failure rate (%)", fontsize=10)
        ax.set_ylabel("Mean outcome share (%)", fontsize=10)
        ax.grid(axis="y", alpha=.22)
    fig.suptitle("Failure-Rate Sensitivity: 500-Device Cohort", fontsize=14)
    finish(fig, "fig7_failure_rate_sensitivity")


def network() -> None:
    data = rows("results/reviewer_revision/csv/network_sensitivity.csv")
    labels = [
        f"{row['profile']}  |  {row['configured_application_delay_ms']} ms delay  |  "
        f"{row['configured_read_rate_limit_mbps']} Mbps read limit"
        for row in data
    ]
    raw_path = ROOT / "results/reviewer_revision/raw/network/application_shaped_fetches.jsonl"
    observed = [json.loads(line) for line in raw_path.read_text().splitlines() if line]
    values = [[float(item["retrieval_time_seconds"]) for item in observed if item["profile"] == row["profile"]] for row in data]
    y = np.arange(len(data))
    fig, ax = plt.subplots(figsize=(7.4, 3.6), layout="constrained")
    colors = [TEAL, TEAL, PURPLE]
    boxes = ax.boxplot(values, positions=y, vert=False, widths=.42, patch_artist=True, showfliers=False,
                       medianprops={"color": "#111111", "linewidth": 1.3})
    for box, color in zip(boxes["boxes"], colors, strict=True):
        box.set_facecolor(color)
        box.set_alpha(.22)
    rng = np.random.default_rng(20260828)
    for yi, group, color in zip(y, values, colors, strict=True):
        ax.scatter(group, yi + rng.uniform(-.12, .12, len(group)), s=15, color=color, alpha=.75, zorder=3)
    maximum = max(max(group) for group in values)
    max_group = next(index for index, group in enumerate(values) if maximum in group)
    ax.annotate(f"{maximum:.3f} s", (maximum, max_group), xytext=(-8, 20), textcoords="offset points", ha="right", fontsize=9)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlabel("End-to-end retrieval time (s, log scale)")
    ax.set_xscale("log")
    ax.set_xlim(min(min(group) for group in values) * .75, maximum * 1.5)
    ax.set_title("Local IPFS Retrieval Sensitivity")
    ax.grid(axis="x", alpha=0.22)
    ax.set_axisbelow(True)
    finish(fig, "fig8_network_sensitivity")


def cache() -> None:
    data = rows("results/reviewer_revision/csv/edge_cache_ablation.csv")
    by_mode = {row["cache_mode"]: row for row in data}
    modes = ["OFF", "ON"]
    labels = ["Cache OFF", "Cache ON"]
    origin_mib = [float(by_mode[mode]["median_origin_bytes_transferred"]) / (1024 * 1024) for mode in modes]
    elapsed = [float(by_mode[mode]["median_total_retrieval_time_seconds"]) for mode in modes]
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 3.7))
    y = np.arange(2)
    axes[0].barh(y, origin_mib, color=[RED, GREEN], height=0.55)
    axes[0].set_yticks(y, labels)
    axes[0].invert_yaxis()
    axes[0].set_xlabel("Origin transfer (MiB)")
    axes[0].set_xscale("log")
    axes[0].grid(axis="x", alpha=0.22)
    axes[1].barh(y, elapsed, color=[RED, GREEN], height=0.55)
    axes[1].set_yticks(y, labels)
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Total retrieval time (s)")
    axes[1].grid(axis="x", alpha=0.22)
    fig.suptitle("Edge-Cache Ablation", y=1.01, fontsize=14)
    for ax in axes:
        ax.set_axisbelow(True)
    fig.tight_layout()
    finish(fig, "fig9_edge_cache_ablation")


def accountability() -> None:
    data = rows("results/reviewer_revision/csv/accountability_ablation.csv")
    fleets = [100, 500, 1000]
    batches = [25, 50, 100, 200]
    modes = ["v1_integrity_root", "v2_complete_witnessed"]
    labels = {"v1_integrity_root": "V1 integrity root", "v2_complete_witnessed": "V2 witnessed commitment"}
    colors = {"v1_integrity_root": TEAL, "v2_complete_witnessed": PURPLE}
    markers = {"v1_integrity_root": "o", "v2_complete_witnessed": "s"}
    fig, axes = plt.subplots(3, 2, figsize=(8.2, 7.3), sharex=True)
    for row_index, fleet in enumerate(fleets):
        naive = {
            batch: next(row for row in data if int(row["fleet_size"]) == fleet and int(row["batch_size"]) == batch and row["reporting_mode"] == "naive_per_device")
            for batch in batches
        }
        for mode in modes:
            selected = [
                next(row for row in data if int(row["fleet_size"]) == fleet and int(row["batch_size"]) == batch and row["reporting_mode"] == mode)
                for batch in batches
            ]
            storage_values = [100 * int(row["formula_storage_slot_bytes"]) / int(naive[batch]["formula_storage_slot_bytes"]) for row, batch in zip(selected, batches, strict=True)]
            gas_values = [100 * int(row["formula_gas_from_path_median"]) / int(naive[batch]["formula_gas_from_path_median"]) for row, batch in zip(selected, batches, strict=True)]
            axes[row_index, 0].plot(batches, storage_values, color=colors[mode], marker=markers[mode], linewidth=2, label=labels[mode])
            axes[row_index, 1].plot(batches, gas_values, color=colors[mode], marker=markers[mode], linewidth=2, label=labels[mode])
        axes[row_index, 0].set_ylabel(f"{fleet} devices\nRelative footprint (%)")
        axes[row_index, 1].set_ylabel(f"{fleet} devices\nRelative gas (%)")
        for ax in axes[row_index]:
            ax.grid(axis="y", alpha=0.22)
            ax.set_axisbelow(True)
    axes[0, 0].set_title("On-chain storage")
    axes[0, 1].set_title("Transaction gas")
    axes[-1, 0].set_xlabel("Batch size (devices)")
    axes[-1, 1].set_xlabel("Batch size (devices)")
    axes[0, 0].legend(frameon=False, loc="upper right")
    fig.suptitle("Storage-Bounded Accountability", y=1.01, fontsize=14)
    fig.tight_layout()
    finish(fig, "fig10_storage_bounded_accountability")


def validator_faults() -> None:
    data = rows("results/reviewer_revision/csv/validator_faults.csv")
    cases = [
        "zero_validators_stopped", "one_validator_stopped", "two_validators_stopped",
        "quorum_restored_after_validator_restart",
    ]
    labels = ["0 stopped", "1 stopped", "2 stopped", "Restart to 3 active"]
    values = [[int(row["observed_block_delta"]) for row in data if row["fault_case"] == case] for case in cases]
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 4.0), gridspec_kw={"width_ratios": [1.2, 1]})
    ax = axes[0]
    positions = np.arange(len(cases))
    progress_trials = [sum(value > 0 for value in group) for group in values]
    ax.bar(positions, progress_trials, color=[BLUE, GREEN, RED, PURPLE], width=0.58)
    ax.set_xticks(positions, ["4 active", "3 active", "2 active", "Restart\nto 3"])
    ax.set_yticks(range(6))
    ax.set_ylim(0, 5.6)
    for position, count in zip(positions, progress_trials, strict=True):
        ax.text(position, count + 0.12, f"{count}/5", ha="center")
    ax.set_ylabel("Trials with block progress")
    ax.set_title("Quorum liveness")
    ax.grid(axis="y", alpha=0.22)
    ax.set_axisbelow(True)
    restored = [row for row in data if row["fault_case"] == cases[-1]]
    trial = [int(row["trial"]) for row in restored]
    axes[1].plot(trial, [float(row["restart_to_first_block_seconds"]) for row in restored],
                 color=TEAL, marker="o", label="First block")
    axes[1].plot(trial, [float(row["restart_to_first_receipt_seconds"]) for row in restored],
                 color=PURPLE, marker="x", linestyle="--", label="First receipt")
    axes[1].set_xticks(trial)
    axes[1].set_xlabel("Independent trial")
    axes[1].set_ylabel("Time from restart (s)")
    axes[1].set_ylim(bottom=0)
    axes[1].set_title("Quorum restoration")
    axes[1].legend(frameon=False)
    axes[1].grid(axis="y", alpha=0.22)
    fig.suptitle("Validator Crash-Fault Boundary and Restoration", y=1.04, fontsize=14)
    fig.tight_layout()
    finish(fig, "fig11_validator_fault_boundary")


def experimental_setup() -> None:
    fig, ax = plt.subplots(figsize=(10.0, 5.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")
    boxes = [
        (0.3, 3.8, 1.8, 1.25, "Release package", "Firmware, manifest,\nSBOM, provenance", BLUE),
        (2.5, 3.8, 2.0, 1.25, "Local IPFS", "CID-addressed artifact\nand edge-cache origin", GREEN),
        (5.0, 3.65, 2.2, 1.55, "Four-validator Besu", "IBFT2 control plane\nV1 and V2 contracts", PURPLE),
        (7.7, 3.8, 2.0, 1.25, "Role clients", "Vendor, security, regulator,\noperator, auditor", ORANGE),
        (0.8, 1.0, 2.2, 1.3, "HTTP / SQLite", "Persistent governance-path\ncomparison", TEAL),
        (3.8, 0.8, 2.4, 1.7, "Software fleet", "100 / 500 / 1,000 devices\nSigned receipts and Merkle roots", GREEN),
        (7.0, 1.0, 2.2, 1.3, "Evidence pipeline", "Raw logs, CSV, statistics,\nvalidation and checksums", BLUE),
    ]
    for x, y, w, h, title, body, color in boxes:
        ax.add_patch(Rectangle((x, y), w, h, facecolor="white", edgecolor=color, linewidth=1.5))
        ax.text(x + w / 2, y + h * 0.68, title, ha="center", va="center", fontsize=11, weight="bold", color=color)
        ax.text(x + w / 2, y + h * 0.30, body, ha="center", va="center", fontsize=9)
    arrows = [
        ((2.1, 4.42), (2.5, 4.42)), ((4.5, 4.42), (5.0, 4.42)), ((7.7, 4.42), (7.2, 4.42)),
        ((6.1, 3.65), (5.2, 2.5)), ((3.0, 1.65), (3.8, 1.65)), ((6.2, 1.65), (7.0, 1.65)),
        ((8.1, 3.8), (8.1, 2.3)), ((1.9, 2.3), (1.9, 3.8)),
    ]
    for start, end in arrows:
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=12, linewidth=1.1, color=GRAY))
    ax.text(5, 5.72, "LedgerGuard Experimental Setup", ha="center", va="center", fontsize=16, weight="bold")
    finish(fig, "fig4_experimental_setup")


def main() -> None:
    generators = {4: experimental_setup, 5: control_plane, 6: fleet, 7: failure_rate, 8: network, 9: cache, 10: accountability, 11: validator_faults}
    parser = argparse.ArgumentParser()
    parser.add_argument("--figures", type=int, nargs="+", choices=generators, default=list(generators))
    args = parser.parse_args()
    for number in args.figures:
        generators[number]()
    print(f"generated {len(args.figures)} PDF and PNG figures in {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

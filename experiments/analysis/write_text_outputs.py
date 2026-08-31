#!/usr/bin/env python3
"""Generate manuscript text insertions and final upgrade summary."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
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

def rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def status_counts(csv_dir: Path) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for name in STRONG_EVAL_CSVS:
        path = csv_dir / name
        if not path.exists():
            continue
        counts: dict[str, int] = {}
        for row in rows(path):
            status = row.get("status") or row.get("result") or row.get("measurement_status") or row.get("evidence_type") or "recorded"
            counts[status] = counts.get(status, 0) + 1
        out[path.name] = counts
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results")
    args = parser.parse_args()

    results = Path(args.results_dir)
    csv_dir = results / "csv"
    validation = results / "validation"
    text_dir = Path("paper_assets/text_insertions")
    text_dir.mkdir(parents=True, exist_ok=True)
    validation.mkdir(parents=True, exist_ok=True)

    setup = """# Experimental Setup Update

The evaluation uses a reproducible local LedgerGuard PoC with a Solidity/Besu control-plane design, off-chain content-addressed artifact metadata, deterministic receipt generation, and Merkle-rooted outcome accountability. A SQLite OTA controller is included as a centralized baseline with persistent release, approval, rollout, outcome, artifact metadata, and append-only audit-log tables.

Unavailable infrastructure is not substituted with fabricated measurements. Distributed validator timing, traffic-shaped network retrieval, HIL execution, and optional static-analysis tools are marked as not_run, scenario, configured, or unavailable unless raw evidence exists.
"""
    results_update = """# Results Update

Current generated results support the SQLite baseline, imported Besu-backed local control-plane evidence, Docker-based validator resource snapshots, local IPFS retrieval benchmarking, and formula-derived accountability scaffolding. WAN/network-shaping and HIL rows remain explicitly status-labeled when the required runtime or hardware is absent. The wording should use "all executed cases passed" only when every executed adversarial case passes, and should avoid unsupported broad claims.
"""
    limitations = """# Limitations Update

The current package does not claim production secure boot enforcement, physical A/B partition recovery, measured hardware validation, real WAN behavior, or measured validator database growth unless those logs are added. Formula and scenario rows are useful for sensitivity framing but must not be described as collected measurements.
"""
    (text_dir / "experimental_setup_update.md").write_text(setup, encoding="utf-8")
    (text_dir / "results_update.md").write_text(results_update, encoding="utf-8")
    (text_dir / "limitations_update.md").write_text(limitations, encoding="utf-8")

    counts = status_counts(csv_dir)
    governance_counts = counts.get("governance_timing.csv", {})
    adversarial_counts = counts.get("adversarial_validation.csv", {})
    security_counts = counts.get("security_checks.csv", {})
    governance_executed = governance_counts.get("executed", 0) + governance_counts.get("passed", 0)
    adversarial_passed = adversarial_counts.get("passed", 0)
    foundry_passed = security_counts.get("passed", 0)

    executed_lines = [
        "- SQLite centralized OTA baseline when Python/SQLite completed successfully.",
        "- Result aggregation, workbook/table/figure generation, and validation.",
    ]
    if governance_executed:
        executed_lines.append("- Besu-backed local PoC governance, rollout, and outcome-root operations imported from raw evidence.")
    if adversarial_passed:
        executed_lines.append("- Besu-backed adversarial PoC cases imported from raw evidence.")
    if foundry_passed:
        executed_lines.append("- Foundry smart-contract tests through Docker.")

    not_run_lines = [
        "- HIL execution unless a hardware configuration is provided.",
        "- Slither/Mythril if the tools are unavailable.",
    ]
    if not governance_executed:
        not_run_lines.insert(0, "- Besu-backed governance repetitions unless Docker/Besu is accessible.")

    supported_claims = [
        "- Reproducible evaluation structure with raw evidence/status files.",
        "- SQLite centralized OTA baseline behavior when status is executed.",
        "- Merkle accountability storage comparison as formula-derived output.",
    ]
    if governance_executed:
        supported_claims.append("- Besu-backed local PoC control-plane operations for the imported run.")
    if adversarial_passed:
        supported_claims.append("- The executed adversarial cases shown as `passed` in `adversarial_validation.csv` behaved as expected.")
    if foundry_passed:
        supported_claims.append("- Smart-contract tests shown as `passed` in `security_checks.csv` completed successfully.")

    lines = [
        "# LedgerGuard Final Upgrade Summary",
        "",
        f"- generated_at_utc: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}",
        "",
        "## What Was Executed",
        "",
        *executed_lines,
        "",
        "## What Was Not Run",
        "",
        *not_run_lines,
        "",
        "## Scenario or Configured Outputs",
        "",
        "- Network and edge-cache rows are scenario/configured unless traffic shaping and retrieval logs exist.",
        "- Accountability ablation rows are formula-derived unless gas/database evidence is added.",
        "",
        "## CSV Status Summary",
        "",
        "```json",
        json.dumps(counts, indent=2, sort_keys=True),
        "```",
        "",
        "## Commands To Reproduce",
        "",
        "```bash",
        "./poc run --suite strong_eval",
        "./poc results --suite strong_eval",
        "python experiments/analysis/validate_results.py",
        "```",
        "",
        "## Supported Claims",
        "",
        *supported_claims,
        "",
        "## Unsupported Claims",
        "",
        "- Ultra-low DLT timing claims below normal block-level timing.",
        "- Universal attack-detection claims.",
        "- Production-readiness claims beyond the validated PoC scope.",
        "- Measured HIL, network, or validator database growth without logs.",
        "",
        "## Recommended Manuscript Changes",
        "",
        "- Separate executed, scenario, configured, and not-run rows in results tables.",
        "- Replace broad security claims with case-specific outcomes.",
        "- Describe network/cache/accountability outputs according to their evidence_type.",
    ]
    (validation / "final_upgrade_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (validation / "upgrade_changelog.md").write_text(
        "# LedgerGuard Upgrade Changelog\n\n"
        f"- generated_at_utc: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}\n"
        "- Added copy-only archival before strong evaluation runs.\n"
        "- Added exact strong-evaluation runner names and CSV output names.\n"
        "- Added repository audit, environment version capture, validation JSON, and final summary.\n"
        "- Added manuscript text insertion files and corrected device workflow figure assets.\n",
        encoding="utf-8",
    )
    print(validation / "final_upgrade_summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

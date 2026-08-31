#!/usr/bin/env python3
"""Run and record the fixed-seed Foundry fuzz and invariant campaign."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SEED = "0x4c656467657247756172642d56322d66757a7a2d323032362d30382d3239"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--forge", default="forge")
    parser.add_argument("--solc", default="solc")
    parser.add_argument("--reuse-existing-coverage", action="store_true")
    args = parser.parse_args()
    raw_path = ROOT / "results/reviewer_revision/raw/security/foundry_final.txt"
    status_path = ROOT / "results/reviewer_revision/validation/foundry_final_status.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.parent.mkdir(parents=True, exist_ok=True)

    version = subprocess.run([args.forge, "--version"], text=True, capture_output=True, check=False)
    command = [
        args.forge, "test", "--root", "contracts", "--offline", "--use", args.solc, "-vv",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    report = completed.stdout + completed.stderr
    raw_path.write_text(report, encoding="utf-8")

    coverage_path = ROOT / "results/reviewer_revision/raw/security/foundry_coverage_final.txt"
    coverage_command = [
        args.forge, "coverage", "--root", "contracts", "--offline", "--use", args.solc,
        "--ir-minimum", "--report", "summary", "--report", "lcov", "--report-file",
        str(ROOT / "results/reviewer_revision/raw/security/foundry_coverage_final.info"),
    ]
    if args.reuse_existing_coverage:
        coverage_returncode = 0 if coverage_path.exists() else 1
    else:
        coverage = subprocess.run(coverage_command, cwd=ROOT, text=True, capture_output=True, check=False)
        coverage_returncode = coverage.returncode
        coverage_path.write_text(coverage.stdout + coverage.stderr, encoding="utf-8")
    coverage_report = coverage_path.read_text(encoding="utf-8") if coverage_path.exists() else ""
    if not args.reuse_existing_coverage:
        probe = subprocess.run([args.forge, "coverage", "--root", "contracts", "--offline", "--use", args.solc,
                                "--report", "summary"], cwd=ROOT, text=True, capture_output=True, check=False)
        (raw_path.parent / "coverage_without_ir_probe.txt").write_text(probe.stdout + probe.stderr, encoding="utf-8")
    coverage_match = re.search(
        r"\| Total\s+\|\s+([0-9.]+)% \((\d+)/(\d+)\)\s+\|\s+"
        r"([0-9.]+)% \((\d+)/(\d+)\)\s+\|\s+([0-9.]+)% \((\d+)/(\d+)\)\s+\|\s+"
        r"([0-9.]+)% \((\d+)/(\d+)\)",
        coverage_report,
    )

    fuzz_match = re.search(r"testFuzzCompletenessReconciliation.*runs: (\d+)", report)
    invariant_match = re.search(
        r"invariantFinalizedCountersReconcileExpectedCohort\(\) \(runs: (\d+), calls: (\d+), reverts: (\d+)\)",
        report,
    )
    total_match = re.search(r"\((\d+) total tests\)", report)
    passed = (
        completed.returncode == 0
        and fuzz_match is not None and int(fuzz_match.group(1)) == 10_000
        and invariant_match is not None and int(invariant_match.group(1)) == 256
        and int(invariant_match.group(2)) == 128_000
        and coverage_returncode == 0 and coverage_match is not None
    )
    status = {
        "status": "PASS" if passed else "FAIL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "foundry_version": version.stdout.strip(),
        "exact_command": "forge test --root contracts --offline --use <SOLC_0.8.24_BINARY> -vv",
        "exit_code": completed.returncode,
        "test_count": int(total_match.group(1)) if total_match else None,
        "test_seed": SEED,
        "fuzz_seed": SEED,
        "invariant_seed": SEED,
        "seed_scope": "Foundry shared fuzz seed from profile.default.fuzz.seed",
        "dedicated_fuzz_runs": int(fuzz_match.group(1)) if fuzz_match else None,
        "invariant_runs": int(invariant_match.group(1)) if invariant_match else None,
        "invariant_depth": 500,
        "invariant_calls": int(invariant_match.group(2)) if invariant_match else None,
        "invariant_reverts": int(invariant_match.group(3)) if invariant_match else None,
        "fail_on_revert": False,
        "handler_contracts": ["V2InvariantHandler"],
        "target_selectors": ["createAndFinalize(uint16,uint16,bytes32)"],
        "raw_report": str(raw_path.relative_to(ROOT)),
        "coverage_exact_command": "forge coverage --root contracts --offline --use <SOLC_0.8.24_BINARY> --ir-minimum --report summary --report lcov --report-file results/reviewer_revision/raw/security/foundry_coverage_final.info",
        "coverage": {
            "line_percent": float(coverage_match.group(1)) if coverage_match else None,
            "statement_percent": float(coverage_match.group(4)) if coverage_match else None,
            "branch_percent": float(coverage_match.group(7)) if coverage_match else None,
            "function_percent": float(coverage_match.group(10)) if coverage_match else None,
            "raw_report": str(coverage_path.relative_to(ROOT)),
            "lcov_report": "results/reviewer_revision/raw/security/foundry_coverage_final.info",
            "instrumentation": "viaIR minimum optimization; source-mapping warning retained",
        },
    }
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

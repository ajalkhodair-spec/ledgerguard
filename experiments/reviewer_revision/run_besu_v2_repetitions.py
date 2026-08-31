#!/usr/bin/env python3
"""Run repeated LedgerGuard V2 governance paths against the local four-validator Besu network."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEVICE_TYPE = "0x" + "4d34" + "00" * 30
CSV_COLUMNS = [
    "run_id", "repetition", "operation", "submitted_at_utc", "receipt_observed_at_utc",
    "submitted_at_ns", "receipt_observed_at_ns", "latency_seconds", "tx_hash", "block_number",
    "transaction_index", "gas_used", "tx_status", "submission_head_block", "inclusion_delay_blocks",
    "first_eligible_block", "receipt_poll_interval_seconds", "configured_block_period_seconds",
    "validator_count", "chain_id", "evidence_type", "error_message", "raw_evidence_path",
]


def utc_from_ns(value: int) -> str:
    return datetime.fromtimestamp(value / 1_000_000_000, timezone.utc).isoformat().replace("+00:00", "Z")


def parse_json_output(output: str) -> dict[str, Any]:
    start = output.find("{")
    if start < 0:
        raise ValueError("JSON output missing")
    value, _end = json.JSONDecoder().raw_decode(output[start:])
    return value


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def rpc_quantity(cast: str, rpc: str, method: str, cwd: Path) -> int:
    result = run([cast, "rpc", "--rpc-url", rpc, method], cwd)
    if result.returncode:
        raise RuntimeError(result.stderr)
    value = json.loads(result.stdout)
    return int(value, 16)


def call(cast: str, rpc: str, target: str, signature: str, values: list[str], cwd: Path) -> str:
    result = run([cast, "call", "--rpc-url", rpc, target, signature, *values], cwd)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout.strip().split()[0]


def bytes32(value: int) -> str:
    return "0x" + f"{value:064x}"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=50)
    parser.add_argument("--start-repetition", type=int, default=1)
    parser.add_argument("--rpc", default="http://127.0.0.1:8545")
    parser.add_argument("--cast", default=os.environ.get("CAST_BIN", "cast"))
    parser.add_argument(
        "--deployment", default=str(ROOT / "results/reviewer_revision/raw/besu_v2_final/deployment.json")
    )
    parser.add_argument(
        "--csv", default=str(ROOT / "results/reviewer_revision/csv/besu_v2_final_timing.csv")
    )
    parser.add_argument(
        "--raw", default=str(ROOT / "results/reviewer_revision/raw/besu_v2_final/governance_transactions.jsonl")
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    private_keys = {
        "vendor": os.environ.get("LEDGERGUARD_DEPLOYER_PRIVATE_KEY", ""),
        "security": os.environ.get("LEDGERGUARD_SECURITY_PRIVATE_KEY", ""),
        "regulator": os.environ.get("LEDGERGUARD_REGULATOR_PRIVATE_KEY", ""),
        "operator": os.environ.get("LEDGERGUARD_OPERATOR_PRIVATE_KEY", ""),
        "auditor": os.environ.get("LEDGERGUARD_AUDITOR_PRIVATE_KEY", ""),
    }
    missing = [name for name, value in private_keys.items() if not value]
    if missing:
        raise RuntimeError(f"missing private-key environment variables for: {', '.join(missing)}")

    deployment = json.loads(Path(args.deployment).read_text(encoding="utf-8"))
    contracts = {name: value["deployedTo"] for name, value in deployment["contracts"].items()}
    contracts_dir = ROOT / "contracts"
    csv_path = Path(args.csv)
    raw_path = Path(args.raw)
    rows: list[dict[str, Any]] = []
    if args.resume and csv_path.exists():
        rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    elif csv_path.exists() or raw_path.exists():
        raise RuntimeError("output exists; use --resume or choose fresh output paths")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    completed = {int(row["repetition"]) for row in rows if row["operation"] == "confirm_outcome_summary" and row["tx_status"] == "success"}
    try:
        raw_evidence_label = str(raw_path.relative_to(ROOT))
    except ValueError:
        raw_evidence_label = str(raw_path)

    def send_timed(rep: int, operation: str, actor: str, target: str, signature: str, values: list[str]) -> bool:
        submission_head = rpc_quantity(args.cast, args.rpc, "eth_blockNumber", contracts_dir)
        command = [
            args.cast, "send", "--rpc-url", args.rpc, "--private-key", private_keys[actor], "--legacy",
            "--gas-price", "0", "--poll-interval", "1", "--json", target, signature, *values,
        ]
        start_ns = time.time_ns()
        result = run(command, contracts_dir)
        end_ns = time.time_ns()
        receipt: dict[str, Any] = {}
        error = ""
        try:
            receipt = parse_json_output(result.stdout)
        except (ValueError, json.JSONDecodeError):
            error = (result.stderr or result.stdout).strip()
        block_number = int(receipt.get("blockNumber", "0x0"), 16)
        tx_ok = result.returncode == 0 and receipt.get("status") == "0x1"
        row = {
            "run_id": f"besu_v2_rep{rep:03d}", "repetition": rep, "operation": operation,
            "submitted_at_utc": utc_from_ns(start_ns), "receipt_observed_at_utc": utc_from_ns(end_ns),
            "submitted_at_ns": start_ns, "receipt_observed_at_ns": end_ns,
            "latency_seconds": f"{(end_ns - start_ns) / 1_000_000_000:.9f}",
            "tx_hash": receipt.get("transactionHash", ""), "block_number": block_number or "",
            "transaction_index": int(receipt.get("transactionIndex", "0x0"), 16) if receipt else "",
            "gas_used": int(receipt.get("gasUsed", "0x0"), 16) if receipt else "",
            "tx_status": "success" if tx_ok else "failed", "submission_head_block": submission_head,
            "inclusion_delay_blocks": block_number - submission_head if block_number else "",
            "first_eligible_block": block_number == submission_head + 1 if block_number else "",
            "receipt_poll_interval_seconds": 1, "configured_block_period_seconds": 2,
            "validator_count": 4, "chain_id": 1337, "evidence_type": "local_besu_measurement",
            "error_message": error, "raw_evidence_path": raw_evidence_label,
        }
        rows.append(row)
        with raw_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row | {"receipt": receipt}, sort_keys=True) + "\n")
        write_csv(csv_path, rows)
        return tx_ok

    stop_repetition = args.start_repetition + args.repetitions
    for rep in range(args.start_repetition, stop_repetition):
        if rep in completed:
            continue
        release_id = int(call(args.cast, args.rpc, contracts["FirmwareRegistry"], "nextReleaseId()(uint256)", [], contracts_dir), 0)
        rollout_id = bytes32(10_000 + rep)
        cohort_id = bytes32(20_000 + rep)
        cohort_commitment = bytes32(30_000 + rep)
        receipt_root = bytes32(40_000 + rep)
        terminal_outcome_root = bytes32(45_000 + rep)
        operations = [
            (
                "register_release", "vendor", contracts["FirmwareRegistry"],
                "registerRelease(bytes32,uint64,string,bytes32,uint32,bytes32,bytes32,uint32,uint64)",
                [DEVICE_TYPE, str(rep), f"bafyreviewerv2{rep:04d}", bytes32(50_000 + rep), "524288", bytes32(60_000 + rep), bytes32(70_000 + rep), "0", "0"],
            ),
            ("security_approval", "security", contracts["FirmwareRegistry"], "approveRelease(uint256)", [str(release_id)]),
            ("regulator_approval", "regulator", contracts["FirmwareRegistry"], "approveRelease(uint256)", [str(release_id)]),
            (
                "start_rollout", "operator", contracts["RolloutCoordinatorV2"],
                "startRollout(uint256,bytes32,uint16)", [str(release_id), DEVICE_TYPE, "9500"],
            ),
            (
                "register_cohort", "operator", contracts["DeviceAttestationV2"],
                "registerCohort(uint256,bytes32,uint32,bytes32,bytes32,uint32,uint64)",
                [str(release_id), rollout_id, "1", cohort_id, cohort_commitment, "1000", "4102444800"],
            ),
        ]
        rep_ok = True
        for operation in operations:
            if not send_timed(rep, *operation):
                rep_ok = False
                break
        if not rep_ok:
            continue
        cohort_key = call(
            args.cast, args.rpc, contracts["DeviceAttestationV2"],
            "cohortKey(uint256,bytes32,uint32)(bytes32)", [str(release_id), rollout_id, "1"], contracts_dir,
        )
        outcome_values = [cohort_key, receipt_root, terminal_outcome_root, "1000", "980", "10", "5", "5", "0"]
        if not send_timed(
            rep, "propose_outcome_summary", "operator", contracts["DeviceAttestationV2"],
            "proposeSummary(bytes32,bytes32,bytes32,uint32,uint32,uint32,uint32,uint32,uint32)", outcome_values,
        ):
            continue
        send_timed(
            rep, "confirm_outcome_summary", "auditor", contracts["DeviceAttestationV2"],
            "confirmSummary(bytes32,bytes32,bytes32,uint32,uint32,uint32,uint32,uint32,uint32)", outcome_values,
        )
        print(f"completed repetition {rep}/{stop_repetition - 1}", flush=True)

    attempted = len({int(row["repetition"]) for row in rows})
    successful = len({int(row["repetition"]) for row in rows if row["operation"] == "confirm_outcome_summary" and row["tx_status"] == "success"})
    print(json.dumps({"attempted_repetitions": attempted, "completed_repetitions": successful, "rows": len(rows), "csv": str(csv_path)}))


if __name__ == "__main__":
    main()

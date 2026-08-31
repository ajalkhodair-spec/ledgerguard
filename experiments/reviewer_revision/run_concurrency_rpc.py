#!/usr/bin/env python3
"""Exercise V2 optimistic-concurrency and replay guards through parallel Besu RPC submissions."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
DEVICE_TYPE = "0x" + "4d34" + "00" * 30
CASE_COLUMNS = [
    "trial", "test_case", "contender_count", "successful_transactions", "reverted_transactions",
    "same_block", "observed_final_state", "expected_invariant", "invariant_satisfied",
    "evidence_type", "raw_evidence_path",
]


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=CONTRACTS, text=True, capture_output=True, check=False)


def parse_json_output(output: str) -> dict[str, Any]:
    start = output.find("{")
    if start < 0:
        raise RuntimeError(f"JSON output missing: {output[:200]}")
    return json.loads(output[start:])


def bytes32(value: int) -> str:
    return "0x" + f"{value:064x}"


def blocking_send(cast: str, rpc: str, key: str, target: str, signature: str, values: list[str]) -> dict[str, Any]:
    result = run([
        cast, "send", "--rpc-url", rpc, "--private-key", key, "--legacy", "--gas-price", "0",
        "--gas-limit", "700000", "--poll-interval", "1", "--json", target, signature, *values,
    ])
    receipt = parse_json_output(result.stdout)
    if result.returncode or receipt.get("status") != "0x1":
        raise RuntimeError((result.stderr or result.stdout).strip())
    return receipt


def nonce(cast: str, rpc: str, address: str) -> int:
    result = run([cast, "nonce", "--rpc-url", rpc, "--block", "pending", address])
    if result.returncode:
        raise RuntimeError(result.stderr)
    return int(result.stdout.strip(), 0)


def async_send(
    cast: str, rpc: str, key: str, tx_nonce: int, target: str, signature: str, values: list[str]
) -> dict[str, Any]:
    start_ns = time.time_ns()
    result = run([
        cast, "send", "--rpc-url", rpc, "--private-key", key, "--legacy", "--gas-price", "0",
        "--gas-limit", "700000", "--nonce", str(tx_nonce), "--async", target, signature, *values,
    ])
    end_ns = time.time_ns()
    tx_hash = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    if result.returncode or not tx_hash.startswith("0x"):
        raise RuntimeError((result.stderr or result.stdout).strip())
    return {"tx_hash": tx_hash, "nonce": tx_nonce, "submitted_at_ns": start_ns, "rpc_returned_at_ns": end_ns}


def wait_receipt(cast: str, rpc: str, tx: dict[str, Any], timeout_seconds: int = 30) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = run([cast, "rpc", "--rpc-url", rpc, "eth_getTransactionReceipt", tx["tx_hash"]])
        if result.returncode == 0:
            receipt = json.loads(result.stdout)
            if receipt:
                observed_ns = time.time_ns()
                return tx | {
                    "receipt_observed_at_ns": observed_ns,
                    "receipt_latency_seconds": (observed_ns - tx["submitted_at_ns"]) / 1_000_000_000,
                    "status": "success" if receipt["status"] == "0x1" else "reverted",
                    "block_number": int(receipt["blockNumber"], 16),
                    "transaction_index": int(receipt["transactionIndex"], 16),
                    "gas_used": int(receipt["gasUsed"], 16),
                    "receipt": receipt,
                }
        time.sleep(0.1)
    raise TimeoutError(f"receipt timeout for {tx['tx_hash']}")


def submit_pair(
    cast: str,
    rpc: str,
    contenders: list[tuple[str, str, int, str, str, list[str]]],
) -> list[dict[str, Any]]:
    barrier_ns = time.time_ns()
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = list(pool.map(lambda c: async_send(cast, rpc, c[1], c[2], c[3], c[4], c[5]), contenders))
    return [wait_receipt(cast, rpc, tx | {"contender": contenders[index][0], "barrier_ns": barrier_ns}) for index, tx in enumerate(pending)]


def call(cast: str, rpc: str, target: str, signature: str, values: list[str]) -> str:
    result = run([cast, "call", "--rpc-url", rpc, target, signature, *values])
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


def rollout_phase(cast: str, rpc: str, coordinator: str, release_id: int) -> int:
    output = call(
        cast, rpc, coordinator,
        "getRollout(uint256)((bytes32,uint8,uint16,uint64,uint64,uint64))", [str(release_id)],
    )
    match = re.match(r"\([^,]+,\s*(\d+)", output)
    if not match:
        raise RuntimeError(f"cannot decode rollout phase: {output}")
    return int(match.group(1))


def summary_state(cast: str, rpc: str, attestation: str, cohort_key: str) -> int:
    output = call(
        cast, rpc, attestation,
        "getSummary(bytes32)((bytes32,uint32,uint32,uint32,uint32,uint32,uint32,address,address,uint64,uint64,uint8))",
        [cohort_key],
    )
    match = re.search(r",\s*(\d+)\s*\)$", output)
    if not match:
        raise RuntimeError(f"cannot decode summary state: {output}")
    return int(match.group(1))


def cohort_key(cast: str, rpc: str, attestation: str, release_id: int, rollout_id: str) -> str:
    return call(
        cast, rpc, attestation, "cohortKey(uint256,bytes32,uint32)(bytes32)",
        [str(release_id), rollout_id, "1"],
    ).split()[0]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--rpc", default="http://127.0.0.1:8545")
    parser.add_argument("--cast", default=os.environ.get("CAST_BIN", "cast"))
    parser.add_argument("--deployment", default=str(ROOT / "results/reviewer_revision/raw/besu_v2_final/deployment.json"))
    parser.add_argument("--csv", default=str(ROOT / "results/reviewer_revision/csv/concurrency_and_replay_tests.csv"))
    parser.add_argument("--raw", default=str(ROOT / "results/reviewer_revision/raw/concurrency/rpc_races.jsonl"))
    parser.add_argument("--status", default=str(ROOT / "results/reviewer_revision/validation/concurrency_status.json"))
    args = parser.parse_args()

    keys = {
        "vendor": os.environ.get("LEDGERGUARD_DEPLOYER_PRIVATE_KEY") or os.environ.get("VENDOR_PRIVATE_KEY", ""),
        "security": os.environ.get("LEDGERGUARD_SECURITY_PRIVATE_KEY") or os.environ.get("SECURITY_PRIVATE_KEY", ""),
        "regulator": os.environ.get("LEDGERGUARD_REGULATOR_PRIVATE_KEY") or os.environ.get("REGULATOR_PRIVATE_KEY", ""),
        "operator": os.environ.get("LEDGERGUARD_OPERATOR_PRIVATE_KEY") or os.environ.get("OPERATOR_PRIVATE_KEY", ""),
        "auditor": os.environ.get("LEDGERGUARD_AUDITOR_PRIVATE_KEY") or os.environ.get("AUDITOR_PRIVATE_KEY", ""),
    }
    missing = [name for name, key in keys.items() if not key]
    if missing:
        raise RuntimeError(f"missing private-key environment variables for: {', '.join(missing)}")

    deployment = json.loads(Path(args.deployment).read_text(encoding="utf-8"))
    contracts = {name: data["deployedTo"] for name, data in deployment["contracts"].items()}
    addresses = deployment["actors"]
    csv_path, raw_path, status_path = Path(args.csv), Path(args.raw), Path(args.status)
    for path in (csv_path, raw_path, status_path):
        if path.exists():
            raise RuntimeError(f"output already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)

    case_rows: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []

    def record_case(trial: int, name: str, receipts: list[dict[str, Any]], final_state: str) -> None:
        successes = sum(tx["status"] == "success" for tx in receipts)
        reverted = sum(tx["status"] == "reverted" for tx in receipts)
        invariant = successes == 1 and reverted == 1
        row = {
            "trial": trial, "test_case": name, "contender_count": len(receipts),
            "successful_transactions": successes, "reverted_transactions": reverted,
            "same_block": len({tx["block_number"] for tx in receipts}) == 1,
            "observed_final_state": final_state,
            "expected_invariant": "exactly_one_competing_transition_succeeds",
            "invariant_satisfied": invariant, "evidence_type": "parallel_local_besu_rpc",
            "raw_evidence_path": str(raw_path.relative_to(ROOT)),
        }
        case_rows.append(row)
        for tx in receipts:
            raw_rows.append({"trial": trial, "test_case": name, **tx})
        if not invariant:
            raise AssertionError(f"concurrency invariant failed: {row}")

    for trial in range(1, args.trials + 1):
        release_id = int(call(
            args.cast, args.rpc, contracts["FirmwareRegistry"], "nextReleaseId()(uint256)", [],
        ).split()[0], 0)
        # Derive the version from persistent chain state so interrupted reruns
        # cannot reuse a version and lose latestApproved eligibility.
        unique = 1_000_000 + release_id
        blocking_send(
            args.cast, args.rpc, keys["vendor"], contracts["FirmwareRegistry"],
            "registerRelease(bytes32,uint64,string,bytes32,uint32,bytes32,bytes32,uint32,uint64)",
            [DEVICE_TYPE, str(unique), f"bafyconcurrency{trial:03d}", bytes32(unique), "524288", bytes32(unique + 100), bytes32(unique + 200), "0", "0"],
        )
        blocking_send(args.cast, args.rpc, keys["security"], contracts["FirmwareRegistry"], "approveRelease(uint256)", [str(release_id)])
        blocking_send(args.cast, args.rpc, keys["regulator"], contracts["FirmwareRegistry"], "approveRelease(uint256)", [str(release_id)])

        operator_nonce = nonce(args.cast, args.rpc, addresses["operator"])
        start_values = [str(release_id), DEVICE_TYPE, "9500"]
        receipts = submit_pair(args.cast, args.rpc, [
            ("start_a", keys["operator"], operator_nonce, contracts["RolloutCoordinatorV2"], "startRollout(uint256,bytes32,uint16)", start_values),
            ("start_b", keys["operator"], operator_nonce + 1, contracts["RolloutCoordinatorV2"], "startRollout(uint256,bytes32,uint16)", start_values),
        ])
        record_case(trial, "duplicate_start", receipts, f"phase={rollout_phase(args.cast, args.rpc, contracts['RolloutCoordinatorV2'], release_id)}")

        operator_nonce = nonce(args.cast, args.rpc, addresses["operator"])
        advance_values = [str(release_id), "1", "1", "98", "1", "1", "0", "0"]
        receipts = submit_pair(args.cast, args.rpc, [
            ("advance_a", keys["operator"], operator_nonce, contracts["RolloutCoordinatorV2"], "advanceRollout(uint256,uint8,uint64,uint32,uint32,uint32,uint32,uint32)", advance_values),
            ("advance_b", keys["operator"], operator_nonce + 1, contracts["RolloutCoordinatorV2"], "advanceRollout(uint256,uint8,uint64,uint32,uint32,uint32,uint32,uint32)", advance_values),
        ])
        record_case(trial, "stale_double_advance", receipts, f"phase={rollout_phase(args.cast, args.rpc, contracts['RolloutCoordinatorV2'], release_id)}")

        operator_nonce = nonce(args.cast, args.rpc, addresses["operator"])
        security_nonce = nonce(args.cast, args.rpc, addresses["security"])
        receipts = submit_pair(args.cast, args.rpc, [
            ("advance", keys["operator"], operator_nonce, contracts["RolloutCoordinatorV2"], "advanceRollout(uint256,uint8,uint64,uint32,uint32,uint32,uint32,uint32)", [str(release_id), "2", "2", "98", "1", "1", "0", "0"]),
            ("halt", keys["security"], security_nonce, contracts["RolloutCoordinatorV2"], "haltRollout(uint256,uint8,uint64)", [str(release_id), "2", "2"]),
        ])
        record_case(trial, "halt_vs_advance", receipts, f"phase={rollout_phase(args.cast, args.rpc, contracts['RolloutCoordinatorV2'], release_id)}")

        rollout_id = bytes32(910_000 + trial)
        blocking_send(
            args.cast, args.rpc, keys["operator"], contracts["DeviceAttestationV2"],
            "registerCohort(uint256,bytes32,uint32,bytes32,bytes32,uint32,uint64)",
            [str(release_id), rollout_id, "1", bytes32(920_000 + trial), bytes32(930_000 + trial), "100", "4102444800"],
        )
        key = cohort_key(args.cast, args.rpc, contracts["DeviceAttestationV2"], release_id, rollout_id)
        summary_values = [key, bytes32(940_000 + trial), bytes32(950_000 + trial), "100", "98", "1", "1", "0", "0"]
        operator_nonce = nonce(args.cast, args.rpc, addresses["operator"])
        receipts = submit_pair(args.cast, args.rpc, [
            ("proposal_a", keys["operator"], operator_nonce, contracts["DeviceAttestationV2"], "proposeSummary(bytes32,bytes32,bytes32,uint32,uint32,uint32,uint32,uint32,uint32)", summary_values),
            ("proposal_b", keys["operator"], operator_nonce + 1, contracts["DeviceAttestationV2"], "proposeSummary(bytes32,bytes32,bytes32,uint32,uint32,uint32,uint32,uint32,uint32)", summary_values),
        ])
        record_case(trial, "duplicate_summary_proposal", receipts, f"summary_state={summary_state(args.cast, args.rpc, contracts['DeviceAttestationV2'], key)}")

        auditor_nonce = nonce(args.cast, args.rpc, addresses["auditor"])
        receipts = submit_pair(args.cast, args.rpc, [
            ("confirmation_a", keys["auditor"], auditor_nonce, contracts["DeviceAttestationV2"], "confirmSummary(bytes32,bytes32,bytes32,uint32,uint32,uint32,uint32,uint32,uint32)", summary_values),
            ("confirmation_b", keys["auditor"], auditor_nonce + 1, contracts["DeviceAttestationV2"], "confirmSummary(bytes32,bytes32,bytes32,uint32,uint32,uint32,uint32,uint32,uint32)", summary_values),
        ])
        record_case(trial, "duplicate_summary_confirmation", receipts, f"summary_state={summary_state(args.cast, args.rpc, contracts['DeviceAttestationV2'], key)}")
        print(f"completed concurrency trial {trial}/{args.trials}", flush=True)

    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=CASE_COLUMNS)
        writer.writeheader()
        writer.writerows(case_rows)
    with raw_path.open("w", encoding="utf-8") as stream:
        for row in raw_rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")

    failed = sum(str(row["invariant_satisfied"]).lower() != "true" for row in case_rows)
    status = {
        "status": "PASS" if failed == 0 else "FAIL",
        "generated_at_utc": utc_now(),
        "parallel_rpc": True,
        "trials": args.trials,
        "cases": len(case_rows),
        "competing_transactions": len(raw_rows),
        "failed_invariants": failed,
        "all_pairs_in_same_block": all(row["same_block"] for row in case_rows),
        "private_keys_written_to_evidence": False,
        "csv": str(csv_path.relative_to(ROOT)),
        "raw": str(raw_path.relative_to(ROOT)),
    }
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, sort_keys=True))


if __name__ == "__main__":
    main()

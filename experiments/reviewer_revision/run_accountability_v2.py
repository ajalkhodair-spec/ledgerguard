#!/usr/bin/env python3
"""Compare per-device, V1 integrity-root, and V2 witnessed accountability on Besu."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
RAW_DIR = ROOT / "results/reviewer_revision/raw/accountability"
CSV_DIR = ROOT / "results/reviewer_revision/csv"
VALIDATION_DIR = ROOT / "results/reviewer_revision/validation"
FLEETS = (100, 500, 1000)
BATCHES = (25, 50, 100, 200)
MODES = ("naive_per_device", "v1_integrity_root", "v2_complete_witnessed")


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=CONTRACTS, text=True, capture_output=True, check=False)


def parse_json_output(output: str) -> dict[str, Any]:
    start = output.find("{")
    if start < 0:
        raise RuntimeError(f"JSON output missing: {output[:200]}")
    return json.loads(output[start:])


def bytes32(value: int) -> str:
    return "0x" + f"{value:064x}"


def directory_bytes(path: Path) -> int:
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def validator_sizes() -> dict[str, int]:
    sizes = {}
    for index in range(1, 5):
        path = ROOT / f"network/Node-{index}/data/database"
        sizes[f"node_{index}_bytes"] = directory_bytes(path)
    sizes["total_bytes"] = sum(sizes.values())
    return sizes


def nonce(cast: str, rpc: str, address: str) -> int:
    result = run([cast, "nonce", "--rpc-url", rpc, "--block", "pending", address])
    if result.returncode:
        raise RuntimeError(result.stderr)
    return int(result.stdout.strip(), 0)


def async_send(
    cast: str, rpc: str, key: str, tx_nonce: int, target: str,
    signature: str, values: list[str], operation: str,
) -> dict[str, Any]:
    start_ns = time.time_ns()
    result = run([
        cast, "send", "--rpc-url", rpc, "--private-key", key, "--legacy",
        "--gas-price", "0", "--gas-limit", "700000", "--nonce", str(tx_nonce),
        "--async", target, signature, *values,
    ])
    returned_ns = time.time_ns()
    tx_hash = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    if result.returncode or not tx_hash.startswith("0x"):
        raise RuntimeError((result.stderr or result.stdout).strip())
    return {
        "operation": operation, "tx_hash": tx_hash, "nonce": tx_nonce,
        "submitted_at_ns": start_ns, "rpc_returned_at_ns": returned_ns,
    }


def wait_receipt(
    cast: str, rpc: str, pending: dict[str, Any], timeout_seconds: int = 60,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = run([cast, "rpc", "--rpc-url", rpc, "eth_getTransactionReceipt", pending["tx_hash"]])
        if result.returncode == 0:
            receipt = json.loads(result.stdout)
            if receipt:
                observed_ns = time.time_ns()
                return pending | {
                    "receipt_observed_at_ns": observed_ns,
                    "latency_seconds": (observed_ns - pending["submitted_at_ns"]) / 1_000_000_000,
                    "status": "success" if receipt["status"] == "0x1" else "reverted",
                    "block_number": int(receipt["blockNumber"], 16),
                    "transaction_index": int(receipt["transactionIndex"], 16),
                    "gas_used": int(receipt["gasUsed"], 16),
                    "event_count": len(receipt["logs"]), "receipt": receipt,
                }
        time.sleep(0.1)
    raise TimeoutError(f"receipt timeout for {pending['tx_hash']}")


def submit_batch(
    cast: str, rpc: str, key: str, address: str, target: str,
    calls: list[tuple[str, str, list[str]]],
) -> list[dict[str, Any]]:
    first_nonce = nonce(cast, rpc, address)
    pending = [
        async_send(cast, rpc, key, first_nonce + index, target, signature, values, operation)
        for index, (operation, signature, values) in enumerate(calls)
    ]
    receipts = [wait_receipt(cast, rpc, tx) for tx in pending]
    failed = [receipt for receipt in receipts if receipt["status"] != "success"]
    if failed:
        raise RuntimeError(f"{len(failed)} transactions reverted in {calls[0][0]} batch")
    return receipts


def deploy_contract(
    forge: str, cast: str, rpc: str, deployer_key: str,
    contract: str, constructor_args: list[str],
) -> dict[str, Any]:
    start_ns = time.time_ns()
    command = [
        forge, "create", "--rpc-url", rpc, "--private-key", deployer_key,
        "--broadcast", "--legacy", "--gas-price", "0", "--json", contract,
    ]
    if constructor_args:
        command.extend(["--constructor-args", *constructor_args])
    result = run(command)
    end_ns = time.time_ns()
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip())
    deployment = parse_json_output(result.stdout)
    tx_hash = deployment["transactionHash"]
    receipt_result = run([cast, "rpc", "--rpc-url", rpc, "eth_getTransactionReceipt", tx_hash])
    receipt = json.loads(receipt_result.stdout)
    return {
        "contract": contract, "deployed_to": deployment["deployedTo"],
        "transaction_hash": tx_hash, "submitted_at_ns": start_ns,
        "receipt_observed_at_ns": end_ns, "gas_used": int(receipt["gasUsed"], 16),
        "receipt": receipt,
    }


def percentile(values: list[int], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def path_statistics(mode: str, paths: list[dict[str, Any]]) -> dict[str, Any]:
    gas = [int(path["gas_total"]) for path in paths]
    latency = [float(path["latency_total_seconds"]) for path in paths]
    q1, q3 = percentile(gas, 0.25), percentile(gas, 0.75)
    latency_ns = [round(value * 1_000_000_000) for value in latency]
    return {
        "reporting_mode": mode, "sample_count": len(paths), "gas_min": min(gas),
        "gas_q1": f"{q1:.3f}", "gas_median": f"{statistics.median(gas):.3f}",
        "gas_q3": f"{q3:.3f}", "gas_max": max(gas), "gas_iqr": f"{q3 - q1:.3f}",
        "gas_mean": f"{statistics.mean(gas):.3f}",
        "gas_sample_stddev": f"{statistics.stdev(gas) if len(gas) > 1 else 0.0:.3f}",
        "latency_median_seconds": f"{statistics.median(latency):.9f}",
        "latency_p95_seconds": f"{percentile(latency_ns, 0.95) / 1_000_000_000:.9f}",
        "evidence_type": "local_besu_measurement", "status": "PASS",
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=50)
    parser.add_argument("--rpc", default="http://127.0.0.1:8545")
    parser.add_argument("--cast", default=os.environ.get("CAST_BIN", "cast"))
    parser.add_argument("--forge", default=os.environ.get("FORGE_BIN", "forge"))
    parser.add_argument(
        "--deployment", default=str(ROOT / "results/reviewer_revision/raw/besu_v2_final/deployment.json"),
        help="Existing deployment used only for KeyManager and actor addresses.",
    )
    args = parser.parse_args()

    deployer_key = os.environ.get("LEDGERGUARD_DEPLOYER_PRIVATE_KEY") or os.environ.get("VENDOR_PRIVATE_KEY", "")
    operator_key = os.environ.get("LEDGERGUARD_OPERATOR_PRIVATE_KEY", "")
    auditor_key = os.environ.get("LEDGERGUARD_AUDITOR_PRIVATE_KEY", "")
    if not all((deployer_key, operator_key, auditor_key)):
        raise RuntimeError("deployer, operator, and auditor private-key environment variables are required")

    base_deployment = json.loads(Path(args.deployment).read_text(encoding="utf-8"))
    key_manager = base_deployment["contracts"]["KeyManager"]["deployedTo"]
    actors = base_deployment["actors"]
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    output_paths = [
        RAW_DIR / "comparison_deployments.json", RAW_DIR / "measured_transactions.jsonl",
        CSV_DIR / "accountability_measured.csv",
        CSV_DIR / "accountability_measured_transactions.csv",
        CSV_DIR / "accountability_path_totals.csv",
        CSV_DIR / "accountability_path_statistics.csv",
        CSV_DIR / "accountability_ablation.csv",
        VALIDATION_DIR / "accountability_status.json",
    ]
    if any(path.exists() for path in output_paths):
        raise RuntimeError("accountability output already exists; archive it before rerunning")

    deployments = {
        "naive_per_device": deploy_contract(
            args.forge, args.cast, args.rpc, deployer_key,
            "src/NaiveDeviceReporting.sol:NaiveDeviceReporting", [key_manager],
        ),
        "v1_integrity_root": deploy_contract(
            args.forge, args.cast, args.rpc, deployer_key,
            "src/DeviceAttestation.sol:DeviceAttestation", [key_manager],
        ),
        "v2_complete_witnessed": deploy_contract(
            args.forge, args.cast, args.rpc, deployer_key,
            "src/DeviceAttestationV2.sol:DeviceAttestationV2", [key_manager],
        ),
    }
    (RAW_DIR / "comparison_deployments.json").write_text(
        json.dumps(deployments, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )

    database_sizes: dict[str, dict[str, int]] = {"before_naive_per_device": validator_sizes()}
    naive_calls = [
        ("naive_submit_device_outcome", "submitDeviceOutcome(uint256,uint32,bytes32,uint8,bytes32)",
         ["1", "1", bytes32(2_000_000 + index), "1", bytes32(3_000_000 + index)])
        for index in range(args.samples)
    ]
    naive_receipts = submit_batch(
        args.cast, args.rpc, operator_key, actors["operator"],
        deployments["naive_per_device"]["deployed_to"], naive_calls,
    )
    database_sizes["after_naive_per_device"] = validator_sizes()

    v1_calls = [
        ("v1_submit_outcome_root", "submitOutcomeRoot(uint256,uint32,bytes32,uint32,uint32,uint32)",
         [str(10_000 + index), "1", bytes32(4_000_000 + index), "98", "1", "1"])
        for index in range(args.samples)
    ]
    v1_receipts = submit_batch(
        args.cast, args.rpc, operator_key, actors["operator"],
        deployments["v1_integrity_root"]["deployed_to"], v1_calls,
    )
    database_sizes["after_v1_integrity_root"] = validator_sizes()

    v2_address = deployments["v2_complete_witnessed"]["deployed_to"]
    register_calls: list[tuple[str, str, list[str]]] = []
    cohort_keys: list[str] = []
    for index in range(args.samples):
        rollout_id = bytes32(5_000_000 + index)
        register_calls.append((
            "v2_register_cohort", "registerCohort(uint256,bytes32,uint32,bytes32,bytes32,uint32,uint64)",
            ["1", rollout_id, "1", bytes32(6_000_000 + index), bytes32(7_000_000 + index),
             "100", "4102444800"],
        ))
        call_result = run([
            args.cast, "call", "--rpc-url", args.rpc, v2_address,
            "cohortKey(uint256,bytes32,uint32)(bytes32)", "1", rollout_id, "1",
        ])
        if call_result.returncode:
            raise RuntimeError(call_result.stderr)
        cohort_keys.append(call_result.stdout.strip().split()[0])

    register_receipts = submit_batch(
        args.cast, args.rpc, operator_key, actors["operator"], v2_address, register_calls,
    )
    propose_calls = [
        ("v2_propose_summary",
         "proposeSummary(bytes32,bytes32,bytes32,uint32,uint32,uint32,uint32,uint32,uint32)",
         [key, bytes32(8_000_000 + index), bytes32(9_000_000 + index),
          "100", "98", "1", "1", "0", "0"])
        for index, key in enumerate(cohort_keys)
    ]
    propose_receipts = submit_batch(
        args.cast, args.rpc, operator_key, actors["operator"], v2_address, propose_calls,
    )
    confirm_calls = [
        ("v2_confirm_summary",
         "confirmSummary(bytes32,bytes32,bytes32,uint32,uint32,uint32,uint32,uint32,uint32)",
         [key, bytes32(8_000_000 + index), bytes32(9_000_000 + index),
          "100", "98", "1", "1", "0", "0"])
        for index, key in enumerate(cohort_keys)
    ]
    confirm_receipts = submit_batch(
        args.cast, args.rpc, auditor_key, actors["auditor"], v2_address, confirm_calls,
    )
    database_sizes["after_v2_complete_witnessed"] = validator_sizes()

    receipt_groups = {
        "naive_per_device": [naive_receipts],
        "v1_integrity_root": [v1_receipts],
        "v2_complete_witnessed": [register_receipts, propose_receipts, confirm_receipts],
    }
    paths: list[dict[str, Any]] = []
    raw_receipts: list[dict[str, Any]] = []
    measured_transactions: list[dict[str, Any]] = []
    for mode in MODES:
        operation_groups = receipt_groups[mode]
        for index in range(args.samples):
            path_id = f"{mode}-{index + 1:03d}"
            path_receipts = [group[index] for group in operation_groups]
            paths.append({
                "path_id": path_id, "reporting_mode": mode,
                "operation_count": len(path_receipts),
                "gas_total": sum(receipt["gas_used"] for receipt in path_receipts),
                "event_count": sum(receipt["event_count"] for receipt in path_receipts),
                "latency_total_seconds": f"{sum(receipt['latency_seconds'] for receipt in path_receipts):.9f}",
                "status": "PASS", "evidence_type": "local_besu_measurement",
                "raw_evidence_path": "results/reviewer_revision/raw/accountability/measured_transactions.jsonl",
            })
            for sequence, receipt in enumerate(path_receipts, start=1):
                annotated = receipt | {
                    "path_id": path_id, "reporting_mode": mode,
                    "path_operation_sequence": sequence,
                }
                raw_receipts.append(annotated)
                measured_transactions.append({
                    "path_id": path_id, "reporting_mode": mode,
                    "path_operation_sequence": sequence, "operation": receipt["operation"],
                    "tx_hash": receipt["tx_hash"], "block_number": receipt["block_number"],
                    "transaction_index": receipt["transaction_index"], "gas_used": receipt["gas_used"],
                    "event_count": receipt["event_count"],
                    "latency_seconds": f"{receipt['latency_seconds']:.9f}",
                    "status": receipt["status"], "evidence_type": "local_besu_measurement",
                    "raw_evidence_path": "results/reviewer_revision/raw/accountability/measured_transactions.jsonl",
                })

    with (RAW_DIR / "measured_transactions.jsonl").open("w", encoding="utf-8") as stream:
        for receipt in raw_receipts:
            stream.write(json.dumps(receipt, sort_keys=True) + "\n")
    write_csv(CSV_DIR / "accountability_measured_transactions.csv", measured_transactions)
    write_csv(CSV_DIR / "accountability_path_totals.csv", paths)

    statistics_rows = [
        path_statistics(mode, [path for path in paths if path["reporting_mode"] == mode])
        for mode in MODES
    ]
    write_csv(CSV_DIR / "accountability_path_statistics.csv", statistics_rows)

    stages = (
        ("naive_per_device", "before_naive_per_device", "after_naive_per_device"),
        ("v1_integrity_root", "after_naive_per_device", "after_v1_integrity_root"),
        ("v2_complete_witnessed", "after_v1_integrity_root", "after_v2_complete_witnessed"),
    )
    summaries = []
    for mode, before_key, after_key in stages:
        mode_paths = [path for path in paths if path["reporting_mode"] == mode]
        mode_transactions = [row for row in measured_transactions if row["reporting_mode"] == mode]
        before = database_sizes[before_key]["total_bytes"]
        after = database_sizes[after_key]["total_bytes"]
        summaries.append({
            "reporting_mode": mode, "logical_paths": len(mode_paths),
            "executed_transactions": len(mode_transactions),
            "total_gas_used": sum(int(path["gas_total"]) for path in mode_paths),
            "median_gas_per_logical_path": f"{statistics.median(int(path['gas_total']) for path in mode_paths):.3f}",
            "emitted_events": sum(int(path["event_count"]) for path in mode_paths),
            "validator_db_bytes_before": before, "validator_db_bytes_after": after,
            "observed_db_delta_bytes": after - before,
            "db_measurement_scope": "four_validator_directories_including_block_and_database_overhead",
            "evidence_type": "local_besu_measurement", "status": "PASS",
        })
    write_csv(CSV_DIR / "accountability_measured.csv", summaries)

    median_gas = {
        row["reporting_mode"]: int(round(float(row["gas_median"]))) for row in statistics_rows
    }
    ablation = []
    for fleet in FLEETS:
        for batch in BATCHES:
            root_count = math.ceil(fleet / batch)
            formulas = {
                "naive_per_device": (fleet, fleet, 32 + fleet * 192,
                                     "32 + fleet*192", fleet * median_gas["naive_per_device"]),
                "v1_integrity_root": (root_count, root_count, 32 + root_count * 64,
                                      "32 + ceil(fleet/batch)*64", root_count * median_gas["v1_integrity_root"]),
                "v2_complete_witnessed": (root_count, root_count * 3, 32 + root_count * 384,
                                          "32 + ceil(fleet/batch)*384", root_count * median_gas["v2_complete_witnessed"]),
            }
            for mode in MODES:
                records, tx_count, storage_bytes, storage_formula, gas = formulas[mode]
                ablation.append({
                    "fleet_size": fleet, "batch_size": batch, "reporting_mode": mode,
                    "on_chain_equivalent_records": records, "formula_transaction_count": tx_count,
                    "formula_storage_slot_bytes": storage_bytes,
                    "formula_gas_from_path_median": gas,
                    "measured_median_gas_basis": median_gas[mode],
                    "storage_formula": storage_formula,
                    "evidence_type": "analytical_using_solidity_layout_and_local_path_gas_median",
                    "status": "PASS",
                    "raw_evidence_path": "results/reviewer_revision/raw/accountability/measured_transactions.jsonl",
                })
    write_csv(CSV_DIR / "accountability_ablation.csv", ablation)

    status = {
        "status": "PASS", "generated_at_utc": utc_now(),
        "samples_per_logical_path": args.samples, "logical_paths": len(paths),
        "measured_transactions": len(measured_transactions), "failed_transactions": 0,
        "contract_deployment_gas": {mode: deployments[mode]["gas_used"] for mode in MODES},
        "path_gas_statistics": {row["reporting_mode"]: row for row in statistics_rows},
        "v2_cost_uses_per_run_transaction_totals": True,
        "v1_integrity_only_comparator_included": True,
        "validator_database_delta_is_observed_run_delta_not_contract_state_size": True,
        "scaling_rows_are_analytical": True,
        "significance_tests_applied_to_formula_rows": False,
        "storage_formulas_include_shared_mapping_or_array_slot": True,
        "storage_layout_incremental_bytes": {
            "naive_per_device": 192, "v1_integrity_root": 64,
            "v2_complete_witnessed": 384,
        },
    }
    (VALIDATION_DIR / "accountability_status.json").write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(json.dumps(status, sort_keys=True))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

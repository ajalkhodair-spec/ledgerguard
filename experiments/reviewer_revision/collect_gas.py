#!/usr/bin/env python3
"""Summarize final-ABI deployment and operation gas with calldata and event metrics."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SUPPORT = {"DeviceIdentityRegistryV2", "DeviceReceiptVerifierV2"}
COMPARISON = {"DeviceAttestation", "NaiveDeviceReporting"}


def evidence_path(value: str) -> str:
    path = Path(value)
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def rpc(rpc_url: str, method: str, params: list[Any]) -> Any:
    request = urllib.request.Request(
        rpc_url,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read())
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload["result"]


def quantity(value: str) -> int:
    return int(value, 16)


def hex_bytes(value: str) -> int:
    normalized = value.removeprefix("0x")
    return len(normalized) // 2


def percentile(values: list[int], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summary_row(category: str, operation: str, samples: list[dict[str, int]], source: str) -> dict[str, Any]:
    gas = [sample["gas"] for sample in samples]
    calldata = [sample["calldata"] for sample in samples]
    events = [sample["events"] for sample in samples]
    gas_q1, gas_q3 = percentile(gas, 0.25), percentile(gas, 0.75)
    return {
        "category": category,
        "operation": operation,
        "n": len(samples),
        "minimum_gas": min(gas),
        "q1_gas": f"{gas_q1:.3f}",
        "median_gas": f"{statistics.median(gas):.3f}",
        "q3_gas": f"{gas_q3:.3f}",
        "maximum_gas": max(gas),
        "iqr_gas": f"{gas_q3 - gas_q1:.3f}",
        "mean_gas": f"{statistics.mean(gas):.3f}",
        "sample_standard_deviation_gas": f"{statistics.stdev(gas) if len(gas) > 1 else 0.0:.3f}",
        "minimum_calldata_bytes": min(calldata),
        "median_calldata_bytes": f"{statistics.median(calldata):.3f}",
        "maximum_calldata_bytes": max(calldata),
        "minimum_event_count": min(events),
        "median_event_count": f"{statistics.median(events):.3f}",
        "maximum_event_count": max(events),
        "gas_price_wei": 0,
        "evidence_type": "local_besu_final_abi_receipt",
        "source_evidence": source,
    }


def transaction_sample(rpc_url: str, tx_hash: str, raw: dict) -> dict[str, int]:
    receipt = rpc(rpc_url, "eth_getTransactionReceipt", [tx_hash])
    transaction = rpc(rpc_url, "eth_getTransactionByHash", [tx_hash])
    if not receipt or receipt.get("status") != "0x1" or not transaction:
        raise RuntimeError(f"successful transaction evidence missing for {tx_hash}")
    raw[tx_hash] = {"receipt": receipt, "transaction": transaction}
    return {
        "gas": quantity(receipt["gasUsed"]),
        "calldata": hex_bytes(transaction.get("input", "0x")),
        "events": len(receipt.get("logs", [])),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpc", default="http://127.0.0.1:8545")
    parser.add_argument(
        "--deployment",
        default=str(ROOT / "results/reviewer_revision/raw/besu_v2_final/deployment.json"),
    )
    parser.add_argument(
        "--comparison-deployments",
        default=str(ROOT / "results/reviewer_revision/raw/accountability/comparison_deployments.json"),
    )
    parser.add_argument(
        "--timing",
        default=str(ROOT / "results/reviewer_revision/csv/besu_v2_final_timing.csv"),
    )
    parser.add_argument(
        "--lifecycle",
        default=str(ROOT / "results/reviewer_revision/raw/besu_v2_final/governance_lifecycle_transactions.jsonl"),
    )
    parser.add_argument(
        "--csv",
        default=str(ROOT / "results/reviewer_revision/statistics/gas_summary_final.csv"),
    )
    parser.add_argument(
        "--raw",
        default=str(ROOT / "results/reviewer_revision/raw/besu_v2_final/deployment_receipts.json"),
    )
    parser.add_argument(
        "--status",
        default=str(ROOT / "results/reviewer_revision/validation/gas_final_status.json"),
    )
    args = parser.parse_args()

    deployment = json.loads(Path(args.deployment).read_text(encoding="utf-8"))
    deployment_items = {
        name: (item["transactionHash"], args.deployment)
        for name, item in deployment["contracts"].items()
    }
    comparison_path = Path(args.comparison_deployments)
    if comparison_path.exists():
        comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
        deployment_items["NaiveDeviceReporting"] = (
            comparison["naive_per_device"]["transaction_hash"], args.comparison_deployments
        )
        deployment_items["DeviceAttestation"] = (
            comparison["v1_integrity_root"]["transaction_hash"], args.comparison_deployments
        )

    raw_deployments: dict[str, Any] = {}
    raw_operations: dict[str, Any] = {}
    output_rows = []
    for name, (tx_hash, source) in sorted(deployment_items.items()):
        receipt = rpc(args.rpc, "eth_getTransactionReceipt", [tx_hash])
        transaction = rpc(args.rpc, "eth_getTransactionByHash", [tx_hash])
        if not receipt or receipt.get("status") != "0x1" or not transaction:
            raise RuntimeError(f"deployment receipt missing for {name}")
        raw_deployments[name] = {"receipt": receipt, "transaction": transaction, "source": evidence_path(source)}
        output_rows.append(summary_row(
            "deployment",
            name,
            [{
                "gas": quantity(receipt["gasUsed"]),
                "calldata": hex_bytes(transaction.get("input", "0x")),
                "events": len(receipt.get("logs", [])),
            }],
            evidence_path(source),
        ))
        output_rows[-1]["contract_group"] = (
            "supporting_verification" if name in SUPPORT else
            "experimental_comparison" if name in COMPARISON else "core_governance"
        )

    grouped: dict[str, list[dict[str, int]]] = defaultdict(list)
    sources: dict[str, str] = {}
    timing_path = Path(args.timing)
    timing_rows = list(csv.DictReader(timing_path.open(encoding="utf-8")))
    successful_by_run: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in timing_rows:
        if row["tx_status"] == "success":
            successful_by_run[row["repetition"]].append(row)
    complete_runs = {
        repetition
        for repetition, rows in successful_by_run.items()
        if len(rows) == 7 and len({row["operation"] for row in rows}) == 7
    }
    for row in timing_rows:
        if row["repetition"] in complete_runs and row["tx_status"] == "success":
            grouped[row["operation"]].append(transaction_sample(args.rpc, row["tx_hash"], raw_operations))
            raw_operations[row["tx_hash"]]["operation"] = row["operation"]
            sources[row["operation"]] = evidence_path(args.timing)

    lifecycle_path = Path(args.lifecycle)
    for line in lifecycle_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        row = json.loads(line)
        if row["status"] == "success":
            grouped[row["operation"]].append(transaction_sample(args.rpc, row["tx_hash"], raw_operations))
            raw_operations[row["tx_hash"]]["operation"] = row["operation"]
            sources[row["operation"]] = evidence_path(args.lifecycle)

    for operation in sorted(grouped):
        output_rows.append(summary_row("operation", operation, grouped[operation], sources[operation]))
        output_rows[-1]["contract_group"] = "governance_workflow"

    raw_path = Path(args.raw)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(
        json.dumps({"chain_id": 1337, "gas_price_wei": 0, "contracts": raw_deployments}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    operation_raw_path = raw_path.with_name("operation_gas_samples.json")
    operation_raw_path.write_text(json.dumps(raw_operations, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    csv_path = Path(args.csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)

    status = {
        "status": "PASS",
        "final_v2_abi": True,
        "deployment_contracts": len(deployment_items),
        "operation_types": len(grouped),
        "operation_receipts": sum(len(samples) for samples in grouped.values()),
        "operation_raw_evidence": evidence_path(str(operation_raw_path)),
        "complete_timing_paths": len(complete_runs),
        "excluded_timing_attempts": len(successful_by_run) - len(complete_runs),
        "full_dispersion_reported": True,
        "calldata_bytes_reported": True,
        "event_counts_reported": True,
        "gas_price_wei": 0,
        "currency_conversion": "not_performed",
        "sources": [
            evidence_path(args.deployment), evidence_path(args.comparison_deployments),
            evidence_path(args.timing), evidence_path(args.lifecycle),
        ],
    }
    status_path = Path(args.status)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, sort_keys=True))


if __name__ == "__main__":
    main()

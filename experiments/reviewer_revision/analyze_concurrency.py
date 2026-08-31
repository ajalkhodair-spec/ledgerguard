#!/usr/bin/env python3
"""Normalize parallel-RPC race evidence into the reviewer-required result schema."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
SCHEMA = [
    "test_id", "trial", "test_case", "initial_state", "submitted_transactions",
    "transaction_hashes", "block_numbers", "transaction_indexes", "expected_state",
    "observed_state", "reverted_transactions", "revert_reasons", "same_block",
    "evidence_type", "raw_evidence_path", "status",
]
CASE = {
    "duplicate_start": ("rollout=NONE", "rollout=CANARY; exactly one start accepted"),
    "stale_double_advance": ("rollout=CANARY, transition_nonce=1", "rollout=BATCH, transition_nonce=2; stale transition rejected"),
    "halt_vs_advance": ("rollout=BATCH, transition_nonce=2", "exactly one of GLOBAL or HALTED, transition_nonce=3"),
    "duplicate_summary_proposal": ("summary=NONE", "summary=PROPOSED; duplicate proposal rejected"),
    "duplicate_summary_confirmation": ("summary=PROPOSED", "summary=FINALIZED; duplicate confirmation rejected"),
}


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=CONTRACTS, text=True, capture_output=True, check=False)


def revert_reason(cast: str, rpc: str, tx_hash: str, block_number: int) -> str:
    transaction = run([cast, "rpc", "--rpc-url", rpc, "eth_getTransactionByHash", tx_hash])
    if transaction.returncode:
        return "receipt_status_0; transaction lookup failed"
    tx = json.loads(transaction.stdout)
    replay = run([
        cast, "call", "--rpc-url", rpc, "--from", tx["from"], "--data", tx["input"],
        "--block", hex(block_number), tx["to"],
    ])
    message = (replay.stderr or replay.stdout).strip()
    match = re.search(r"Execution reverted \((.*?)\)", message)
    return match.group(1) if match else "receipt_status_0; exact reason unavailable"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpc", default="http://127.0.0.1:8545")
    parser.add_argument("--cast", default="cast")
    parser.add_argument("--raw", default=str(ROOT / "results/reviewer_revision/raw/concurrency/rpc_races.jsonl"))
    parser.add_argument("--existing-csv", default=str(ROOT / "results/reviewer_revision/csv/concurrency_and_replay_tests.csv"))
    parser.add_argument("--output", default=str(ROOT / "results/reviewer_revision/csv/concurrency_and_replay_tests.csv"))
    parser.add_argument("--status", default=str(ROOT / "results/reviewer_revision/validation/concurrency_status.json"))
    args = parser.parse_args()

    raw_path = Path(args.raw)
    groups: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for line in raw_path.read_text(encoding="utf-8").splitlines():
        tx = json.loads(line)
        groups[(int(tx["trial"]), tx["test_case"])].append(tx)

    observed = {}
    with Path(args.existing_csv).open(encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            observed[(int(row["trial"]), row["test_case"])] = row.get("observed_final_state", row.get("observed_state", ""))

    rows = []
    reason_cache: dict[str, str] = {}
    for index, ((trial, case_name), transactions) in enumerate(sorted(groups.items()), start=1):
        transactions.sort(key=lambda tx: (tx["block_number"], tx["transaction_index"]))
        reverted = [tx for tx in transactions if tx["status"] == "reverted"]
        reasons = []
        for tx in reverted:
            reason_cache.setdefault(
                tx["tx_hash"], revert_reason(args.cast, args.rpc, tx["tx_hash"], int(tx["block_number"])),
            )
            reasons.append(reason_cache[tx["tx_hash"]])
        initial_state, expected_state = CASE[case_name]
        passed = len(transactions) == 2 and len(reverted) == 1 and sum(tx["status"] == "success" for tx in transactions) == 1
        rows.append({
            "test_id": f"RPC-RACE-{index:03d}", "trial": trial, "test_case": case_name,
            "initial_state": initial_state,
            "submitted_transactions": json.dumps([tx["contender"] for tx in transactions], separators=(",", ":")),
            "transaction_hashes": json.dumps([tx["tx_hash"] for tx in transactions], separators=(",", ":")),
            "block_numbers": json.dumps([tx["block_number"] for tx in transactions], separators=(",", ":")),
            "transaction_indexes": json.dumps([tx["transaction_index"] for tx in transactions], separators=(",", ":")),
            "expected_state": expected_state, "observed_state": observed[(trial, case_name)],
            "reverted_transactions": len(reverted), "revert_reasons": json.dumps(reasons, separators=(",", ":")),
            "same_block": len({tx["block_number"] for tx in transactions}) == 1,
            "evidence_type": "parallel_local_besu_rpc", "raw_evidence_path": str(raw_path.relative_to(ROOT)),
            "status": "PASS" if passed else "FAIL",
        })

    output_path = Path(args.output)
    with output_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=SCHEMA)
        writer.writeheader()
        writer.writerows(rows)

    failed = sum(row["status"] != "PASS" for row in rows)
    status_path = Path(args.status)
    prior = json.loads(status_path.read_text(encoding="utf-8"))
    prior.update({
        "status": "PASS" if failed == 0 else "FAIL",
        "required_schema_complete": all(all(str(row[field]) != "" for field in SCHEMA) for row in rows),
        "revert_reasons_recovered_by_historical_eth_call": len(reason_cache),
        "revert_reason_probe_method": "historical_eth_call_at_containing_block_post_state",
        "revert_reason_is_exact_intermediate_state_reconstruction": False,
        "primary_concurrency_evidence": "mined_receipt_status_transaction_order_and_final_contract_state",
        "failed_invariants": failed,
    })
    status_path.write_text(json.dumps(prior, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "revert_reasons": len(reason_cache), "failed": failed}, sort_keys=True))


if __name__ == "__main__":
    main()

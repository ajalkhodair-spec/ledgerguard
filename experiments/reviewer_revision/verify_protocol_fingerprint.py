#!/usr/bin/env python3
"""Retrospectively bind recorded timing transactions to compiled source and live bytecode."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from eth_utils import keccak

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results/reviewer_revision"
OPERATIONS = {
    "register_release": ("FirmwareRegistry", "registerRelease"),
    "security_approval": ("FirmwareRegistry", "approveRelease"),
    "regulator_approval": ("FirmwareRegistry", "approveRelease"),
    "start_rollout": ("RolloutCoordinatorV2", "startRollout"),
    "register_cohort": ("DeviceAttestationV2", "registerCohort"),
    "propose_outcome_summary": ("DeviceAttestationV2", "proposeSummary"),
    "confirm_outcome_summary": ("DeviceAttestationV2", "confirmSummary"),
}


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def rpc(url: str, method: str, params: list) -> object:
    request = urllib.request.Request(url, canonical({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}), {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    if "error" in result:
        raise RuntimeError(f"{method}: {result['error']}")
    return result["result"]


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpc", default="http://127.0.0.1:8545")
    parser.add_argument("--solc", default="solc")
    args = parser.parse_args()
    output_dir = RESULTS / "raw/protocol_fingerprint"
    output_dir.mkdir(parents=True, exist_ok=True)
    deployment = json.loads((RESULTS / "raw/besu_v2_final/deployment.json").read_text())
    sources = {p.relative_to(ROOT / "contracts").as_posix(): {"content": p.read_text()} for p in sorted((ROOT / "contracts/src").glob("*.sol"))}
    settings = {
        "optimizer": {"enabled": True, "runs": 200}, "viaIR": True,
        "evmVersion": "berlin", "metadata": {"bytecodeHash": "ipfs"},
        "outputSelection": {"*": {"": ["ast"], "*": ["abi", "storageLayout", "metadata", "evm.deployedBytecode", "evm.methodIdentifiers"]}},
    }
    compiler_input = {"language": "Solidity", "sources": sources, "settings": settings}
    compile_result = subprocess.run([args.solc, "--standard-json"], input=json.dumps(compiler_input), text=True, capture_output=True, check=True)
    compiled = json.loads(compile_result.stdout)
    errors = [item for item in compiled.get("errors", []) if item["severity"] == "error"]
    if errors:
        raise RuntimeError(errors)
    for name, data in (("compiler_input.json", compiler_input), ("compiler_output.json", compiled)):
        (output_dir / name).write_bytes(canonical(data) + b"\n")
    variables = {str(node["id"]): node["name"] for source in compiled["sources"].values() for node in walk(source["ast"]) if node.get("nodeType") == "VariableDeclaration"}
    contracts = deployment["contracts"]
    immutable_addresses = {"keyManager": contracts["KeyManager"]["deployedTo"], "registry": contracts["FirmwareRegistry"]["deployedTo"], "identityRegistry": contracts["DeviceIdentityRegistryV2"]["deployedTo"]}
    head = rpc(args.rpc, "eth_blockNumber", [])
    records = {}
    expected_code = {}
    for name, deployed in contracts.items():
        artifact = compiled["contracts"][f"src/{name}.sol"][name]
        runtime = artifact["evm"]["deployedBytecode"]
        code = bytearray.fromhex(runtime["object"])
        for variable_id, references in runtime.get("immutableReferences", {}).items():
            value = int(immutable_addresses[variables[variable_id]], 16)
            for reference in references:
                start, length = reference["start"], reference["length"]
                code[start:start + length] = value.to_bytes(length, "big")
        actual = bytes.fromhex(rpc(args.rpc, "eth_getCode", [deployed["deployedTo"], head])[2:])
        if bytes(code) != actual:
            raise RuntimeError(f"{name}: deployed runtime does not match source, compiler settings, and constructor bindings")
        expected_code[name] = actual
        (output_dir / f"{name}_runtime.hex").write_text(actual.hex() + "\n")
        records[name] = {
            "address": deployed["deployedTo"], "deployment_transaction": deployed["transactionHash"],
            "runtime_sha256": sha(actual), "runtime_keccak256": "0x" + keccak(actual).hex(),
            "abi_sha256": sha(canonical(artifact["abi"])),
            "storage_layout_sha256": sha(canonical(artifact["storageLayout"])),
            "bytecode_match": "exact_including_metadata_and_bound_immutables",
        }
    timing = list(csv.DictReader((RESULTS / "csv/besu_v2_final_timing_complete.csv").open()))
    linked = []
    for row in timing:
        name, method = OPERATIONS[row["operation"]]
        transaction = rpc(args.rpc, "eth_getTransactionByHash", [row["tx_hash"]])
        receipt = rpc(args.rpc, "eth_getTransactionReceipt", [row["tx_hash"]])
        artifact = compiled["contracts"][f"src/{name}.sol"][name]
        selectors = {selector for signature, selector in artifact["evm"]["methodIdentifiers"].items() if signature.startswith(method + "(")}
        block = hex(int(row["block_number"]))
        historical = bytes.fromhex(rpc(args.rpc, "eth_getCode", [records[name]["address"], block])[2:])
        if not (
            transaction and receipt and receipt["status"] == "0x1"
            and transaction["to"].lower() == records[name]["address"].lower()
            and transaction["input"][2:10] in selectors
            and receipt["blockNumber"] == block
            and int(receipt["gasUsed"], 16) == int(row["gas_used"])
            and historical == expected_code[name]
        ):
            raise RuntimeError(f"timing/source binding failed: {row['tx_hash']}")
        linked.append({"run_id": row["run_id"], "operation": row["operation"], "contract": name,
                       "runtime_sha256": records[name]["runtime_sha256"], "abi_sha256": records[name]["abi_sha256"],
                       "transaction": transaction, "receipt": receipt})
    if len(linked) != 350:
        raise RuntimeError("expected 350 linked timing transactions")
    (output_dir / "timing_transaction_bindings.json").write_bytes(canonical(linked) + b"\n")
    commit = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=ROOT, text=True, capture_output=True)
    source_hashes = {name: sha(data["content"].encode()) for name, data in sources.items()}
    protocol = {
        "status": "PASS", "protocol_version": "V2", "receipt_schema_version": "2",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "verification_type": "retrospective_exact_bytecode_and_historical_transaction_verification",
        "git_commit": commit.stdout.strip() if commit.returncode == 0 else None,
        "git_commit_at_execution": None, "historical_commit_not_recorded": True,
        "git_worktree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip()),
        "git_freeze_status": "PENDING" if commit.returncode else "requires_clean_source_match",
        "source_sha256": source_hashes, "source_set_sha256": sha(canonical(source_hashes)),
        "compiler": subprocess.check_output([args.solc, "--version"], text=True).strip(),
        "compiler_settings": settings, "chain_id": int(rpc(args.rpc, "eth_chainId", []), 16),
        "verification_block": int(head, 16), "contracts": records,
        "linked_timing_rows": len(linked), "timing_csv_sha256": sha((RESULTS / "csv/besu_v2_final_timing_complete.csv").read_bytes()),
        "receipt_pipeline_sha256": sha((ROOT / "experiments/reviewer_revision/receipt_pipeline.py").read_bytes()),
        "limitations": "No historical Git commit is invented. Timing fixtures are not end-to-end fleet receipts.",
    }
    (RESULTS / "validation/protocol_fingerprint.json").write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "contracts_exactly_matched": len(records), "timing_rows_bound": len(linked), "git_freeze_status": protocol["git_freeze_status"]}))


if __name__ == "__main__":
    main()

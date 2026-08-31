#!/usr/bin/env python3
"""Offline consistency gate for the narrow final reviewer-evidence cleanup."""

import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from experiments.reviewer_revision.collect_gas import summary_row
from experiments.reviewer_revision.summarize_final_distributions import describe, outcome_shares
from experiments.reviewer_revision.verify_protocol_fingerprint import OPERATIONS, canonical
from experiments.reviewer_revision.revision_manifest import git_state

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results/reviewer_revision"


def rows(path):
    with (RESULTS / path).open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def read(path):
    return json.loads((RESULTS / path).read_text(encoding="utf-8"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify():
    fingerprint = read("validation/protocol_fingerprint.json")
    require(fingerprint["status"] == "PASS", "protocol fingerprint did not pass")
    source_hashes = {path.relative_to(ROOT / "contracts").as_posix(): sha(path.read_bytes())
                     for path in sorted((ROOT / "contracts/src").glob("*.sol"))}
    require(source_hashes == fingerprint["source_sha256"], "contract sources changed after bytecode verification")
    require(sha(canonical(source_hashes)) == fingerprint["source_set_sha256"], "source-set digest mismatch")
    require(sha((ROOT / "experiments/reviewer_revision/receipt_pipeline.py").read_bytes()) ==
            fingerprint["receipt_pipeline_sha256"], "receipt pipeline changed after verification")
    require(sha((RESULTS / "csv/besu_v2_final_timing_complete.csv").read_bytes()) ==
            fingerprint["timing_csv_sha256"], "verified timing CSV changed")
    compiled = read("raw/protocol_fingerprint/compiler_output.json")
    compiler_input = read("raw/protocol_fingerprint/compiler_input.json")
    require({name: sha(value["content"].encode()) for name, value in compiler_input["sources"].items()} ==
            source_hashes, "archived compiler input is stale")
    for name, record in fingerprint["contracts"].items():
        artifact = compiled["contracts"][f"src/{name}.sol"][name]
        runtime = bytes.fromhex((RESULTS / f"raw/protocol_fingerprint/{name}_runtime.hex").read_text().strip())
        require(sha(runtime) == record["runtime_sha256"], f"runtime digest mismatch: {name}")
        require(sha(canonical(artifact["abi"])) == record["abi_sha256"], f"ABI digest mismatch: {name}")
        require(sha(canonical(artifact["storageLayout"])) == record["storage_layout_sha256"], f"layout digest mismatch: {name}")
    bindings = read("raw/protocol_fingerprint/timing_transaction_bindings.json")
    timing = {row["tx_hash"]: row for row in rows("csv/besu_v2_final_timing_complete.csv")}
    require(len(bindings) == len(timing) == 350, "expected 350 timing transaction bindings")
    require({item["transaction"]["hash"] for item in bindings} == set(timing), "timing identities differ")
    for item in bindings:
        tx, receipt = item["transaction"], item["receipt"]
        row = timing[tx["hash"]]
        name, method = OPERATIONS[row["operation"]]
        record = fingerprint["contracts"][name]
        selectors = compiled["contracts"][f"src/{name}.sol"][name]["evm"]["methodIdentifiers"]
        require(item["contract"] == name and tx["to"].lower() == record["address"].lower(), "wrong timing target")
        require(tx["input"][2:10] in {v for k, v in selectors.items() if k.startswith(method + "(")}, "wrong method selector")
        require(receipt["transactionHash"] == tx["hash"] and receipt["status"] == "0x1", "receipt identity/status mismatch")
        require(int(receipt["gasUsed"], 16) == int(row["gas_used"]) and
                int(receipt["blockNumber"], 16) == int(row["block_number"]), "timing gas/block mismatch")

    gas = rows("statistics/gas_summary_final.csv")
    deployments = read("raw/besu_v2_final/deployment_receipts.json")["contracts"]
    operations = read("raw/besu_v2_final/operation_gas_samples.json")
    require(len(deployments) == 8 and len(operations) == 550 and len(gas) == 19, "gas evidence cardinality mismatch")
    grouped = defaultdict(list)
    for key, item in operations.items():
        require(item["receipt"]["transactionHash"] == key == item["transaction"]["hash"], "gas transaction identity mismatch")
        grouped[item["operation"]].append(item)
    require(len(grouped) == 11 and all(len(values) == 50 for values in grouped.values()), "expected 11 operations x 50")
    deployment_rows = [row for row in gas if row["category"] == "deployment"]
    require(Counter(row["contract_group"] for row in deployment_rows) ==
            {"core_governance": 4, "supporting_verification": 2, "experimental_comparison": 2}, "gas contract classification mismatch")
    for row in gas:
        items = [deployments[row["operation"]]] if row["category"] == "deployment" else grouped[row["operation"]]
        samples = []
        for item in items:
            receipt, tx = item["receipt"], item["transaction"]
            require(receipt["status"] == "0x1", "failed receipt in gas statistics")
            samples.append({"gas": int(receipt["gasUsed"], 16), "calldata": len(tx["input"].removeprefix("0x")) // 2,
                            "events": len(receipt["logs"])})
        expected = summary_row(row["category"], row["operation"], samples, row["source_evidence"])
        require(all(row[key] == str(value) for key, value in expected.items()), f"gas summary mismatch: {row['operation']}")

    paths = rows("csv/accountability_path_totals.csv")
    path_groups = defaultdict(list)
    for row in paths:
        path_groups[row["reporting_mode"]].append(int(row["gas_total"]))
    require(len(paths) == 150 and len(path_groups) == 3 and all(len(v) == 50 for v in path_groups.values()), "accountability paths incomplete")
    medians = {mode: statistics.median(values) for mode, values in path_groups.items()}
    ablation = rows("csv/accountability_ablation.csv")
    require(len(ablation) == 36, "accountability ablation incomplete")
    for row in ablation:
        n, b, mode = int(row["fleet_size"]), int(row["batch_size"]), row["reporting_mode"]
        batches = math.ceil(n / b)
        records, txs, storage = {"naive_per_device": (n, n, 32 + 192*n),
                                "v1_integrity_root": (batches, batches, 32 + 64*batches),
                                "v2_complete_witnessed": (batches, 3*batches, 32 + 384*batches)}[mode]
        require(int(row["formula_transaction_count"]) == txs and int(row["on_chain_equivalent_records"]) == records,
                "accountability transaction/record formula mismatch")
        require(int(row["formula_storage_slot_bytes"]) == storage, "accountability storage formula mismatch")
        require(float(row["measured_median_gas_basis"]) == medians[mode] and
                float(row["formula_gas_from_path_median"]) == records * medians[mode], "gas must use median of complete path totals")

    fleet = rows("csv/fleet_multiseed_runs.csv")
    outcome_groups = defaultdict(list)
    for row in fleet:
        for outcome, value in outcome_shares(row).items():
            outcome_groups[(int(row["fleet_size"]), float(row["configured_failure_rate"]), outcome)].append(value)
    outcome_summary = rows("statistics/fleet_outcome_categories.csv")
    require(len(fleet) == 180 and len(outcome_summary) == 45, "fleet outcome evidence incomplete")
    for row in outcome_summary:
        values = outcome_groups[(int(row["fleet_size"]), float(row["configured_failure_rate"]), row["outcome"])]
        require(all(math.isclose(float(row[k]), v, abs_tol=1e-10) for k, v in describe(values).items()), "outcome distribution mismatch")
    network = [json.loads(line) for line in (RESULTS / "raw/network/application_shaped_fetches.jsonl").read_text().splitlines() if line]
    network_groups = defaultdict(list)
    for row in network:
        network_groups[row["profile"]].append(float(row["retrieval_time_seconds"]))
    network_summary = rows("statistics/network_full_distribution.csv")
    require(len(network) == 60 and len(network_summary) == 3 and all(len(v) == 20 for v in network_groups.values()), "network observations incomplete")
    for row in network_summary:
        require(all(math.isclose(float(row[k]), v, abs_tol=1e-10) for k, v in describe(network_groups[row["profile"]]).items()), "network distribution mismatch or observation removed")
    for name in ("foundry_final_status", "python_final_status", "coverage_review_status", "distribution_status", "validation_report", "revision_closure_status"):
        require(read(f"validation/{name}.json")["status"] == "PASS", f"{name} did not pass")
    slither = read("validation/slither_status.json")
    triage = rows("validation/slither_triage.csv")
    require(len(triage) == slither["detector_results"] == slither["triaged_findings"] == 15, "Slither triage incomplete")
    require(sha((RESULTS / slither["raw_json"].removeprefix("results/reviewer_revision/")).read_bytes()) == slither["raw_report_sha256"], "Slither source report changed")
    return {"status": "PASS", "technical_checks": "PASS", "source_and_abi_traceability": "retrospective_exact_bytecode_match",
            "git_freeze_status": git_state()["status"], "revision_commit": git_state()["revision_commit"], "historical_git_commit_recorded": False,
            "timing_rows_bound": len(bindings), "deployment_contracts": len(deployments), "operation_gas_receipts": len(operations),
            "accountability_formula_rows": len(ablation), "path_gas_medians": medians,
            "n500_b50_transaction_counts": {"naive": 500, "v1": 10, "v2": 30},
            "n500_b50_transaction_reduction_percent": {"v1": 98, "v2": 94},
            "network_maximum_seconds_retained": max(max(v) for v in network_groups.values()),
            "coverage": read("validation/foundry_final_status.json")["coverage"],
            "python_test_count": read("validation/python_final_status.json")["test_count"],
            "remaining_freeze_action": None if git_state()["status"] == "FROZEN" else "Commit the public revision and package from a clean worktree; no historical commit can be backfilled."}


def main():
    try:
        status = verify()
    except (ValueError, KeyError, OSError) as error:
        status = {"status": "FAIL", "error": str(error)}
    (RESULTS / "validation/evidence_freeze_status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
    print(json.dumps(status, sort_keys=True))
    if status["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

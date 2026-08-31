#!/usr/bin/env python3
"""Validate the complete reviewer-revision evidence set and evidence boundaries."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from eth_account import Account

from experiments.reviewer_revision.receipt_pipeline import CohortContext, aggregate_receipts, device_id_hash


ROOT = Path(__file__).resolve().parents[2]
CHAIN_ID = 1337
VERIFIER = "0x1111111111111111111111111111111111111111"


def csv_rows(path: str) -> list[dict]:
    return list(csv.DictReader((ROOT / path).open(encoding="utf-8")))


def main() -> int:
    errors: list[str] = []
    checks: dict[str, dict] = {}

    besu = csv_rows("results/reviewer_revision/csv/besu_v2_final_timing_complete.csv")
    hashes: set[str] = set()
    for index, row in enumerate(besu, start=2):
        if int(row["receipt_observed_at_ns"]) < int(row["submitted_at_ns"]):
            errors.append(f"Besu row {index}: receipt precedes submission")
        if float(row["latency_seconds"]) < 0:
            errors.append(f"Besu row {index}: negative latency")
        if row["tx_status"] == "success":
            if not row["tx_hash"] or row["tx_hash"] in hashes:
                errors.append(f"Besu row {index}: missing or duplicate transaction hash")
            hashes.add(row["tx_hash"])
            if not row["block_number"]:
                errors.append(f"Besu row {index}: successful transaction missing block number")
            if int(row["gas_used"] or 0) <= 0:
                errors.append(f"Besu row {index}: successful state change has zero gas")
    checks["besu_timing"] = {"rows": len(besu), "unique_transaction_hashes": len(hashes)}
    if len(besu) != 350 or len(hashes) != 350:
        errors.append("final-ABI Besu timing must contain 350 unique successful transaction rows")

    baseline = csv_rows("results/reviewer_revision/csv/http_sqlite_v2_timing.csv")
    for index, row in enumerate(baseline, start=2):
        if int(row["end_ns"]) < int(row["start_ns"]):
            errors.append(f"HTTP/SQLite row {index}: end precedes start")
        if float(row["latency_ms"]) < 0:
            errors.append(f"HTTP/SQLite row {index}: negative latency")
    checks["http_sqlite_timing"] = {"rows": len(baseline)}

    fleet = csv_rows("results/reviewer_revision/csv/fleet_multiseed_runs.csv")
    max_fleet = max(int(row["fleet_size"]) for row in fleet)
    keys = [f"0x{index + 1:064x}" for index in range(max_fleet)]
    devices = [device_id_hash(f"fleet-device-{index:05d}") for index in range(max_fleet)]
    identities = {
        device: Account.from_key(key).address.lower()
        for device, key in zip(devices, keys, strict=True)
    }
    verified_receipts = 0
    for row in fleet:
        expected = int(row["expected_count"])
        received = int(row["received_valid_count"])
        counts = sum(int(row[name]) for name in ("success_count", "rollback_count", "fail_count", "rejected_count"))
        missing = int(row["missing_count"])
        if counts != received or received + missing != expected:
            errors.append(f"{row['run_id']}: outcome counts do not reconcile")
        receipts_path = ROOT / row["raw_evidence_path"] / "receipts.jsonl"
        receipts = [json.loads(line) for line in receipts_path.read_text(encoding="utf-8").splitlines() if line]
        terminal_devices = [receipt["deviceIdHash"].lower() for receipt in receipts]
        if len(terminal_devices) != len(set(terminal_devices)):
            errors.append(f"{row['run_id']}: duplicate terminal device")
        first = receipts[0]
        context = CohortContext(
            release_id=int(first["releaseId"]), rollout_id=first["rolloutId"], epoch=int(first["epoch"]),
            cohort_id=first["cohortId"], deadline=int(first["deadline"]),
            target_version=int(first["targetVersion"]), expected_device_ids=tuple(devices[:expected]),
        )
        rebuilt = aggregate_receipts(
            context=context, signed_receipts=receipts,
            active_device_signers={device: identities[device] for device in devices[:expected]},
            chain_id=CHAIN_ID, verifying_contract=VERIFIER,
        )
        comparisons = {
            "receiptRoot": row["receipt_root"],
            "terminalOutcomeRoot": row["terminal_outcome_root"],
            "cohortCommitment": row["cohort_commitment"],
            "expectedCount": expected, "receivedValidCount": received,
            "successCount": int(row["success_count"]), "rollbackCount": int(row["rollback_count"]),
            "failCount": int(row["fail_count"]), "rejectedCount": int(row["rejected_count"]),
            "missingCount": missing,
        }
        for field, recorded in comparisons.items():
            if rebuilt[field] != recorded:
                errors.append(f"{row['run_id']}: rebuilt {field} does not match")
        verified_receipts += len(receipts)
    checks["fleet_and_merkle"] = {
        "runs": len(fleet), "verified_signed_receipts": verified_receipts,
        "all_feasible_roots_rebuilt": True,
    }
    fleet_status = json.loads(
        (ROOT / "results/reviewer_revision/validation/fleet_statistics_status.json").read_text(encoding="utf-8")
    )
    if len(fleet) != 180 or verified_receipts != 96_000 or fleet_status.get("seeds_per_configuration") != 20:
        errors.append("fleet evidence must contain 180 runs, 20 seeds per configuration, and 96,000 receipts")

    completeness = csv_rows("results/reviewer_revision/csv/aggregation_completeness_tests.csv")
    failed_completeness = [row["test_id"] for row in completeness if row["status"] != "passed"]
    if failed_completeness:
        errors.append(f"completeness cases failed: {failed_completeness}")
    required_merkle = next((row for row in completeness if row["test_id"] == "merkle_proof_validation"), None)
    if not required_merkle:
        errors.append("Merkle proof negative validation is missing")
    checks["completeness"] = {"cases": len(completeness), "failed": len(failed_completeness)}

    witness = csv_rows("results/reviewer_revision/csv/independent_witness_tests.csv")
    witness_status = json.loads(
        (ROOT / "results/reviewer_revision/validation/independent_witness_status.json").read_text(encoding="utf-8")
    )
    if len(witness) != 6 or any(row["status"] != "PASS" for row in witness):
        errors.append("independent aggregator/witness evidence is incomplete or failed")
    if (
        witness_status.get("status") != "PASS"
        or not witness_status.get("separate_process_reconstruction")
        or not witness_status.get("separate_receipt_journals")
        or not witness_status.get("software_device_dual_delivery")
        or witness_status.get("witness_input_obtained_from_aggregator") is not False
        or witness_status.get("common_omission_or_collusion_eliminated") is not False
    ):
        errors.append("independent witness execution or residual trust boundary is invalid")
    checks["independent_witness"] = {"cases": len(witness), **witness_status}

    gas = csv_rows("results/reviewer_revision/statistics/gas_summary_final.csv")
    deployments = [row for row in gas if row["category"] == "deployment"]
    operations = [row for row in gas if row["category"] == "operation"]
    if len(deployments) != 8 or len(operations) != 11 or any(float(row["median_gas"]) <= 0 for row in gas):
        errors.append("deployment or operation gas evidence is incomplete")
    if any(int(row["n"]) != 1 for row in deployments) or any(int(row["n"]) != 50 for row in operations):
        errors.append("final gas evidence must use one deployment and 50 receipts per operation")
    checks["gas"] = {"deployment_contracts": len(deployments), "operation_types": len(operations)}

    size_status = json.loads(
        (ROOT / "results/reviewer_revision/validation/receipt_size_status.json").read_text(encoding="utf-8")
    )
    if (
        size_status.get("status") != "PASS" or not size_status.get("signature_included")
        or not size_status.get("unsigned_payload_reported")
        or not size_status.get("aggregate_terminal_set_reported")
    ):
        errors.append("receipt-size definition failed or excludes signatures")
    checks["receipt_size"] = size_status

    block_period = csv_rows("results/reviewer_revision/csv/block_period_sensitivity.csv")
    valid_block_period = [row for row in block_period if row["status"] == "success"]
    if len(block_period) != 90 or len(valid_block_period) != 90:
        errors.append("block-period evidence does not contain 90 successful transactions")
    for index, row in enumerate(block_period, start=2):
        if float(row["latency_seconds"]) < 0 or not row["tx_hash"] or not row["block_number"]:
            errors.append(f"block-period row {index}: invalid timing or transaction identity")
    block_status = json.loads(
        (ROOT / "results/reviewer_revision/validation/block_period_status.json").read_text(encoding="utf-8")
    )
    if block_status.get("status") != "PASS" or block_status.get("slow_valid_observations_removed") != 0:
        errors.append("block-period analysis failed or removed a valid slow observation")
    checks["block_period"] = {"rows": len(block_period), **block_status}

    concurrency = csv_rows("results/reviewer_revision/csv/concurrency_and_replay_tests.csv")
    required_concurrency_fields = {
        "test_id", "initial_state", "submitted_transactions", "transaction_hashes", "block_numbers",
        "transaction_indexes", "expected_state", "observed_state", "reverted_transactions",
        "revert_reasons", "status",
    }
    if len(concurrency) != 25 or any(row["status"] != "PASS" for row in concurrency):
        errors.append("parallel-RPC concurrency evidence is incomplete or failed")
    if concurrency and not required_concurrency_fields.issubset(concurrency[0]):
        errors.append("concurrency CSV is missing reviewer-required columns")
    for row in concurrency:
        if int(row["reverted_transactions"]) != 1 or not json.loads(row["revert_reasons"]):
            errors.append(f"{row['test_id']}: expected one documented mined revert")
    concurrency_status = json.loads(
        (ROOT / "results/reviewer_revision/validation/concurrency_status.json").read_text(encoding="utf-8")
    )
    if (
        concurrency_status.get("status") != "PASS"
        or not concurrency_status.get("required_schema_complete")
        or concurrency_status.get("revert_reason_is_exact_intermediate_state_reconstruction") is not False
    ):
        errors.append("concurrency status failed required schema validation")
    checks["concurrency"] = {"cases": len(concurrency), **concurrency_status}

    accountability_tx = csv_rows("results/reviewer_revision/csv/accountability_measured_transactions.csv")
    accountability_hashes = {row["tx_hash"] for row in accountability_tx}
    if len(accountability_tx) != 250 or len(accountability_hashes) != 250:
        errors.append("accountability transaction evidence is missing or has duplicate hashes")
    if any(row["status"] != "success" or int(row["gas_used"]) <= 0 or not row["block_number"] for row in accountability_tx):
        errors.append("accountability transaction evidence contains failed or incomplete rows")
    accountability_measured = csv_rows("results/reviewer_revision/csv/accountability_measured.csv")
    accountability_modes = {"naive_per_device", "v1_integrity_root", "v2_complete_witnessed"}
    if {row["reporting_mode"] for row in accountability_measured} != accountability_modes:
        errors.append("per-device, V1 integrity-only, and V2 witnessed accountability paths are required")
    if any(int(row["observed_db_delta_bytes"]) < 0 for row in accountability_measured):
        errors.append("accountability validator-directory delta is negative")
    accountability_ablation = csv_rows("results/reviewer_revision/csv/accountability_ablation.csv")
    if len(accountability_ablation) != 36:
        errors.append("three-mode accountability fleet/batch sensitivity must contain 36 rows")
    if any("analytical" not in row["evidence_type"] for row in accountability_ablation):
        errors.append("accountability formula rows are not labeled analytical")
    accountability_status = json.loads(
        (ROOT / "results/reviewer_revision/validation/accountability_status.json").read_text(encoding="utf-8")
    )
    if (
        accountability_status.get("status") != "PASS"
        or not accountability_status.get("scaling_rows_are_analytical")
        or not accountability_status.get("v2_cost_uses_per_run_transaction_totals")
        or not accountability_status.get("v1_integrity_only_comparator_included")
    ):
        errors.append("accountability validation failed or conflated analytical scaling with measurement")
    accountability_paths = csv_rows("results/reviewer_revision/csv/accountability_path_totals.csv")
    accountability_statistics = csv_rows("results/reviewer_revision/csv/accountability_path_statistics.csv")
    if len(accountability_paths) != 150 or {row["reporting_mode"] for row in accountability_paths} != accountability_modes:
        errors.append("accountability logical-path totals are incomplete")
    if len(accountability_statistics) != 3 or {row["reporting_mode"] for row in accountability_statistics} != accountability_modes:
        errors.append("accountability path-dispersion statistics are incomplete")
    transactions_by_path: dict[str, list[dict]] = {}
    for row in accountability_tx:
        transactions_by_path.setdefault(row["path_id"], []).append(row)
    for path in accountability_paths:
        transactions = transactions_by_path.get(path["path_id"], [])
        if len(transactions) != int(path["operation_count"]):
            errors.append(f"{path['path_id']}: transaction count does not match path total")
            continue
        if sum(int(row["gas_used"]) for row in transactions) != int(path["gas_total"]):
            errors.append(f"{path['path_id']}: gas total is not the sum of its transactions")
    checks["accountability"] = {
        "measured_transactions": len(accountability_tx), "analytical_rows": len(accountability_ablation),
        **accountability_status,
    }

    network = csv_rows("results/reviewer_revision/csv/network_sensitivity.csv")
    network_raw = [
        json.loads(line) for line in
        (ROOT / "results/reviewer_revision/raw/network/application_shaped_fetches.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    if len(network) != 3 or len(network_raw) != 60 or any(row["status"] != "PASS" for row in network_raw):
        errors.append("application-shaped network evidence is incomplete or failed")
    if any(not row["integrity_valid"] or int(row["bytes_transferred"]) != int(row["artifact_size_bytes"]) for row in network_raw):
        errors.append("network fetch integrity or byte-count validation failed")
    network_status = json.loads(
        (ROOT / "results/reviewer_revision/validation/network_status.json").read_text(encoding="utf-8")
    )
    if (
        network_status.get("status") != "PASS"
        or network_status.get("wan_or_production_claim_supported") is not False
        or network_status.get("repetitions_per_profile") != 20
        or network_status.get("terminology") != "configured_application_delay_and_read_rate_limit"
    ):
        errors.append("network evidence status or claim boundary is invalid")
    checks["network"] = {"summary_rows": len(network), "raw_fetches": len(network_raw), **network_status}

    cache = csv_rows("results/reviewer_revision/csv/edge_cache_ablation.csv")
    cache_trials = csv_rows("results/reviewer_revision/csv/edge_cache_trials.csv")
    cache_raw = [
        json.loads(line) for line in
        (ROOT / "results/reviewer_revision/raw/cache/edge_cache_requests.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    if len(cache) != 2 or len(cache_trials) != 20 or len(cache_raw) != 20_000 or any(row["status"] != "PASS" for row in cache_raw):
        errors.append("edge-cache evidence is incomplete or failed")
    modes = {row["cache_mode"]: row for row in cache}
    if set(modes) != {"OFF", "ON"} or float(modes.get("ON", {}).get("median_origin_requests", 0)) != 1:
        errors.append("edge-cache ON/OFF semantics were not observed")
    cache_status = json.loads(
        (ROOT / "results/reviewer_revision/validation/cache_status.json").read_text(encoding="utf-8")
    )
    if (
        cache_status.get("status") != "PASS" or cache_status.get("physical_device_used") is not False
        or cache_status.get("independent_trials_per_mode") != 10
    ):
        errors.append("cache evidence status or physical-device boundary is invalid")
    checks["cache"] = {"summary_rows": len(cache), "raw_requests": len(cache_raw), **cache_status}

    compatibility = csv_rows("results/reviewer_revision/csv/protocol_compatibility_tests.csv")
    if len(compatibility) != 5 or any(row["status"] != "PASS" for row in compatibility):
        errors.append("V1/V2 protocol compatibility evidence is incomplete or failed")
    checks["protocol_compatibility"] = {"cases": len(compatibility)}

    validator_faults = csv_rows("results/reviewer_revision/csv/validator_faults.csv")
    if len(validator_faults) != 20 or any(row["status"] != "PASS" for row in validator_faults):
        errors.append("validator crash-fault evidence is incomplete or failed")
    for row in validator_faults:
        expected = row["expected_progress"].lower() == "true"
        observed = row["observed_progress"].lower() == "true"
        if expected != observed:
            errors.append(
                f"validator fault trial {row['trial']} case {row['fault_case']}: "
                "observed progress differs from expectation"
            )
    validator_fault_status = json.loads(
        (ROOT / "results/reviewer_revision/validation/validator_fault_status.json").read_text(encoding="utf-8")
    )
    if validator_fault_status.get("status") != "PASS" or validator_fault_status.get("byzantine_fault_injection"):
        errors.append("validator fault boundary is invalid or crash-fault trials failed")
    restoration = [row for row in validator_faults if row["fault_case"] == "quorum_restored_after_validator_restart"]
    if (
        len(restoration) != 5
        or any(row["restoration_tx_status"] != "success" for row in restoration)
        or validator_fault_status.get("successful_restoration_trials") != 5
    ):
        errors.append("quorum restoration lacks five resumed blocks and successful transaction receipts")
    checks["validator_crash_faults"] = {"rows": len(validator_faults), **validator_fault_status}

    claim_status = json.loads(
        (ROOT / "results/reviewer_revision/validation/claim_registry_status.json").read_text(encoding="utf-8")
    )
    if claim_status.get("status") != "PASS" or claim_status.get("counts", {}).get("blocked", 0) < 1:
        errors.append("claim registry failed or does not preserve unsupported-claim boundaries")
    checks["claim_registry"] = claim_status

    slither_status = json.loads(
        (ROOT / "results/reviewer_revision/validation/slither_status.json").read_text(encoding="utf-8")
    )
    if (
        slither_status.get("high_impact") != 0
        or slither_status.get("status") != "completed_with_reviewed_findings"
        or not slither_status.get("manual_triage_completed")
        or slither_status.get("detectors_suppressed") != []
        or slither_status.get("unmitigated_high_severity") != 0
    ):
        errors.append("Slither was not completed with reviewed findings or contains a high-impact result")
    checks["static_analysis"] = slither_status

    foundry_status = json.loads(
        (ROOT / "results/reviewer_revision/validation/foundry_final_status.json").read_text(encoding="utf-8")
    )
    if (
        foundry_status.get("status") != "PASS"
        or foundry_status.get("dedicated_fuzz_runs") != 10_000
        or foundry_status.get("invariant_calls") != 128_000
        or foundry_status.get("invariant_depth") != 500
        or not foundry_status.get("coverage", {}).get("line_percent")
        or not foundry_status.get("coverage", {}).get("branch_percent")
    ):
        errors.append("final Foundry fuzz/invariant campaign is incomplete or failed")
    checks["foundry_security"] = foundry_status

    report = {
        "status": "PASS" if not errors else "FAIL",
        "error_count": len(errors),
        "errors": errors,
        "checks": checks,
        "evidence_boundaries": {
            "besu": "local_besu_measurement",
            "fleet": "authenticated_software_emulation",
            "baseline": "local_persistent_backend_measurement",
            "network": "application_shaped_local_ipfs_fetch",
            "cache": "executed_local_ipfs_edge_cache",
            "accountability_scaling": "analytical_using_solidity_layout_and_local_path_gas_median",
            "current_terminal_root_accountability": "local_besu_measurement_current_abi",
            "control_plane_timing": "local_besu_measurement_final_v2_abi",
            "governance_gas_summary": "local_besu_measurement_final_v2_abi",
            "hil": "not_run",
            "physical_devices": "not_run",
            "mythril": "not_run",
        },
    }
    validation_dir = ROOT / "results/reviewer_revision/validation"
    json_path = validation_dir / "validation_report.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md = [
        "# Reviewer-Revision Validation Report",
        "",
        f"Overall status: **{report['status']}**",
        "",
        f"- Besu transaction rows: {len(besu)}",
        f"- HTTP/SQLite operation rows: {len(baseline)}",
        f"- Fleet runs: {len(fleet)}",
        f"- Signed receipts reverified: {verified_receipts}",
        f"- Completeness/Merkle cases: {len(completeness)}",
        f"- Independent witness cases: {len(witness)}",
        f"- Deployment gas records: {len(deployments)}",
        f"- Parallel-RPC race cases: {len(concurrency)}",
        f"- Accountability transactions: {len(accountability_tx)}",
        f"- Application-shaped IPFS fetches: {len(network_raw)}",
        f"- Edge-cache requests: {len(cache_raw)}",
        f"- Validator crash-fault observations: {len(validator_faults)}",
        "- HIL and physical devices: not run",
    ]
    if errors:
        md.extend(["", "## Errors", "", *[f"- {error}" for error in errors]])
    (validation_dir / "validation_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "errors": len(errors), "verified_receipts": verified_receipts}))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

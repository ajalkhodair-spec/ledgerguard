#!/usr/bin/env python3
"""Build narrow reviewer-closure evidence without rerunning or changing the protocol."""

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path

from experiments.reviewer_revision.receipt_pipeline import receipt_typed_data

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results/reviewer_revision"
VALIDATION = RESULTS / "validation"

# Explicit scope mapping, not a claim that the fuzz handler tests every guard.
BRANCHES = [
    ("Below-threshold approval", "testApprovalThresholdRequiredBeforeFinalApproval", "none", "Shared registry approval predicate; V2 eligibility is separately tested."),
    ("Duplicate approval", "testApprovalCountsRolesRatherThanSigners", "none", "Direct role-unique approval regression; no duplicate-approval fuzz property."),
    ("Revoked signer", "testRevokedSignerCannotApprove;testRevokedDeviceReceiptFails;testRolloutThresholdEligibilityAndAuthorization", "none", "Governance, device verifier, and V2 rollout authorization."),
    ("Unauthorized rollout", "testRolloutThresholdEligibilityAndAuthorization", "none", "Direct V2 wrong-role and inactive-role rejection."),
    ("Invalid phase transition", "testRolloutEmptyCountersNonceAndCompletedPhase;testTwoStaleAdvanceTransactionsYieldOneTransitionAndOneRevert", "none", "Direct nonce, terminal-state, and stale-phase checks."),
    ("Kill-switch block", "testKillSwitchBlocksSubsequentAdvance", "none", "Direct V2 progression rejection after activation."),
    ("Wrong epoch or root", "testNonsequentialEpochReverts;testEmptyTerminalRootReverts;testConflictingRootForSameEpochReverts", "none", "Direct negative cases; valid-root fuzz inputs do not cover invalid roots."),
    ("Counter mismatch", "testExpectedCountMismatchReverts;testSummaryCounterRootAndDeadlineGuards", "valid_reconciliation_only", "Fuzz/invariant exercise valid counter reconciliation, not mismatch rejection."),
    ("Witness disagreement", "testWitnessCounterMismatchReverts;testWitnessTerminalRootMismatchReverts;testAggregatorCannotConfirmAfterRoleReplacement", "none", "Direct disagreement and observer-account independence checks."),
    ("Receipt replay", "testCrossChainReplayFails;testCrossContractReplayFails;testCrossEpochReplayFails", "none", "Solidity tests bind domains; Python consumed-nonce test covers stateful journal replay."),
    ("Missing identity reconciliation", "testCompletenessUsesExpectedCohortDenominator;testMissingBeforeDeadlineReverts", "valid_reconciliation_only", "Solidity randomized tests cover counters, not individual identities; Python tests cover canonical terminal identities."),
    ("Deadline and expiry boundaries", "testExpiryBoundaryAndDeprecation;testSummaryCounterRootAndDeadlineGuards;testReceiptMandatoryFieldsAndDeadline", "none", "Direct equality, passed-deadline, and missing-before-deadline checks."),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def minimum_profitable_batch(naive_gas, aggregate_gas):
    if naive_gas <= 0 or aggregate_gas <= 0:
        raise ValueError("gas medians must be positive")
    return math.floor(aggregate_gas / naive_gas) + 1


def strip_private_fields(value):
    if isinstance(value, dict):
        return {key: strip_private_fields(item) for key, item in value.items()
                if key.lower().replace("_", "") not in {"privatekey", "secretkey", "mnemonic"}}
    if isinstance(value, list):
        return [strip_private_fields(item) for item in value]
    return value


def critical_branches():
    report_path = RESULTS / "raw/security/foundry_final.txt"
    report = report_path.read_text()
    python_report = (RESULTS / "raw/security/python_final.txt").read_text()
    sources = {}
    for path in sorted((ROOT / "contracts/test").glob("*.sol")):
        text = path.read_text()
        for match in re.finditer(r"function\s+((?:test|invariant)\w+)\s*\(", text):
            sources[match[1]] = f"{path.relative_to(ROOT)}:{text.count(chr(10), 0, match.start()) + 1}"
    rows = []
    for condition, names, randomized, scope in BRANCHES:
        tests = names.split(";")
        for name in tests:
            if name not in sources or not re.search(r"\[PASS\]\s+" + name + r"\(", report):
                raise ValueError(f"missing direct test evidence: {name}")
        rows.append({"critical_condition": condition, "direct_tests": names,
                     "source_locations": ";".join(sources[name] for name in tests),
                     "fuzz_scope": randomized, "invariant_scope": randomized,
                     "direct_test_result": "PASS", "scope_limit": scope,
                     "raw_evidence": str(report_path.relative_to(ROOT))})
    required_python = ["test_consumed_nonce_replay_fails_across_aggregations",
                       "test_each_terminal_identity_occurs_exactly_once_with_all_outcomes",
                       "test_missing_device_identity_changes_terminal_root"]
    for name in required_python:
        if not re.search(name + r" .* \.\.\. ok", python_report):
            raise ValueError(f"missing Python identity/replay evidence: {name}")
    for name in ("testFuzzCompletenessReconciliation", "invariantFinalizedCountersReconcileExpectedCohort"):
        if not re.search(r"\[PASS\]\s+" + name + r"\(", report):
            raise ValueError(f"missing randomized evidence: {name}")
    write_csv(VALIDATION / "critical_branch_matrix.csv", rows)
    lines = ["# Critical-Branch Test Matrix", "", "This is a manually scoped source/test mapping, not a replacement LCOV percentage.", "",
             "| Condition | Direct result | Fuzz/invariant scope | Direct tests |", "|---|---|---|---|"]
    lines += [f"| {r['critical_condition']} | PASS | {r['fuzz_scope']} | {r['direct_tests']} |" for r in rows]
    lines += ["", "`none` means no corresponding randomized property is claimed; direct tests still passed.",
              "`valid_reconciliation_only` covers randomized expected/missing counters in successful summaries, not negative guard arms or identity-level completeness.",
              "The handler returns immediately when lastKey is nonzero: at most one constructive cohort-finalization path occurs per invariant run. The 128,000 calls are handler invocations, not 128,000 distinct state-changing paths.",
              "Python identity and consumed-nonce cases are recorded in raw/security/python_final.txt. See CSV scope_limit for per-row distinctions."]
    (VALIDATION / "critical_branch_matrix.md").write_text("\n".join(lines) + "\n")
    return {"conditions": len(rows), "status": "PASS", "all_conditions_have_randomized_coverage": False,
            "maximum_constructive_paths_per_invariant_run": 1}


def break_even():
    with (RESULTS / "csv/accountability_path_statistics.csv").open() as stream:
        medians = {row["reporting_mode"]: float(row["gas_median"]) for row in csv.DictReader(stream)}
    naive = medians["naive_per_device"]
    rows = []
    for mode in ("v1_integrity_root", "v2_complete_witnessed"):
        for batch in (1, 2, 3, 4, 25, 50, 100, 200):
            gas = medians[mode]
            rows.append({"reporting_mode": mode, "batch_size": batch, "naive_batch_gas": naive * batch,
                         "aggregate_path_gas": gas, "difference_gas": naive * batch - gas,
                         "aggregate_strictly_lower_gas": gas < naive * batch,
                         "evidence_type": "analytical_from_executed_path_medians"})
    write_csv(RESULTS / "statistics/gas_break_even.csv", rows)
    result = {"status": "PASS", "path_gas_medians": medians,
              "v2_ratio": medians["v2_complete_witnessed"] / naive,
              "minimum_full_batch_devices": {mode: minimum_profitable_batch(naive, medians[mode]) for mode in medians if mode != "naive_per_device"},
              "scope": "Per full batch under fixed executed path medians; excludes deployment and off-chain work. Partial final batches require ceil(N/B)*aggregate_gas < N*naive_gas."}
    write_json(VALIDATION / "gas_break_even_status.json", result)
    return result


def outlier_review():
    source = RESULTS / "raw/network/application_shaped_fetches.jsonl"
    rows = [json.loads(line) for line in source.read_text().splitlines() if line]
    maximum = max(rows, key=lambda row: row["retrieval_time_seconds"])
    if not (maximum["status"] == "PASS" and maximum["integrity_valid"] and maximum["http_status"] == 200
            and maximum["bytes_transferred"] == maximum["artifact_size_bytes"]):
        raise ValueError("maximum observation did not pass integrity/transfer checks")
    result = {"status": "PASS", "source_sha256": sha(source.read_bytes()), "observation_retained": maximum,
              "causal_attribution": "undetermined_from_preserved_evidence",
              "diagnostic_limit": "Network JSONL omits start/end timestamps and per-read pacing timing. No synchronized host scheduler, Docker-resource, or IPFS-gateway diagnostic trace is preserved with this campaign.",
              "candidate_causes_not_established": ["host scheduling", "IPFS stall", "pacing behavior", "Docker contention"],
              "removed_observations": 0}
    write_json(VALIDATION / "network_outlier_review.json", result)
    (VALIDATION / "network_outlier_review.md").write_text(
        "# Slow IPFS Observation Review\n\n"
        f"{maximum['run_id']} completed in {maximum['retrieval_time_seconds']} seconds with HTTP 200, a valid SHA-256, and matching byte count. It remains in all distributions.\n\n"
        + result["diagnostic_limit"] + "\n\nThe strongly right-skewed distribution is reported using its full range and dispersion. No cause is retroactively assigned; present-day logs or reruns cannot establish the cause of this historical event.\n")
    return result


def configuration_snapshot(genesis):
    target = VALIDATION / "execution_configuration_snapshot.json"
    if genesis.exists():
        raw = genesis.read_bytes()
        public = strip_private_fields(json.loads(raw))
        snapshot = {"capture_type": "retrospective_local_configuration_snapshot", "source_path": "network/genesis.json",
                    "original_genesis_file_sha256": sha(raw), "sanitized_genesis": public,
                    "sanitized_genesis_sha256": sha(canonical(public)),
                    "private_fields_archived": False,
                    "limitation": "The original hash identifies the private local file; only sanitized configuration is archived. This is not a contemporaneous configuration record."}
        write_json(target, snapshot)
    elif not target.exists():
        raise ValueError("configuration snapshot absent; supply the original local genesis")
    receipt = {"outcome": "SUCCESS", "deviceIdHash": "0x" + "01" * 32, "releaseId": 1,
               "rolloutId": "0x" + "02" * 32, "epoch": 1, "cohortId": "0x" + "03" * 32,
               "deadline": 1, "targetVersion": 1, "observedAt": 1, "nonce": 1}
    typed = receipt_typed_data(receipt, 1337, "0x" + "01" * 20)
    schema = {"types": typed["types"], "primaryType": typed["primaryType"],
              "domain_name": typed["domain"]["name"], "domain_version": typed["domain"]["version"],
              "outcome_encoding": {"SUCCESS": 1, "ROLLBACK": 2, "FAIL": 3, "REJECTED": 4},
              "missing": "Derived terminal leaf, not a signed receipt outcome"}
    write_json(VALIDATION / "receipt_schema_v2.json", schema)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--genesis", type=Path, default=ROOT / "network/genesis.json")
    args = parser.parse_args()
    configuration_snapshot(args.genesis)
    branches, gas, network = critical_branches(), break_even(), outlier_review()
    status = {"status": "PASS", "critical_branches": branches,
              "v2_minimum_full_batch_devices": gas["minimum_full_batch_devices"]["v2_complete_witnessed"],
              "network_outlier_cause": network["causal_attribution"]}
    write_json(VALIDATION / "revision_closure_status.json", status)
    print(json.dumps(status))


if __name__ == "__main__":
    main()

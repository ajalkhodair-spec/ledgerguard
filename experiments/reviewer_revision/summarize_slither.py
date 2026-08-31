#!/usr/bin/env python3
"""Validate and summarize the final Slither report and manual triage metadata."""

from __future__ import annotations

import json
import csv
import hashlib
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

# Manual dispositions for the unchanged Solidity source, keyed by detector and function.
TIME_RISK = "Validator timestamps determine expiry/deadlines; a malicious quorum is outside the tested threat boundary."
STATE_RISK = "This detector does not identify a timestamp operand in the cited state guard; broader state-machine risks remain covered only by the tested cases."
TRIAGE = {
    ("incorrect-equality", "DeviceAttestationV2.successRateBps"): ("false positive", "FINALIZED is an enum state, not a balance or exact-time equality. Requiring this state is intentional.", "False state supplied by colluding observers is not ruled out by this guard.", "testSummaryReadAndConfirmationStates"),
    ("timestamp", "RolloutCoordinatorV2.startRollout"): ("accepted design condition", "The cited NONE comparison is a state guard. The same function intentionally relies on time-sensitive registry eligibility.", TIME_RISK, "testRolloutThresholdEligibilityAndAuthorization"),
    ("timestamp", "DeviceAttestationV2.registerCohort"): ("accepted design condition", "Deadline must be at or after the current block timestamp; the equality boundary is explicitly tested.", TIME_RISK, "testCohortRegistrationBoundaries"),
    ("timestamp", "DeviceAttestationV2.proposeSummary"): ("accepted design condition", "Missing outcomes are admitted only at/after the deadline. Summary-state equality is separately intentional.", TIME_RISK, "testSummaryCounterRootAndDeadlineGuards"),
    ("timestamp", "RolloutCoordinator.halt"): ("false positive", "The cited condition compares a phase with NONE; no timestamp operand occurs in that guard.", STATE_RISK, "testLegacyAdvanceCompletionAndHaltGuards"),
    ("timestamp", "RolloutCoordinator.startRollout"): ("accepted design condition", "The cited phase guard is not a timestamp equality; registry eligibility elsewhere in this function is time-sensitive.", TIME_RISK, "testReleaseCannotRollOutBeforeApproval"),
    ("timestamp", "FirmwareRegistry.registerRelease"): ("accepted design condition", "Zero means no expiry; nonzero expiry must be strictly later than block timestamp.", TIME_RISK, "testRegistrationRoleAndMetadataGuards"),
    ("timestamp", "DeviceAttestationV2.successRateBps"): ("false positive", "The cited expression checks cohort existence and a FINALIZED enum, not time.", STATE_RISK, "testSummaryReadAndConfirmationStates"),
    ("timestamp", "DeviceAttestationV2.summaryHash"): ("false positive", "NONE is an enum sentinel. The summary hash getter contains no time comparison.", STATE_RISK, "testSummaryReadAndConfirmationStates"),
    ("timestamp", "RolloutCoordinator._advance"): ("false positive", "The cited guards compare NONE, HALTED, and COMPLETED phase values, not timestamps.", STATE_RISK, "testLegacyAdvanceCompletionAndHaltGuards"),
    ("timestamp", "RolloutCoordinatorV2.advanceRollout"): ("accepted design condition", "Phase, nonce, and success checks are not time comparisons, but latestApproved eligibility depends on release expiry.", TIME_RISK, "testExpiryBoundaryAndDeprecation"),
    ("timestamp", "DeviceAttestationV2.confirmSummary"): ("false positive", "The cited checks compare proposed state and actor addresses. Finalization time is recorded, not compared in these guards.", "Separate addresses do not prove organizational independence; collusion remains possible.", "testAggregatorCannotConfirmAfterRoleReplacement"),
    ("timestamp", "RolloutCoordinatorV2.haltRollout"): ("false positive", "The cited guards compare phase and transition nonce. updatedAt records time after the checks.", STATE_RISK, "testHaltRoleStateAndNonceGuards"),
    ("timestamp", "FirmwareRegistry.latestApproved"): ("accepted design condition", "A release remains eligible at exact expiry and becomes ineligible after it; both boundaries are tested.", TIME_RISK, "testExpiryBoundaryAndDeprecation"),
    ("assembly", "DeviceReceiptVerifierV2.recoverSigner"): ("accepted design condition", "Assembly extracts r/s/v only after checking 65-byte length; v normalization, low-s rejection, and invalid recovery are tested.", "Signature validity authenticates a software key, not firmware state or hardware custody.", "testMalformedSignaturesAndNormalizedV"),
}


def main() -> None:
    raw = ROOT / "results/reviewer_revision/raw/security/slither_final.json"
    report = json.loads(raw.read_text(encoding="utf-8"))
    detectors = report.get("results", {}).get("detectors", [])
    impacts = Counter(item["impact"] for item in detectors)
    rows = []
    test_source = "\n".join(path.read_text() for path in (ROOT / "contracts/test").glob("*.sol"))
    for item in detectors:
        function = next(element for element in item["elements"] if element["type"] == "function")
        source = function["source_mapping"]["filename_relative"]
        name = f"{Path(source).stem}.{function['name']}"
        disposition, justification, residual, test = TRIAGE[(item["check"], name)]
        if f"function {test}(" not in test_source:
            raise RuntimeError(f"missing triage regression test {test}")
        locations = sorted({line for element in item["elements"] if element["type"] == "node" for line in element["source_mapping"]["lines"]})
        rows.append({"finding_id": item["id"], "detector": item["check"], "contract_function": name,
                     "severity": item["impact"], "source_location": f"contracts/{source}:" + ",".join(map(str, locations)),
                     "description": item["description"].strip(), "disposition": disposition,
                     "fix_applied": "No Solidity change; retained guard/design with regression evidence",
                     "residual_risk": residual, "justification": justification, "related_test": test,
                     "source_sha256": hashlib.sha256((ROOT / "contracts" / source).read_bytes()).hexdigest()})
    if len(rows) != len(TRIAGE):
        raise RuntimeError("triage does not cover exactly the reviewed findings")
    triage_csv = ROOT / "results/reviewer_revision/validation/slither_triage.csv"
    with triage_csv.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    md = ["# Slither Finding Dispositions", "", "All 15 original findings are retained. No detector or finding is suppressed.", "",
          "| Detector | Contract/function | Severity | Disposition | Justification | Residual risk |",
          "|---|---|---|---|---|---|"]
    for row in rows:
        md.append("| " + " | ".join(row[key].replace("|", "/") for key in ("detector", "contract_function", "severity", "disposition", "justification", "residual_risk")) + " |")
    md.extend(["", "The CSV includes exact finding IDs, source locations, source SHA-256 hashes, and related regression tests.",
               "Related tests exercise relevant guard behavior; they are not proofs eliminating every detector-class risk.",
               "Raw report: `results/reviewer_revision/raw/security/slither_final.json`."])
    (triage_csv.with_suffix(".md")).write_text("\n".join(md) + "\n")
    status = {
        "status": "completed_with_reviewed_findings",
        "analyzer": "slither",
        "analyzer_version": "0.11.6",
        "exact_command": "slither . --foundry-out-directory out --json ../results/reviewer_revision/raw/security/slither_final.json",
        "working_directory": "contracts",
        "configuration": "Foundry project; Solidity 0.8.24; default Slither detector set",
        "contracts_analyzed": 9,
        "detectors_available": 102,
        "detectors_suppressed": [],
        "findings_suppressed": [],
        "suppression_rationale": "none; every emitted finding is retained and manually triaged",
        "detector_results": len(detectors),
        "high_impact": impacts["High"],
        "medium_impact": impacts["Medium"],
        "low_impact": impacts["Low"],
        "informational": impacts["Informational"],
        "manual_triage_completed": True,
        "triaged_findings": len(rows),
        "triage_csv": "results/reviewer_revision/validation/slither_triage.csv",
        "raw_report_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
        "unmitigated_high_severity": 0,
        "conclusion": "No unmitigated high-severity Slither finding remained after manual triage.",
        "raw_json": str(raw.relative_to(ROOT)),
        "raw_text": "results/reviewer_revision/raw/security/slither_final.txt",
        "triage": "results/reviewer_revision/validation/slither_triage.md",
    }
    if not report.get("success") or len(detectors) != 15 or impacts["High"] != 0:
        raise RuntimeError("final Slither report does not match the reviewed evidence")
    path = ROOT / "results/reviewer_revision/validation/slither_status.json"
    path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, sort_keys=True))


if __name__ == "__main__":
    main()

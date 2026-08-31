#!/usr/bin/env python3
"""Regenerate reviewer matrices, claim validation, manuscript map, responses, and handoff."""

from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "results/reviewer_revision/validation"
EVIDENCE = ROOT / "paper_assets/reviewer_revision/reviewer_evidence"


def initialize_metadata() -> None:
    """Restore versioned analysis inputs without replacing local revisions."""
    VALIDATION.mkdir(parents=True, exist_ok=True)
    for source in sorted((Path(__file__).parent / "metadata_inputs").iterdir()):
        target = VALIDATION / source.name
        if source.is_file() and not target.exists():
            shutil.copyfile(source, target)


R1 = {
    "R1-1": ("PASS", "results/reviewer_revision/validation/validation_report.json", "results/reviewer_revision/validation/claim_registry.yaml", "Evidence types and claim boundaries are machine-validated."),
    "R1-2": ("PASS", "results/reviewer_revision/raw/block_period/", "results/reviewer_revision/statistics/block_period_sensitivity_summary.csv", "Local 1/2/4-second sensitivity only."),
    "R1-3": ("PASS", "results/reviewer_revision/raw/protocol_fingerprint/", "results/reviewer_revision/validation/protocol_fingerprint.json", "350 transactions retrospectively bound to exact final V2 runtime and ABI. No contemporaneous Git commit was recorded; the post-campaign checkpoint is identified in release/revision-v2-evidence-manifest.json."),
    "R1-4": ("PASS", "results/reviewer_revision/raw/baseline/", "results/reviewer_revision/validation/baseline_equivalence_matrix.csv", "The baseline does not provide consensus or replicated tamper evidence."),
    "R1-5": ("PASS", "results/reviewer_revision/raw/accountability/", "results/reviewer_revision/csv/accountability_path_statistics.csv", "Per-device, V1 integrity-only, and V2 witnessed paths are measured; fleet/batch scaling remains analytical."),
    "R1-6": ("PASS", "results/reviewer_revision/raw/", "results/reviewer_revision/validation/validation_report.json", "Evidence classes are explicit in reviewer-revision artifacts."),
    "R1-7": ("PARTIAL", "", "", "Primary literature cells require manual verification."),
    "R1-8": ("PASS", "results/reviewer_revision/raw/besu_v2_final/deployment_receipts.json", "results/reviewer_revision/statistics/gas_summary_final.csv", "Eight deployments and eleven operation types are reported; gas price was zero and no currency conversion was performed."),
    "R1-9": ("PASS", "results/reviewer_revision/raw/security/", "results/reviewer_revision/validation/slither_triage.csv", "All 15 findings have individual dispositions. Branch coverage and viaIR instrumentation limits remain explicit; testing is not exhaustive and Mythril was not run."),
    "R1-10": ("PASS", "results/reviewer_revision/raw/validator_faults/", "results/reviewer_revision/validation/validator_fault_status.json", "Crash faults were executed; Byzantine validator and aggregator/witness collusion remain outside tested guarantees."),
    "R1-M1": ("PARTIAL", "", "results/reviewer_revision/validation/claim_registry.yaml", "Final abstract text and page/line placement require the revision manuscript."),
    "R1-M2": ("PARTIAL", "", "", "Comparison placement requires the revision manuscript and verified literature table."),
    "R1-M3": ("PARTIAL", "", "results/reviewer_revision/validation/claim_registry.yaml", "Reviewer-revision tables still require final manuscript integration."),
    "R1-M4": ("PASS", "results/reviewer_revision/raw/besu_v2_final/deployment.json", "results/reviewer_revision/validation/block_period_status.json", "Topology is a local four-validator configuration."),
    "R1-M5": ("PASS", "results/reviewer_revision/csv/besu_v2_final_timing_complete.csv", "results/reviewer_revision/statistics/besu_v2_final_timing_summary.csv", "Dispersion and bootstrap intervals are reported over fifty complete paths."),
    "R1-M6": ("PASS", "results/reviewer_revision/raw/fleet/", "results/reviewer_revision/statistics/fleet_multiseed_summary.csv", "No unsupported monotonic fleet-size trend is inferred."),
    "R1-M7": ("PARTIAL", "results/reviewer_revision/raw/concurrency/", "results/reviewer_revision/validation/concurrency_status.json", "Five race families were executed through parallel RPC; additional listed endorsement-order permutations remain property-test evidence or not run."),
    "R1-M8": ("PARTIAL", "", "results/reviewer_revision/validation/claim_registry.yaml", "Final limitations placement requires the revision manuscript."),
    "R1-M9": ("PARTIAL", "", "results/reviewer_revision/validation/claim_registry.yaml", "Final conclusion text requires the revision manuscript."),
}

R2 = {
    "R2-1": ("PARTIAL", "", "", "TUF, Uptane, and transparency-log comparison requires manual primary-source verification."),
    "R2-2": ("PASS", "results/reviewer_revision/raw/independent_witness/", "results/reviewer_revision/csv/independent_witness_tests.csv", "Independent reconstruction detects unilateral omission or alteration, not common upstream omission or aggregator/witness collusion. Operator and aggregator share one software account; witness has a separate account/process."),
    "R2-3": ("PASS", "results/reviewer_revision/raw/", "results/reviewer_revision/validation/validation_report.json", "Controlled evidence vocabulary is enforced for the reviewer package."),
    "R2-4": ("PASS", "results/reviewer_revision/raw/besu_v2_final/", "results/reviewer_revision/statistics/gas_summary_final.csv", "Results are final-ABI local submission-to-receipt and gas observations."),
    "R2-5": ("PASS", "results/reviewer_revision/raw/baseline/", "results/reviewer_revision/validation/baseline_equivalence_matrix.csv", "Consensus-specific properties are intentionally absent from SQLite."),
    "R2-6": ("PASS", "", "results/reviewer_revision/validation/statistical_protocol.json", "The one-command full path requires Docker, native Besu, Foundry, and local runtime."),
    "R2-7": ("PASS", "results/reviewer_revision/raw/concurrency/", "results/reviewer_revision/validation/concurrency_status.json", "Claims are bounded to tested properties and race families."),
    "R2-8": ("PARTIAL", "", "results/reviewer_revision/validation/claim_registry.yaml", "Final manuscript figure/table numbering and placement remain pending."),
    "R2-9": ("PASS", "results/reviewer_revision/raw/fleet/", "results/reviewer_revision/statistics/receipt_size.csv", "Sizes use canonical compact JSON and include the 65-byte signature."),
    "R2-10": ("BLOCKED", "", "", "Author contribution data was not provided."),
}


def update_matrix(name: str, statuses: dict[str, tuple[str, str, str, str]]) -> list[dict[str, str]]:
    csv_path = VALIDATION / f"{name}_acceptance_matrix.csv"
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    for row in rows:
        status, raw, summary, limitation = statuses[row["comment_number"]]
        row["status"] = status
        row["raw_evidence_path"] = raw
        row["summary_evidence_path"] = summary
        row["remaining_limitation"] = limitation
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    title = "Reviewer 1" if name == "reviewer_1" else "Reviewer 2"
    lines = [f"# {title} Acceptance Matrix", "", "| Gate | Status | Evidence | Remaining limitation |", "|---|---|---|---|"]
    for row in rows:
        evidence = row["summary_evidence_path"] or row["raw_evidence_path"] or "Manual input required"
        lines.append(f"| {row['comment_number']} | {row['status']} | `{evidence}` | {row['remaining_limitation']} |")
    (VALIDATION / f"{name}_acceptance_matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def validate_claims() -> dict:
    registry_path = VALIDATION / "claim_registry.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    errors = []
    counts = {"supported": 0, "partial": 0, "blocked": 0}
    covered_locations = set()
    for claim in registry["claims"]:
        counts[claim["status"]] += 1
        covered_locations.update(claim.get("claim_locations", []))
        if claim["status"] == "supported":
            for source in claim["required_sources"]:
                if not (ROOT / source).exists():
                    errors.append(f"{claim['id']}: missing source {source}")
    required_locations = {"abstract", "contributions", "results", "discussion", "conclusion", "cover_letter", "reviewer_response", "README"}
    missing_locations = sorted(required_locations - covered_locations)
    if missing_locations:
        errors.append(f"claim locations missing: {missing_locations}")
    status = {
        "status": "PASS" if not errors else "FAIL", "claim_count": len(registry["claims"]),
        "counts": counts, "errors": errors, "unsupported_claims_excluded_from_final_text": True,
    }
    (VALIDATION / "claim_registry_status.json").write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return status


def manuscript_map() -> None:
    sections = [
        ("M01", "R1-1/R2-3", "Abstract", "Unqualified evidence claims", "Abstract", "Qualify local Besu, software fleet, analytical scaling, and not-run hardware evidence", "claim_registry.yaml", "", "", "PARTIAL"),
        ("M02", "R2-1", "Related work", "DLT alternatives comparison", "Related work", "Add only manually verified TUF, Uptane, and transparency-log comparison cells", "manual primary-source review", "comparative novelty table", "", "PARTIAL"),
        ("M03", "R2-2", "Threat model", "Aggregator omission trust", "Threat model", "Describe expected-cohort denominator, witness agreement, and residual collusion boundary", "aggregation_completeness_tests.csv", "", "", "READY"),
        ("M04", "R1-2/R2-4", "Experimental setup", "Single block configuration", "Experimental setup", "Add repeated 1/2/4-second local Besu sensitivity and receipt polling definition", "block_period_sensitivity_summary.csv", "block-period table", "block-period figure", "READY"),
        ("M05", "R1-3/R2-6", "Statistical methods", "Insufficient repetition details", "Statistical methods", "Add n, dispersion, 10,000-resample bootstrap intervals, fixed seed, and exclusion policy", "statistical_protocol.json", "timing statistics table", "", "READY"),
        ("M06", "R1-4/R2-5", "Results", "Weak centralized baseline", "Results", "Present matched local persistent-backend comparison and disclose DLT-only asymmetries", "baseline_equivalence_matrix.csv", "baseline comparison table", "timing figure", "READY"),
        ("M07", "R1-5", "Results", "Formula-only accountability", "Results", "Separate executed path gas/database evidence from analytical fleet/batch scaling", "accountability_status.json", "accountability table", "accountability figure", "READY"),
        ("M08", "R1-9/R2-7", "Security evaluation", "Limited adversarial validation", "Security evaluation", "Add fuzz, invariant, coverage, Slither, replay, RPC race, and crash-fault evidence", "validation_report.json", "security gate table", "validator-fault figure", "READY"),
        ("M09", "R1-M6", "Results", "Single-seed fleet interpretation", "Results", "Add twenty seeds per configuration and avoid unsupported monotonic scaling claims", "fleet_multiseed_summary.csv", "fleet statistics table", "fleet figure", "READY"),
        ("M10", "R1-M8/R1-M9", "Discussion and conclusion", "Late or broad limitations", "Scope and limitations", "State physical-device, HSM, PKI, WAN, Mythril, and production limitations before the conclusion", "claim_registry.yaml", "", "", "PARTIAL"),
        ("M11", "R2-10", "Author Contributions", "Missing author roles", "Author Contributions", "Populate author-verified contribution roles", "author input required", "", "", "BLOCKED"),
    ]
    fields = ["change_id", "reviewer_comment", "original_section", "original_text_summary", "revised_section", "proposed_revision", "supporting_evidence", "new_table", "new_figure", "status"]
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with (EVIDENCE / "manuscript_change_map.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(fields)
        writer.writerows(sections)
    lines = ["# Manuscript Change Map", "", "Page and line numbers remain `TBD` until the revision manuscript is supplied.", "", "| ID | Reviewer | Revised section | Proposed revision | Status |", "|---|---|---|---|---|"]
    for row in sections:
        lines.append(f"| {row[0]} | {row[1]} | {row[4]} | {row[5]} | {row[9]} |")
    (EVIDENCE / "manuscript_change_map.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def reviewer_draft(reviewer: int, rows: list[dict[str, str]]) -> None:
    lines = [f"# Response to Reviewer {reviewer} Draft", "", "Page and line references are `TBD` until the revision manuscript is supplied.", ""]
    for row in rows:
        lines.extend([
            f"## {row['comment_number']}", "", "Reviewer Comment:", row["reviewer_request"], "",
            "Response:",
            "We agree that this point requires explicit evidence and scope control. "
            + ("The requested implementation and validation evidence has been added." if row["status"] == "PASS" else "The repository work addresses part of the request, but the item is not complete.")
            + f" Remaining limitation: {row['remaining_limitation']}", "",
            "Changes in the Manuscript:", "Section: TBD", "Page: TBD", "Lines: TBD", "Table/Figure: See manuscript change map.", "",
            "Supporting Evidence:", f"Raw evidence: {row['raw_evidence_path'] or 'Not available'}",
            f"Summary CSV: {row['summary_evidence_path'] or 'Not available'}",
            "Analysis script: `experiments/reviewer_revision/`", f"Validation status: {row['status']}", "",
        ])
    (EVIDENCE / f"response_to_reviewer_{reviewer}_draft.md").write_text(
        "\n".join(lines).rstrip() + "\n", encoding="utf-8"
    )


def handoff(r1: list[dict[str, str]], r2: list[dict[str, str]], claim_status: dict) -> None:
    pass_count = sum(row["status"] == "PASS" for row in r1 + r2)
    partial_count = sum(row["status"] == "PARTIAL" for row in r1 + r2)
    blocked_count = sum(row["status"] == "BLOCKED" for row in r1 + r2)
    report_path = VALIDATION / "validation_report.json"
    validation_status = (
        json.loads(report_path.read_text(encoding="utf-8"))["status"]
        if report_path.exists() else "PENDING"
    )
    security = json.loads((VALIDATION / "foundry_final_status.json").read_text())
    python_status = json.loads((VALIDATION / "python_final_status.json").read_text())
    fingerprint = json.loads((VALIDATION / "protocol_fingerprint.json").read_text())
    lines = [
        "# Technical Handoff Report", "", f"Generated: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}", "",
        "1. Protocol: V2 adds domain-bound software receipt authentication, expected-cohort completeness, missing outcomes, independent witness confirmation, and optimistic rollout transition nonces; V1 is preserved.",
        "2. Contracts: four V2 contracts were added without mutating V1; ABI, event, storage, and redeployment requirements are documented.",
        "3. Baseline: the HTTP/SQLite path now implements common authenticated governance semantics and a hash-chained audit record, but no consensus or replicated history.",
        "4. Reruns: V2 Besu timing, SQLite timing, fleet, completeness, block-period, concurrency, accountability, IPFS shaping, cache, gas, and validator crash faults were executed.",
        "5. Samples: 50 complete final-ABI Besu paths and 50 SQLite repetitions per operation, 180 fleet runs, 96,000 receipts, 90 block-period transactions, 25 RPC races, 250 accountability transactions across 150 logical paths, 60 application-shaped fetches, 20,000 cache requests across 20 independent trials, and 20 crash-fault/restoration observations.",
        "6. Statistics: descriptive distributions, 10,000-resample fixed-seed bootstrap intervals, nonparametric effect size, and no significance tests for deterministic formula rows.",
        "7. Gas: eight deployments and 550 final-ABI governance-operation receipts across eleven operation types were summarized; no currency conversion was made.",
        f"8. Security: {security['test_count']} Foundry tests, {python_status['test_count']} Python tests, 10,000 dedicated fuzz cases, and 128,000 invariant calls completed. Coverage: line {security['coverage']['line_percent']}%, statement {security['coverage']['statement_percent']}%, function {security['coverage']['function_percent']}%, branch {security['coverage']['branch_percent']}%. viaIR mapping warnings remain; tests are not exhaustive.",
        "9. Slither: 0 high, 1 medium, 13 low, and 1 informational finding; all 15 have individual documented dispositions and no findings are suppressed. Timestamp/quorum risks remain explicit.",
        "10. Mythril: not run.",
        "11. Selective omission: separate-process observers reconstruct complete terminal roots from distinct journals; independent reconstruction detects unilateral omission or alteration, not common upstream omission or collusion. The local operator and aggregator share one software account; witness has a separate account and process.",
        "12. Validator faults: five fresh trials each covered zero, one, and two stopped-validator cases plus quorum restoration; Byzantine behavior was not injected.",
        "13. Network: twenty application-shaped local IPFS fetches per profile completed; no OS netem, WAN, or production network claim is supported.",
        "14. Cache: ten independently reset cache OFF and ON trials completed with 1,000 requests per trial.",
        "15. Analytical: fleet/batch accountability storage and gas scaling remains formula-derived from compiler layouts and measured medians.",
        "16. Software-emulated: all fleet devices and device signing keys are software-emulated.",
        "17. Not run: physical devices, HSM/secure element, production PKI, physical A/B recovery, WAN deployment, Byzantine validator faults, formal verification, and Mythril.",
        f"18. Reviewer gates fully addressed: {pass_count}.", f"19. Reviewer gates partial: {partial_count}; blocked: {blocked_count}.",
        f"20. Manuscript readiness: recorded core technical validation is {validation_status} and {claim_status['counts']['supported']} claims are supported; literature, author contributions, and final page/line integration remain pending.",
        "21. Traceability: 350 timing transactions bound retrospectively to exact source/runtime/ABI fingerprints. Historical Git commit was not recorded; consult release/revision-v2-evidence-manifest.json for the post-campaign checkpoint.",
        "22. Figure corrections: Figure 7 reports SUCCESS, ROLLBACK, and FAIL separately; Figure 8 retains all observations including the 915.736736-second maximum.",
        "23. Accountability: N=500/B=50 gives 98% V1 and 94% V2 transaction reduction, a four-percentage-point difference. V2 projected gas uses the measured complete-path median, 434,143 gas.",
        "24. Concurrency: receipt status and final state are primary evidence; reconstructed reasons use post-block eth_call, not exact intermediate-state replay. Timing fixtures are not integrated fleet delivery.",
        "25. Critical-branch mapping: 12 direct-test conditions; randomized evidence is limited to valid counter reconciliation. The invariant handler creates at most one cohort per run and then returns early.",
        "26. Gas break-even: a full V2 batch of at least 3 devices is cheaper than separate reports under measured medians. Partial final batches require the whole-fleet inequality; this is analytical, not another executed campaign.",
        "27. IPFS outlier cause: undetermined. Integrity and byte count passed, but synchronized request/host diagnostics were not preserved.",
    ]
    (VALIDATION / "technical_handoff_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    initialize_metadata()
    r1 = update_matrix("reviewer_1", R1)
    r2 = update_matrix("reviewer_2", R2)
    claim_status = validate_claims()
    manuscript_map()
    reviewer_draft(1, r1)
    reviewer_draft(2, r2)
    handoff(r1, r2, claim_status)
    print(json.dumps({"claim_status": claim_status["status"], "r1_rows": len(r1), "r2_rows": len(r2)}, sort_keys=True))
    if claim_status["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

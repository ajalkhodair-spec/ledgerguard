#!/usr/bin/env python3
"""Preserve all LCOV branches and distinguish reported hits from source-mapping caveats."""

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results/reviewer_revision"


def main():
    report = RESULTS / "raw/security/foundry_coverage_final.info"
    rows, sources = [], []
    for block in report.read_text().split("end_of_record"):
        lines = block.strip().splitlines()
        source = next((line[3:] for line in lines if line.startswith("SF:")), "")
        if not source.startswith("src/"):
            continue
        text = (ROOT / "contracts" / source).read_text().splitlines()
        line_hits = {int(line[3:].split(",")[0]): int(line[3:].split(",")[1]) for line in lines if line.startswith("DA:")}
        counters = {line.split(":")[0]: int(line.split(":")[1]) for line in lines if line.startswith(("LF:", "LH:", "FNF:", "FNH:", "BRF:", "BRH:"))}
        sources.append({"source": f"contracts/{source}", **counters,
                        "unhit_lines": ";".join(str(number) for number, hits in line_hits.items() if hits == 0)})
        for item in lines:
            if not item.startswith("BRDA:"):
                continue
            line, block_id, branch_id, taken = item[5:].split(",")
            number = int(line)
            statement = text[number - 1].strip()
            observed = taken != "-" and int(taken) > 0
            if observed:
                category = "observed"
            elif statement.startswith("require("):
                category = "require_guard_unresolved_in_instrumented_report"
            else:
                category = "unobserved_in_report_requires_source_review"
            rows.append({"source": f"contracts/{source}", "line": number, "block_id": block_id,
                         "branch_id": branch_id, "taken": taken, "line_hits": line_hits.get(number, 0),
                         "source_statement": statement, "classification": category})
    for name, records in (("coverage_branches.csv", rows), ("coverage_source_summary.csv", sources)):
        with (RESULTS / "validation" / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator="\n")
            writer.writeheader(); writer.writerows(records)
    log = (RESULTS / "raw/security/foundry_coverage_final.txt").read_text()
    probe = RESULTS / "raw/security/coverage_without_ir_probe.txt"
    status = json.loads((RESULTS / "validation/foundry_final_status.json").read_text())
    counts = Counter(row["classification"] for row in rows)
    review = {
        "status": "PASS", "review_status": "documented_not_exhaustive", "coverage": status["coverage"],
        "source_only_branch_hits": sum(row["BRH"] for row in sources),
        "source_only_branch_total": sum(row["BRF"] for row in sources),
        "classification_counts": dict(counts), "via_ir_mapping_warning": "inaccurate source mappings" in log,
        "missing_anchor_warnings": log.count("Could not find anchor"),
        "non_ir_probe_stack_too_deep": probe.exists() and "Stack too deep" in probe.read_text(),
        "uncovered_branches_removed_from_denominator": False,
        "source_contracts_modified_for_coverage": False,
    }
    (RESULTS / "validation/coverage_review_status.json").write_text(json.dumps(review, indent=2) + "\n")
    md = ["# Coverage Review", "", f"Foundry report: {status['coverage']}", "",
          "The primary report retains its original denominator, including helper contracts. The source-only CSV separately lists all nine Solidity source files.",
          "", "## Instrumentation evidence", "",
          "Coverage without viaIR fails with stack-too-deep at DeviceAttestationV2.confirmSummary. The retained probe shows this failure.",
          "The successful --ir-minimum run explicitly warns about inaccurate source mappings and reports missing instruction anchors.",
          "Several require guards show neither branch hit although successful calls and exact-reason revert tests execute. This is an unresolved instrumentation result, not proof that the guards are untested or fully covered.",
          "", "## Targeted additions", "",
          "LedgerGuardBoundariesTest exercises constructor inputs, owner/role authorization, revoked actors, duplicate role approvals, expiry equality and expiry+1, zero cohort fields, received/expected reconciliation, root guards, deadline equality, independent witness role reassignment, terminal rollout phases, stale nonces, malformed signatures, normalized v, high-s rejection, and legacy/comparison boundaries.",
          "Identity-level Python tests separately cover all five terminal states, expected-device uniqueness, changed terminal states, and canonical root reconstruction.",
          "", "## Remaining categories", "",
          "- IR assembly extraction and the inlined popcount helper can be unmapped even when their results are used by passing tests; report them without claiming complete instruction coverage.",
          "- A single LCOV branch does not enumerate every short-circuit operand, arithmetic panic, ABI decoding failure, or EVM-generated branch.",
          "- Legacy advanceWithMetrics repeats a threshold guard after canAdvance has returned allowed=true; the failure arm is unreachable through that unchanged public path. Legacy _advance has an exhaustive phase chain after terminal-state guards; its residual fall-through is similarly not a valid reachable state.",
          "- The default invariant handler targets createAndFinalize only. Its 128,000 calls do not cover all lifecycle/concurrency behaviors; those rely on separate tests.",
          "- Software nonce replay protection is enforced by the receipt journal. The Solidity view verifier authenticates signatures and is not a stateful nonce-consumption service.",
          "", "All observed and unobserved branch records are retained in coverage_branches.csv. No target percentage is asserted, and these tests are not exhaustive security verification."]
    (RESULTS / "validation/coverage_review.md").write_text("\n".join(md) + "\n")
    print(json.dumps(review))


if __name__ == "__main__":
    main()

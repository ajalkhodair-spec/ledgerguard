#!/usr/bin/env python3
"""Define and calculate signed-receipt JSON transport sizes from preserved fleet evidence."""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

from experiments.reviewer_revision.receipt_pipeline import (
    CohortContext,
    canonical_json,
    canonical_terminal_records,
)


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    run_rows = list(
        csv.DictReader((ROOT / "results/reviewer_revision/csv/fleet_multiseed_runs.csv").open(encoding="utf-8"))
    )
    output_rows: list[dict] = []
    for row in run_rows:
        receipt_path = ROOT / row["raw_evidence_path"] / "receipts.jsonl"
        receipts = [json.loads(line) for line in receipt_path.read_text(encoding="utf-8").splitlines() if line]
        encoded = [canonical_json(receipt) for receipt in receipts]
        unsigned = [canonical_json({key: value for key, value in receipt.items() if key != "signature"}) for receipt in receipts]
        if any(len(bytes.fromhex(receipt["signature"].removeprefix("0x"))) != 65 for receipt in receipts):
            raise RuntimeError(f"non-65-byte signature in {receipt_path}")
        sizes = [len(value) for value in encoded]
        unsigned_sizes = [len(value) for value in unsigned]
        first = receipts[0]
        context = CohortContext(
            release_id=int(first["releaseId"]), rollout_id=first["rolloutId"], epoch=int(first["epoch"]),
            cohort_id=first["cohortId"], deadline=int(first["deadline"]),
            target_version=int(first["targetVersion"]),
            expected_device_ids=tuple(sorted(receipt["deviceIdHash"] for receipt in receipts)),
        )
        accepted = {receipt["deviceIdHash"].lower(): receipt for receipt in receipts}
        terminal_records = canonical_terminal_records(context=context, accepted_receipts=accepted)
        terminal_record_sizes = [len(canonical_json(record)) for record in terminal_records]
        output_rows.append(
            {
                "run_id": row["run_id"], "fleet_size": row["fleet_size"],
                "configured_failure_rate": row["configured_failure_rate"], "seed": row["seed"],
                "receipt_count": len(receipts),
                "minimum_unsigned_payload_bytes": min(unsigned_sizes),
                "median_unsigned_payload_bytes": statistics.median(unsigned_sizes),
                "maximum_unsigned_payload_bytes": max(unsigned_sizes),
                "signature_bytes_per_receipt": 65,
                "minimum_signed_receipt_bytes": min(sizes),
                "median_signed_receipt_bytes": statistics.median(sizes),
                "maximum_signed_receipt_bytes": max(sizes),
                "receipt_hash_bytes_per_device": 32,
                "minimum_terminal_record_bytes": min(terminal_record_sizes),
                "median_terminal_record_bytes": statistics.median(terminal_record_sizes),
                "maximum_terminal_record_bytes": max(terminal_record_sizes),
                "terminal_leaf_hash_bytes_per_device": 32,
                "aggregate_signed_receipt_set_bytes": sum(sizes),
                "aggregate_terminal_set_bytes": sum(terminal_record_sizes),
                "aggregate_terminal_leaf_hash_bytes": len(terminal_records) * 32,
                "jsonl_file_bytes": receipt_path.stat().st_size,
                "encoding": "canonical_compact_sorted_utf8_json_with_0x_hex_signature",
                "evidence_type": "software_emulation_byte_count",
                "raw_evidence_path": str(receipt_path.relative_to(ROOT)),
            }
        )
    output = ROOT / "results/reviewer_revision/statistics/receipt_size.csv"
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    status = {
        "status": "PASS",
        "runs": len(output_rows),
        "encoding": "canonical compact sorted-key UTF-8 JSON",
        "signature_included": True,
        "signature_bytes": 65,
        "receipt_hash_bytes": 32,
        "terminal_leaf_hash_bytes": 32,
        "unsigned_payload_reported": True,
        "canonical_terminal_record_reported": True,
        "aggregate_signed_receipt_set_reported": True,
        "aggregate_terminal_set_reported": True,
        "per_receipt_and_aggregate_columns_separate": True,
        "variable_length_fields_measured_from_each_preserved_receipt": True,
    }
    (ROOT / "results/reviewer_revision/validation/receipt_size_status.json").write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()

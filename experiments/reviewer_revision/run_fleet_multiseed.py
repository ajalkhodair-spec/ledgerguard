#!/usr/bin/env python3
"""Execute the preregistered V2 authenticated software-fleet matrix."""

from __future__ import annotations

import csv
import json
import random
import time
from pathlib import Path

from eth_account import Account

from experiments.reviewer_revision.receipt_pipeline import (
    CohortContext,
    aggregate_receipts,
    device_id_hash,
    sign_receipt,
)


ROOT = Path(__file__).resolve().parents[2]
FLEET_SIZES = (100, 500, 1000)
FAILURE_RATES = (0.01, 0.02, 0.05)
SEEDS = tuple(range(2101, 2121))
CHAIN_ID = 1337
VERIFIER = "0x1111111111111111111111111111111111111111"
DEADLINE = 2_000_000_000


def main() -> None:
    output_path = ROOT / "results/reviewer_revision/csv/fleet_multiseed_runs.csv"
    raw_root = ROOT / "results/reviewer_revision/raw/fleet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw_root.mkdir(parents=True, exist_ok=True)

    keys = [f"0x{index + 1:064x}" for index in range(max(FLEET_SIZES))]
    devices = [device_id_hash(f"fleet-device-{index:05d}") for index in range(max(FLEET_SIZES))]
    identities = {
        device: Account.from_key(key).address.lower()
        for device, key in zip(devices, keys, strict=True)
    }
    rows: list[dict] = []
    for fleet_size in FLEET_SIZES:
        for failure_rate in FAILURE_RATES:
            for seed in SEEDS:
                run_id = f"fleet_v2_n{fleet_size}_f{int(failure_rate * 100):02d}_s{seed}"
                rng = random.Random(seed + fleet_size * 10_000 + int(failure_rate * 1_000_000))
                rollout_id = "0x" + f"{fleet_size * 10_000_000 + int(failure_rate * 1000) * 10_000 + seed:064x}"
                cohort_id = "0x" + f"{fleet_size * 20_000_000 + int(failure_rate * 1000) * 10_000 + seed:064x}"
                context = CohortContext(
                    release_id=1,
                    rollout_id=rollout_id,
                    epoch=1,
                    cohort_id=cohort_id,
                    deadline=DEADLINE,
                    target_version=2,
                    expected_device_ids=tuple(devices[:fleet_size]),
                )
                run_dir = raw_root / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                signed_receipts: list[dict] = []
                signing_start = time.perf_counter_ns()
                for index in range(fleet_size):
                    draw = rng.random()
                    if draw < failure_rate:
                        outcome = "ROLLBACK" if rng.random() < 0.3 else "FAIL"
                    else:
                        outcome = "SUCCESS"
                    receipt = {
                        "deviceIdHash": devices[index], "releaseId": 1, "rolloutId": rollout_id,
                        "epoch": 1, "cohortId": cohort_id, "deadline": DEADLINE,
                        "targetVersion": 2, "outcome": outcome, "observedAt": DEADLINE - 1,
                        "nonce": index + 1,
                    }
                    signed_receipts.append(sign_receipt(receipt, keys[index], CHAIN_ID, VERIFIER))
                signing_ms = (time.perf_counter_ns() - signing_start) / 1_000_000
                aggregation_start = time.perf_counter_ns()
                summary = aggregate_receipts(
                    context=context,
                    signed_receipts=signed_receipts,
                    active_device_signers={device: identities[device] for device in devices[:fleet_size]},
                    chain_id=CHAIN_ID,
                    verifying_contract=VERIFIER,
                )
                aggregation_ms = (time.perf_counter_ns() - aggregation_start) / 1_000_000
                receipts_path = run_dir / "receipts.jsonl"
                with receipts_path.open("w", encoding="utf-8") as stream:
                    for receipt in signed_receipts:
                        stream.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")
                summary_payload = {
                    "run_id": run_id,
                    "evidence_type": "authenticated_software_emulation",
                    "configured_failure_rate": failure_rate,
                    "seed": seed,
                    "fleet_size": fleet_size,
                    "signing_ms": signing_ms,
                    "aggregation_ms": aggregation_ms,
                    "summary": summary,
                }
                (run_dir / "summary.json").write_text(
                    json.dumps(summary_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
                rows.append(
                    {
                        "run_id": run_id, "fleet_size": fleet_size,
                        "configured_failure_rate": failure_rate, "seed": seed,
                        "expected_count": summary["expectedCount"],
                        "received_valid_count": summary["receivedValidCount"],
                        "success_count": summary["successCount"], "rollback_count": summary["rollbackCount"],
                        "fail_count": summary["failCount"], "rejected_count": summary["rejectedCount"],
                        "missing_count": summary["missingCount"],
                        "final_adoption_rate": summary["successRateExpectedCohort"],
                        "signing_ms": signing_ms, "aggregation_ms": aggregation_ms,
                        "receipt_root": summary["receiptRoot"],
                        "terminal_outcome_root": summary["terminalOutcomeRoot"],
                        "cohort_commitment": summary["cohortCommitment"],
                        "status": "success", "evidence_type": "authenticated_software_emulation",
                        "raw_evidence_path": str(run_dir.relative_to(ROOT)),
                    }
                )
                print(f"completed {run_id}", flush=True)

    with output_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"runs": len(rows), "failed": 0, "csv": str(output_path.relative_to(ROOT))}))


if __name__ == "__main__":
    main()

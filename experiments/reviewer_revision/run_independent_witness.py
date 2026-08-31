#!/usr/bin/env python3
"""Exercise independent aggregator/witness reconstruction from separate receipt journals."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from eth_account import Account

from experiments.reviewer_revision.receipt_pipeline import (
    ReceiptValidationError,
    assert_witness_agreement,
    device_id_hash,
    sign_receipt,
)


ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = ROOT / "results/reviewer_revision/raw/independent_witness"
CSV_PATH = ROOT / "results/reviewer_revision/csv/independent_witness_tests.csv"
PIPELINE = ROOT / "experiments/reviewer_revision/receipt_pipeline.py"
CHAIN_ID = 1337
VERIFIER = "0x1111111111111111111111111111111111111111"
ROLLOUT_ID = "0x" + "22" * 32
COHORT_ID = "0x" + "33" * 32
DEADLINE = 2_000_000_000


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def append_journal(path: Path, receipts: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        for receipt in receipts:
            stream.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")


def run_worker(case_dir: Path, actor: str) -> tuple[bool, dict | None, str]:
    journal = case_dir / f"{actor}_journal.jsonl"
    summary = case_dir / f"{actor}_summary.json"
    process = subprocess.run(
        [
            sys.executable,
            str(PIPELINE),
            "--context", str(case_dir / "context.json"),
            "--receipts", str(journal),
            "--identities", str(case_dir / "identities.json"),
            "--chain-id", str(CHAIN_ID),
            "--verifying-contract", VERIFIER,
            "--nonce-journal", str(case_dir / f"{actor}_consumed_nonces.jsonl"),
            "--out", str(summary),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": f"{ROOT}:{os.environ.get('PYTHONPATH', '')}"},
        check=False,
    )
    if process.returncode:
        return False, None, (process.stderr or process.stdout).strip().splitlines()[-1]
    return True, json.loads(summary.read_text(encoding="utf-8")), ""


def main() -> int:
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    keys = [f"0x{index + 1:064x}" for index in range(10)]
    devices = [device_id_hash(f"independent-device-{index:02d}") for index in range(10)]
    identities = {
        device: Account.from_key(key).address.lower()
        for device, key in zip(devices, keys, strict=True)
    }
    context = {
        "releaseId": 1,
        "rolloutId": ROLLOUT_ID,
        "epoch": 1,
        "cohortId": COHORT_ID,
        "deadline": DEADLINE,
        "targetVersion": 2,
        "expectedDeviceIds": devices,
    }
    receipts = []
    for index, (device, key) in enumerate(zip(devices, keys, strict=True)):
        unsigned = {
            "deviceIdHash": device,
            "releaseId": 1,
            "rolloutId": ROLLOUT_ID,
            "epoch": 1,
            "cohortId": COHORT_ID,
            "deadline": DEADLINE,
            "targetVersion": 2,
            "outcome": "FAIL" if index == 9 else "SUCCESS",
            "observedAt": DEADLINE - 1,
            "nonce": index + 1,
        }
        receipts.append(sign_receipt(unsigned, key, CHAIN_ID, VERIFIER))

    altered = dict(receipts[0])
    altered["outcome"] = "FAIL"
    cases = [
        ("complete_dual_delivery", receipts, receipts, "agreement", "independent complete streams agree"),
        ("aggregator_selective_omission", receipts[:-1], receipts, "mismatch", "witness detects aggregator omission"),
        ("witness_selective_omission", receipts, receipts[1:], "mismatch", "aggregator detects witness omission"),
        (
            "common_omission_residual_boundary",
            receipts[:-1],
            receipts[:-1],
            "agreement",
            "matching incomplete streams agree; common omission or collusion remains a trust boundary",
        ),
        ("altered_aggregator_receipt", [altered, *receipts[1:]], receipts, "aggregator_rejects", "altered signature-bound field is rejected"),
        ("duplicate_witness_receipt", receipts, [*receipts, receipts[0]], "witness_rejects", "duplicate device receipt is rejected"),
    ]

    rows = []
    for test_id, aggregator_receipts, witness_receipts, expected, interpretation in cases:
        case_dir = RAW_ROOT / test_id
        case_dir.mkdir(parents=True, exist_ok=True)
        for stale in case_dir.glob("*.json*"):
            stale.unlink()
        (case_dir / "context.json").write_text(json.dumps(context, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (case_dir / "identities.json").write_text(json.dumps(identities, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        append_journal(case_dir / "aggregator_journal.jsonl", aggregator_receipts)
        append_journal(case_dir / "witness_journal.jsonl", witness_receipts)
        aggregator_ok, aggregator_summary, aggregator_error = run_worker(case_dir, "aggregator")
        witness_ok, witness_summary, witness_error = run_worker(case_dir, "witness")

        if aggregator_ok and witness_ok:
            try:
                assert_witness_agreement(aggregator_summary or {}, witness_summary or {})
                observed = "agreement"
            except ReceiptValidationError:
                observed = "mismatch"
        elif not aggregator_ok and witness_ok:
            observed = "aggregator_rejects"
        elif aggregator_ok and not witness_ok:
            observed = "witness_rejects"
        else:
            observed = "both_reject"

        rows.append({
            "test_id": test_id,
            "aggregator_receipts": len(aggregator_receipts),
            "witness_receipts": len(witness_receipts),
            "aggregator_journal_sha256": sha256(case_dir / "aggregator_journal.jsonl"),
            "witness_journal_sha256": sha256(case_dir / "witness_journal.jsonl"),
            "aggregator_terminal_root": (aggregator_summary or {}).get("terminalOutcomeRoot", ""),
            "witness_terminal_root": (witness_summary or {}).get("terminalOutcomeRoot", ""),
            "expected_observation": expected,
            "observed": observed,
            "aggregator_error": aggregator_error,
            "witness_error": witness_error,
            "interpretation": interpretation,
            "evidence_type": "authenticated_dual_journal_software_emulation",
            "status": "PASS" if observed == expected else "FAIL",
            "raw_evidence_path": case_dir.relative_to(ROOT).as_posix(),
        })

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    failed = [row["test_id"] for row in rows if row["status"] != "PASS"]
    status = {
        "status": "PASS" if not failed else "FAIL",
        "cases": len(rows),
        "failed_cases": failed,
        "separate_process_reconstruction": True,
        "separate_receipt_journals": True,
        "software_device_dual_delivery": True,
        "witness_input_obtained_from_aggregator": False,
        "journal_population": "each device-produced authenticated receipt is appended independently; neither journal is copied from the other",
        "terminal_outcome_root_covers_expected_cohort": True,
        "common_omission_or_collusion_eliminated": False,
        "physical_devices_used": False,
    }
    status_path = ROOT / "results/reviewer_revision/validation/independent_witness_status.json"
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

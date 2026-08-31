#!/usr/bin/env python3
"""Generate raw and CSV evidence for the V2 software receipt pipeline."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from eth_account import Account

from experiments.reviewer_revision.receipt_pipeline import (
    CohortContext,
    ReceiptValidationError,
    aggregate_receipts,
    assert_witness_agreement,
    device_id_hash,
    receipt_merkle_proof,
    receipt_merkle_root,
    sign_receipt,
    verify_receipt_merkle_proof,
)


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "results/reviewer_revision/raw/completeness"
CSV_PATH = ROOT / "results/reviewer_revision/csv/aggregation_completeness_tests.csv"
CHAIN_ID = 1337
VERIFIER = "0x1111111111111111111111111111111111111111"
ROLLOUT_ID = "0x" + "22" * 32
COHORT_ID = "0x" + "33" * 32
DEADLINE = 2_000_000_000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_case(rows: list[dict], test_id: str, expected: str, observed: str, passed: bool, details: dict) -> None:
    raw_path = RAW_DIR / f"{test_id}.json"
    payload = {
        "test_id": test_id,
        "expected_behavior": expected,
        "observed_behavior": observed,
        "evidence_type": "software_emulation",
        "status": "passed" if passed else "failed",
        "timestamp_utc": utc_now(),
        "details": details,
    }
    raw_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows.append({
        "test_id": test_id,
        "expected_behavior": expected,
        "observed_behavior": observed,
        "evidence_type": "software_emulation",
        "status": payload["status"],
        "raw_evidence_path": str(raw_path.relative_to(ROOT)),
    })


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    keys = [f"0x{value:064x}" for value in range(1, 11)]
    devices = [device_id_hash(f"review-device-{index:02d}") for index in range(10)]
    identities = {
        device: Account.from_key(key).address.lower()
        for device, key in zip(devices, keys, strict=True)
    }
    context = CohortContext(
        release_id=1,
        rollout_id=ROLLOUT_ID,
        epoch=1,
        cohort_id=COHORT_ID,
        deadline=DEADLINE,
        target_version=2,
        expected_device_ids=tuple(devices),
    )

    def receipt(index: int, outcome: str) -> dict:
        unsigned = {
            "deviceIdHash": devices[index], "releaseId": 1, "rolloutId": ROLLOUT_ID,
            "epoch": 1, "cohortId": COHORT_ID, "deadline": DEADLINE,
            "targetVersion": 2, "outcome": outcome, "observedAt": DEADLINE - 1,
            "nonce": index + 1,
        }
        return sign_receipt(unsigned, keys[index], CHAIN_ID, VERIFIER)

    def aggregate(receipts: list[dict], *, chain_id: int = CHAIN_ID, contract: str = VERIFIER, signer_map=None):
        return aggregate_receipts(
            context=context, signed_receipts=receipts,
            active_device_signers=identities if signer_map is None else signer_map,
            chain_id=chain_id, verifying_contract=contract,
        )

    rows: list[dict] = []
    complete_receipts = [receipt(index, "SUCCESS" if index < 8 else "FAIL") for index in range(10)]
    complete = aggregate(complete_receipts)
    write_case(rows, "complete_expected_cohort",
        "All ten authenticated terminal receipts reconcile the expected cohort.",
        f"received={complete['receivedValidCount']}, missing={complete['missingCount']}",
        complete["receivedValidCount"] == 10 and complete["missingCount"] == 0, complete)

    canonical_root = receipt_merkle_root(complete_receipts)
    proofs_valid = True
    proof_depths: list[int] = []
    for signed_receipt in complete_receipts:
        leaf, proof, proof_root = receipt_merkle_proof(complete_receipts, signed_receipt["deviceIdHash"])
        proof_depths.append(len(proof))
        proofs_valid = proofs_valid and proof_root == canonical_root
        proofs_valid = proofs_valid and verify_receipt_merkle_proof(leaf, proof, canonical_root)
    reordered_root = receipt_merkle_root(list(reversed(complete_receipts)))
    leaf, proof, _ = receipt_merkle_proof(complete_receipts, complete_receipts[0]["deviceIdHash"])
    altered_leaf = bytearray.fromhex(leaf[2:])
    altered_leaf[-1] ^= 1
    altered_leaf_rejected = not verify_receipt_merkle_proof("0x" + altered_leaf.hex(), proof, canonical_root)
    altered_proof = [dict(step) for step in proof]
    altered_sibling = bytearray.fromhex(altered_proof[0]["sibling"][2:])
    altered_sibling[0] ^= 1
    altered_proof[0]["sibling"] = "0x" + altered_sibling.hex()
    altered_path_rejected = not verify_receipt_merkle_proof(leaf, altered_proof, canonical_root)
    write_case(
        rows,
        "merkle_proof_validation",
        "All feasible receipt proofs verify; altered leaves and paths fail; input order is canonicalized.",
        f"proofs={len(complete_receipts)}, altered_leaf_rejected={altered_leaf_rejected}, altered_path_rejected={altered_path_rejected}",
        proofs_valid and reordered_root == canonical_root and altered_leaf_rejected and altered_path_rejected,
        {
            "canonical_root": canonical_root,
            "reordered_root": reordered_root,
            "proof_count": len(complete_receipts),
            "proof_depths": proof_depths,
            "altered_leaf_rejected": altered_leaf_rejected,
            "altered_path_rejected": altered_path_rejected,
        },
    )

    omitted = aggregate(complete_receipts[:-2])
    write_case(rows, "selective_omission_denominator",
        "Omitted failed devices remain missing and cannot reduce the success denominator.",
        f"success={omitted['successCount']}, expected={omitted['expectedCount']}, missing={omitted['missingCount']}, rate={omitted['successRateExpectedCohort']}",
        omitted["successCount"] == 8 and omitted["expectedCount"] == 10 and omitted["missingCount"] == 2 and omitted["successRateExpectedCohort"] == 0.8,
        omitted)

    def rejected_case(test_id: str, expected: str, action) -> None:
        try:
            action()
        except ReceiptValidationError as exc:
            write_case(rows, test_id, expected, str(exc), True, {"rejection": str(exc)})
        else:
            write_case(rows, test_id, expected, "invalid input was accepted", False, {})

    tampered = dict(complete_receipts[0])
    tampered["outcome"] = "FAIL"
    rejected_case("tampered_signed_receipt", "Altered signed fields are rejected.", lambda: aggregate([tampered]))
    rejected_case("cross_chain_replay", "Receipt signed for another chain is rejected.", lambda: aggregate([complete_receipts[0]], chain_id=CHAIN_ID + 1))
    rejected_case("cross_contract_replay", "Receipt signed for another verifier is rejected.", lambda: aggregate([complete_receipts[0]], contract="0x2222222222222222222222222222222222222222"))
    rejected_case("duplicate_device_receipt", "A device contributes at most one terminal receipt.", lambda: aggregate([complete_receipts[0], complete_receipts[0]]))
    revoked = dict(identities)
    revoked.pop(devices[0])
    rejected_case("revoked_device_signer", "A revoked device signer is rejected.", lambda: aggregate([complete_receipts[0]], signer_map=revoked))
    witness = dict(complete)
    witness["successCount"] -= 1
    rejected_case("aggregator_witness_mismatch", "A witness summary with different counters is rejected.", lambda: assert_witness_agreement(complete, witness))

    with CSV_PATH.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    failed = sum(row["status"] != "passed" for row in rows)
    print(json.dumps({"cases": len(rows), "failed": failed, "csv": str(CSV_PATH.relative_to(ROOT))}, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

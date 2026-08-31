#!/usr/bin/env python3

from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from eth_account import Account

from experiments.reviewer_revision.receipt_pipeline import (
    CohortContext,
    ConsumedNonceJournal,
    ReceiptValidationError,
    aggregate_receipts,
    assert_witness_agreement,
    canonical_terminal_records,
    device_id_hash,
    receipt_merkle_proof,
    receipt_merkle_root,
    sign_receipt,
    terminal_leaf,
    terminal_outcome_merkle_root,
    verify_receipt_merkle_proof,
)


class ReceiptPipelineTest(unittest.TestCase):
    chain_id = 1337
    verifier = "0x1111111111111111111111111111111111111111"
    rollout_id = "0x" + "22" * 32
    cohort_id = "0x" + "33" * 32
    deadline = 2_000_000_000

    def setUp(self) -> None:
        self.keys = [f"0x{value:064x}" for value in range(1, 6)]
        self.devices = [device_id_hash(f"device-{index}") for index in range(5)]
        self.identities = {
            device: Account.from_key(key).address.lower()
            for device, key in zip(self.devices, self.keys, strict=True)
        }
        self.context = CohortContext(
            release_id=1,
            rollout_id=self.rollout_id,
            epoch=1,
            cohort_id=self.cohort_id,
            deadline=self.deadline,
            target_version=2,
            expected_device_ids=tuple(self.devices),
        )

    def receipt(self, index: int, outcome: str) -> dict:
        unsigned = {
            "deviceIdHash": self.devices[index],
            "releaseId": 1,
            "rolloutId": self.rollout_id,
            "epoch": 1,
            "cohortId": self.cohort_id,
            "deadline": self.deadline,
            "targetVersion": 2,
            "outcome": outcome,
            "observedAt": self.deadline - 1,
            "nonce": index + 1,
        }
        return sign_receipt(unsigned, self.keys[index], self.chain_id, self.verifier)

    def aggregate(self, receipts: list[dict]) -> dict:
        return aggregate_receipts(
            context=self.context,
            signed_receipts=receipts,
            active_device_signers=self.identities,
            chain_id=self.chain_id,
            verifying_contract=self.verifier,
        )

    def test_missing_device_remains_in_denominator(self) -> None:
        receipts = [self.receipt(0, "SUCCESS"), self.receipt(1, "SUCCESS"), self.receipt(2, "SUCCESS"), self.receipt(3, "FAIL")]
        summary = self.aggregate(receipts)
        self.assertEqual(summary["expectedCount"], 5)
        self.assertEqual(summary["receivedValidCount"], 4)
        self.assertEqual(summary["missingCount"], 1)
        self.assertEqual(summary["successRateExpectedCohort"], 0.6)
        self.assertNotEqual(summary["terminalOutcomeRoot"], summary["receiptRoot"])

    def test_omitting_failure_does_not_inflate_expected_cohort_success(self) -> None:
        full = self.aggregate([self.receipt(0, "SUCCESS"), self.receipt(1, "SUCCESS"), self.receipt(2, "SUCCESS"), self.receipt(3, "FAIL")])
        omitted = self.aggregate([self.receipt(0, "SUCCESS"), self.receipt(1, "SUCCESS"), self.receipt(2, "SUCCESS")])
        self.assertEqual(full["successRateExpectedCohort"], omitted["successRateExpectedCohort"])
        self.assertEqual(omitted["missingCount"], 2)

    def test_tampered_receipt_fails_signature_validation(self) -> None:
        receipt = self.receipt(0, "SUCCESS")
        receipt["outcome"] = "FAIL"
        with self.assertRaises(ReceiptValidationError):
            self.aggregate([receipt])

    def test_wrong_chain_replay_fails(self) -> None:
        receipt = self.receipt(0, "SUCCESS")
        with self.assertRaises(ReceiptValidationError):
            aggregate_receipts(
                context=self.context,
                signed_receipts=[receipt],
                active_device_signers=self.identities,
                chain_id=self.chain_id + 1,
                verifying_contract=self.verifier,
            )

    def test_duplicate_device_fails(self) -> None:
        receipt = self.receipt(0, "SUCCESS")
        with self.assertRaises(ReceiptValidationError):
            self.aggregate([receipt, receipt])

    def test_consumed_nonce_replay_fails_across_aggregations(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            journal = ConsumedNonceJournal(Path(temporary_directory) / "consumed.jsonl")
            receipt = self.receipt(0, "SUCCESS")
            aggregate_receipts(
                context=self.context,
                signed_receipts=[receipt],
                active_device_signers=self.identities,
                chain_id=self.chain_id,
                verifying_contract=self.verifier,
                nonce_journal=journal,
            )
            with self.assertRaises(ReceiptValidationError):
                aggregate_receipts(
                    context=self.context,
                    signed_receipts=[receipt],
                    active_device_signers=self.identities,
                    chain_id=self.chain_id,
                    verifying_contract=self.verifier,
                    nonce_journal=journal,
                )

    def test_zero_nonce_fails(self) -> None:
        receipt = self.receipt(0, "SUCCESS")
        receipt["nonce"] = 0
        with self.assertRaises(ReceiptValidationError):
            self.aggregate([receipt])

    def test_witness_mismatch_fails(self) -> None:
        aggregator = self.aggregate([self.receipt(0, "SUCCESS")])
        witness = dict(aggregator)
        witness["successCount"] = 0
        with self.assertRaises(ReceiptValidationError):
            assert_witness_agreement(aggregator, witness)

    def test_selective_delivery_to_witness_fails_agreement(self) -> None:
        aggregator = self.aggregate([self.receipt(0, "SUCCESS"), self.receipt(1, "FAIL")])
        witness = self.aggregate([self.receipt(0, "SUCCESS"), self.receipt(1, "FAIL"), self.receipt(2, "SUCCESS")])
        self.assertNotEqual(aggregator["receiptRoot"], witness["receiptRoot"])
        self.assertNotEqual(aggregator["terminalOutcomeRoot"], witness["terminalOutcomeRoot"])
        with self.assertRaises(ReceiptValidationError):
            assert_witness_agreement(aggregator, witness)

    def test_terminal_root_commits_every_expected_device(self) -> None:
        complete = self.aggregate([self.receipt(index, "SUCCESS") for index in range(5)])
        missing = self.aggregate([self.receipt(index, "SUCCESS") for index in range(4)])
        self.assertNotEqual(complete["terminalOutcomeRoot"], missing["terminalOutcomeRoot"])
        self.assertEqual(missing["missingCount"], 1)

        missing_record = {
            "protocolVersion": "V2",
            "releaseId": 1,
            "rolloutId": self.rollout_id,
            "epoch": 1,
            "cohortId": self.cohort_id,
            "deadline": self.deadline,
            "targetVersion": 2,
            "deviceIdHash": self.devices[4],
            "outcome": "MISSING",
            "observedAt": self.deadline,
            "nonce": 0,
            "receiptHash": "0x" + "00" * 32,
        }
        self.assertEqual(len(terminal_leaf(missing_record)), 32)

    def test_terminal_root_rebuilds_from_complete_ordered_cohort(self) -> None:
        receipts = [self.receipt(3, "FAIL"), self.receipt(0, "SUCCESS"), self.receipt(2, "ROLLBACK")]
        summary = self.aggregate(receipts)
        accepted = {receipt["deviceIdHash"].lower(): receipt for receipt in receipts}
        records = canonical_terminal_records(context=self.context, accepted_receipts=accepted)
        self.assertEqual(len(records), self.context.expected_count)
        self.assertEqual([record["deviceIdHash"] for record in records], sorted(self.devices))
        self.assertEqual(summary["terminalOutcomeRoot"], terminal_outcome_merkle_root(records))
        counts = {outcome: sum(record["outcome"] == outcome for record in records) for outcome in ("SUCCESS", "ROLLBACK", "FAIL", "REJECTED", "MISSING")}
        self.assertEqual(summary["successCount"], counts["SUCCESS"])
        self.assertEqual(summary["rollbackCount"], counts["ROLLBACK"])
        self.assertEqual(summary["failCount"], counts["FAIL"])
        self.assertEqual(summary["rejectedCount"], counts["REJECTED"])
        self.assertEqual(summary["missingCount"], counts["MISSING"])

    def test_terminal_root_is_independent_of_receipt_input_order(self) -> None:
        receipts = [self.receipt(index, "SUCCESS") for index in range(5)]
        self.assertEqual(
            self.aggregate(receipts)["terminalOutcomeRoot"],
            self.aggregate(list(reversed(receipts)))["terminalOutcomeRoot"],
        )

    def test_changed_terminal_state_changes_root(self) -> None:
        success = self.aggregate([self.receipt(0, "SUCCESS")])
        failed = self.aggregate([self.receipt(0, "FAIL")])
        self.assertNotEqual(success["terminalOutcomeRoot"], failed["terminalOutcomeRoot"])
        self.assertEqual(success["expectedCount"], failed["expectedCount"])

    def test_duplicate_expected_identity_is_rejected(self) -> None:
        duplicate = replace(self.context, expected_device_ids=(*self.devices, self.devices[0]))
        with self.assertRaisesRegex(ReceiptValidationError, "duplicate device identity"):
            aggregate_receipts(context=duplicate, signed_receipts=[], active_device_signers=self.identities,
                               chain_id=self.chain_id, verifying_contract=self.verifier)

    def test_each_terminal_identity_occurs_exactly_once_with_all_outcomes(self) -> None:
        outcomes = ["SUCCESS", "ROLLBACK", "FAIL", "REJECTED"]
        receipts = [self.receipt(i, value) for i, value in enumerate(outcomes)]
        accepted = {receipt["deviceIdHash"]: receipt for receipt in receipts}
        records = canonical_terminal_records(context=self.context, accepted_receipts=accepted)
        self.assertCountEqual([record["deviceIdHash"] for record in records], self.devices)
        self.assertEqual(len({record["deviceIdHash"] for record in records}), self.context.expected_count)
        self.assertCountEqual([record["outcome"] for record in records], [*outcomes, "MISSING"])
        summary = self.aggregate(receipts)
        for field in ("successCount", "rollbackCount", "failCount", "rejectedCount", "missingCount"):
            self.assertEqual(summary[field], 1)

    def test_conflicting_terminal_outcomes_for_device_fail(self) -> None:
        success = self.receipt(0, "SUCCESS")
        failure = self.receipt(0, "FAIL")
        with self.assertRaises(ReceiptValidationError):
            self.aggregate([success, failure])

    def test_unexpected_device_receipt_fails(self) -> None:
        key = f"0x{99:064x}"
        unsigned = {
            "deviceIdHash": device_id_hash("outside-device"), "releaseId": 1,
            "rolloutId": self.rollout_id, "epoch": 1, "cohortId": self.cohort_id,
            "deadline": self.deadline, "targetVersion": 2, "outcome": "SUCCESS",
            "observedAt": self.deadline - 1, "nonce": 99,
        }
        with self.assertRaises(ReceiptValidationError):
            self.aggregate([sign_receipt(unsigned, key, self.chain_id, self.verifier)])

    def test_missing_device_identity_changes_terminal_root(self) -> None:
        original = self.aggregate([])
        replacement_device = device_id_hash("replacement-missing-device")
        changed_context = CohortContext(
            release_id=self.context.release_id,
            rollout_id=self.context.rollout_id,
            epoch=self.context.epoch,
            cohort_id=self.context.cohort_id,
            deadline=self.context.deadline,
            target_version=self.context.target_version,
            expected_device_ids=(*self.context.expected_device_ids[:-1], replacement_device),
        )
        changed = aggregate_receipts(
            context=changed_context, signed_receipts=[], active_device_signers={},
            chain_id=self.chain_id, verifying_contract=self.verifier,
        )
        self.assertNotEqual(original["terminalOutcomeRoot"], changed["terminalOutcomeRoot"])

    def test_merkle_proofs_and_canonical_ordering(self) -> None:
        receipts = [self.receipt(index, "SUCCESS") for index in range(4)]
        root = receipt_merkle_root(receipts)
        self.assertEqual(root, receipt_merkle_root(list(reversed(receipts))))
        for receipt in receipts:
            leaf, proof, proof_root = receipt_merkle_proof(receipts, receipt["deviceIdHash"])
            self.assertEqual(root, proof_root)
            self.assertTrue(verify_receipt_merkle_proof(leaf, proof, root))

            altered_leaf_bytes = bytearray.fromhex(leaf[2:])
            altered_leaf_bytes[-1] ^= 1
            self.assertFalse(verify_receipt_merkle_proof("0x" + altered_leaf_bytes.hex(), proof, root))

            altered_proof = [dict(step) for step in proof]
            sibling = bytearray.fromhex(altered_proof[0]["sibling"][2:])
            sibling[0] ^= 1
            altered_proof[0]["sibling"] = "0x" + sibling.hex()
            self.assertFalse(verify_receipt_merkle_proof(leaf, altered_proof, root))


if __name__ == "__main__":
    unittest.main()

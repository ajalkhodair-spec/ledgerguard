#!/usr/bin/env python3
"""Authenticated receipt and completeness-aware aggregation for LedgerGuard V2."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from eth_account import Account
from eth_account.messages import encode_typed_data


OUTCOMES = {"SUCCESS", "ROLLBACK", "FAIL", "REJECTED"}
TERMINAL_OUTCOMES = OUTCOMES | {"MISSING"}
ZERO_ROOT = "0x" + ("00" * 32)


class ReceiptValidationError(ValueError):
    """Raised when a receipt or cohort violates the V2 protocol."""


class ConsumedNonceJournal:
    """Append-only observer journal that rejects reuse of a device nonce."""

    def __init__(self, path: Path):
        self.path = path

    def consume(self, entries: Iterable[tuple[str, int]]) -> None:
        normalized = [(_as_bytes32(device_id, "nonce device id"), int(nonce)) for device_id, nonce in entries]
        if any(nonce <= 0 for _, nonce in normalized):
            raise ReceiptValidationError("receipt nonce must be positive")
        if len(normalized) != len(set(normalized)):
            raise ReceiptValidationError("duplicate device nonce in receipt batch")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            stream.seek(0)
            consumed = {
                (entry["deviceIdHash"].lower(), int(entry["nonce"]))
                for line in stream
                if line.strip()
                for entry in [json.loads(line)]
            }
            replayed = sorted(set(normalized) & consumed)
            if replayed:
                raise ReceiptValidationError(
                    f"receipt nonce already consumed for device {replayed[0][0]}"
                )
            stream.seek(0, 2)
            for device_id, nonce in normalized:
                stream.write(json.dumps({"deviceIdHash": device_id, "nonce": nonce}, sort_keys=True) + "\n")
            stream.flush()
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def device_id_hash(device_id: str) -> str:
    return "0x" + hashlib.sha256(device_id.encode("utf-8")).hexdigest()


def _as_bytes32(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.startswith("0x") or len(value) != 66:
        raise ReceiptValidationError(f"{field} must be a 32-byte 0x-prefixed hex value")
    try:
        bytes.fromhex(value[2:])
    except ValueError as exc:
        raise ReceiptValidationError(f"{field} is not valid hex") from exc
    return value.lower()


def receipt_typed_data(receipt: dict[str, Any], chain_id: int, verifying_contract: str) -> dict[str, Any]:
    outcome_map = {"SUCCESS": 1, "ROLLBACK": 2, "FAIL": 3, "REJECTED": 4}
    if receipt.get("outcome") not in outcome_map:
        raise ReceiptValidationError("receipt has unsupported terminal outcome")
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "DeviceReceipt": [
                {"name": "deviceIdHash", "type": "bytes32"},
                {"name": "releaseId", "type": "uint256"},
                {"name": "rolloutId", "type": "bytes32"},
                {"name": "epoch", "type": "uint32"},
                {"name": "cohortId", "type": "bytes32"},
                {"name": "deadline", "type": "uint64"},
                {"name": "targetVersion", "type": "uint64"},
                {"name": "outcome", "type": "uint8"},
                {"name": "observedAt", "type": "uint64"},
                {"name": "nonce", "type": "uint256"},
            ],
        },
        "primaryType": "DeviceReceipt",
        "domain": {
            "name": "LedgerGuardDeviceReceipt",
            "version": "2",
            "chainId": int(chain_id),
            "verifyingContract": verifying_contract,
        },
        "message": {
            "deviceIdHash": _as_bytes32(receipt["deviceIdHash"], "deviceIdHash"),
            "releaseId": int(receipt["releaseId"]),
            "rolloutId": _as_bytes32(receipt["rolloutId"], "rolloutId"),
            "epoch": int(receipt["epoch"]),
            "cohortId": _as_bytes32(receipt["cohortId"], "cohortId"),
            "deadline": int(receipt["deadline"]),
            "targetVersion": int(receipt["targetVersion"]),
            "outcome": outcome_map[receipt["outcome"]],
            "observedAt": int(receipt["observedAt"]),
            "nonce": int(receipt["nonce"]),
        },
    }


def sign_receipt(
    receipt: dict[str, Any], private_key: str, chain_id: int, verifying_contract: str
) -> dict[str, Any]:
    message = encode_typed_data(full_message=receipt_typed_data(receipt, chain_id, verifying_contract))
    signed = Account.sign_message(message, private_key=private_key)
    return {**receipt, "signature": "0x" + signed.signature.hex()}


def recover_receipt_signer(receipt: dict[str, Any], chain_id: int, verifying_contract: str) -> str:
    signature = receipt.get("signature", "")
    if not isinstance(signature, str) or not signature.startswith("0x"):
        raise ReceiptValidationError("receipt signature is missing")
    unsigned = {key: value for key, value in receipt.items() if key != "signature"}
    message = encode_typed_data(full_message=receipt_typed_data(unsigned, chain_id, verifying_contract))
    try:
        return Account.recover_message(message, signature=signature).lower()
    except Exception as exc:
        raise ReceiptValidationError("receipt signature recovery failed") from exc


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _merkle_root(leaves: list[bytes]) -> bytes:
    if not leaves:
        return bytes(32)
    level = list(leaves)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [_sha256(level[index] + level[index + 1]) for index in range(0, len(level), 2)]
    return level[0]


def receipt_leaf(receipt: dict[str, Any]) -> bytes:
    return _sha256(canonical_json(receipt))


def canonical_receipt_leaves(receipts: list[dict[str, Any]]) -> list[tuple[str, bytes]]:
    ordered = sorted(receipts, key=lambda receipt: _as_bytes32(receipt["deviceIdHash"], "deviceIdHash"))
    device_ids = [_as_bytes32(receipt["deviceIdHash"], "deviceIdHash") for receipt in ordered]
    if len(device_ids) != len(set(device_ids)):
        raise ReceiptValidationError("duplicate terminal receipt for device")
    return [(device_id, receipt_leaf(receipt)) for device_id, receipt in zip(device_ids, ordered, strict=True)]


def receipt_merkle_root(receipts: list[dict[str, Any]]) -> str:
    return "0x" + _merkle_root([leaf for _, leaf in canonical_receipt_leaves(receipts)]).hex()


def receipt_merkle_proof(receipts: list[dict[str, Any]], device_id: str) -> tuple[str, list[dict[str, Any]], str]:
    leaves = canonical_receipt_leaves(receipts)
    normalized = _as_bytes32(device_id, "deviceIdHash")
    indexes = [index for index, (candidate, _) in enumerate(leaves) if candidate == normalized]
    if not indexes:
        raise ReceiptValidationError("device receipt is not in Merkle set")
    index = indexes[0]
    leaf = leaves[index][1]
    level = [value for _, value in leaves]
    proof: list[dict[str, Any]] = []
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        sibling_index = index - 1 if index % 2 else index + 1
        proof.append({"sibling": "0x" + level[sibling_index].hex(), "sibling_on_left": bool(index % 2)})
        level = [_sha256(level[position] + level[position + 1]) for position in range(0, len(level), 2)]
        index //= 2
    return "0x" + leaf.hex(), proof, "0x" + level[0].hex()


def verify_receipt_merkle_proof(leaf_hex: str, proof: list[dict[str, Any]], root_hex: str) -> bool:
    try:
        current = bytes.fromhex(leaf_hex.removeprefix("0x"))
        expected = bytes.fromhex(root_hex.removeprefix("0x"))
        if len(current) != 32 or len(expected) != 32:
            return False
        for step in proof:
            sibling = bytes.fromhex(str(step["sibling"]).removeprefix("0x"))
            if len(sibling) != 32:
                return False
            current = _sha256(sibling + current) if step["sibling_on_left"] else _sha256(current + sibling)
        return current == expected
    except (KeyError, TypeError, ValueError):
        return False


def cohort_commitment(expected_device_ids: Iterable[str]) -> str:
    normalized = sorted(_as_bytes32(value, "expected device id") for value in expected_device_ids)
    if len(normalized) != len(set(normalized)):
        raise ReceiptValidationError("cohort contains duplicate device identity")
    return "0x" + _merkle_root([bytes.fromhex(value[2:]) for value in normalized]).hex()


def terminal_record(
    *, context: "CohortContext", device_id: str, receipt: dict[str, Any] | None
) -> dict[str, Any]:
    normalized_device_id = _as_bytes32(device_id, "terminal device id")
    if receipt is None:
        outcome = "MISSING"
        receipt_hash = ZERO_ROOT
        observed_at = context.deadline
        nonce = 0
    else:
        outcome = str(receipt["outcome"])
        if outcome not in OUTCOMES:
            raise ReceiptValidationError("terminal record has unsupported outcome")
        receipt_hash = "0x" + receipt_leaf(receipt).hex()
        observed_at = int(receipt["observedAt"])
        nonce = int(receipt["nonce"])
    return {
        "protocolVersion": "V2",
        "releaseId": context.release_id,
        "rolloutId": context.rollout_id.lower(),
        "epoch": context.epoch,
        "cohortId": context.cohort_id.lower(),
        "deadline": context.deadline,
        "targetVersion": context.target_version,
        "deviceIdHash": normalized_device_id,
        "outcome": outcome,
        "observedAt": observed_at,
        "nonce": nonce,
        "receiptHash": receipt_hash,
    }


def terminal_leaf(record: dict[str, Any]) -> bytes:
    if record.get("outcome") not in TERMINAL_OUTCOMES:
        raise ReceiptValidationError("terminal leaf has unsupported outcome")
    return _sha256(canonical_json(record))


def canonical_terminal_records(
    *, context: "CohortContext", accepted_receipts: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        terminal_record(context=context, device_id=device_id, receipt=accepted_receipts.get(device_id))
        for device_id in sorted(_as_bytes32(value, "expected device id") for value in context.expected_device_ids)
    ]


def terminal_outcome_merkle_root(records: list[dict[str, Any]]) -> str:
    if not records:
        raise ReceiptValidationError("terminal outcome set must not be empty")
    device_ids = [_as_bytes32(record["deviceIdHash"], "terminal device id") for record in records]
    if device_ids != sorted(device_ids):
        raise ReceiptValidationError("terminal records are not canonically ordered")
    if len(device_ids) != len(set(device_ids)):
        raise ReceiptValidationError("duplicate terminal record for device")
    return "0x" + _merkle_root([terminal_leaf(record) for record in records]).hex()


@dataclass(frozen=True)
class CohortContext:
    release_id: int
    rollout_id: str
    epoch: int
    cohort_id: str
    deadline: int
    target_version: int
    expected_device_ids: tuple[str, ...]

    @property
    def expected_count(self) -> int:
        return len(self.expected_device_ids)

    @property
    def commitment(self) -> str:
        return cohort_commitment(self.expected_device_ids)


def aggregate_receipts(
    *,
    context: CohortContext,
    signed_receipts: list[dict[str, Any]],
    active_device_signers: dict[str, str],
    chain_id: int,
    verifying_contract: str,
    nonce_journal: ConsumedNonceJournal | None = None,
) -> dict[str, Any]:
    expected = {_as_bytes32(value, "expected device id") for value in context.expected_device_ids}
    if not expected:
        raise ReceiptValidationError("cohort must not be empty")
    if len(expected) != len(context.expected_device_ids):
        raise ReceiptValidationError("cohort contains duplicate device identity")

    accepted: dict[str, dict[str, Any]] = {}
    for receipt in signed_receipts:
        device_hash = _as_bytes32(receipt.get("deviceIdHash", ""), "deviceIdHash")
        if device_hash not in expected:
            raise ReceiptValidationError("receipt device is outside expected cohort")
        if device_hash in accepted:
            raise ReceiptValidationError("duplicate terminal receipt for device")
        if int(receipt.get("releaseId", -1)) != context.release_id:
            raise ReceiptValidationError("receipt release mismatch")
        if _as_bytes32(receipt.get("rolloutId", ""), "rolloutId") != context.rollout_id.lower():
            raise ReceiptValidationError("receipt rollout mismatch")
        if int(receipt.get("epoch", -1)) != context.epoch:
            raise ReceiptValidationError("receipt epoch mismatch")
        if _as_bytes32(receipt.get("cohortId", ""), "cohortId") != context.cohort_id.lower():
            raise ReceiptValidationError("receipt cohort mismatch")
        if int(receipt.get("deadline", -1)) != context.deadline:
            raise ReceiptValidationError("receipt deadline mismatch")
        if int(receipt.get("targetVersion", -1)) != context.target_version:
            raise ReceiptValidationError("receipt target version mismatch")
        if int(receipt.get("observedAt", context.deadline + 1)) > context.deadline:
            raise ReceiptValidationError("receipt observed after deadline")
        if receipt.get("outcome") not in OUTCOMES:
            raise ReceiptValidationError("receipt outcome is invalid")
        if int(receipt.get("nonce", 0)) <= 0:
            raise ReceiptValidationError("receipt nonce must be positive")

        recovered = recover_receipt_signer(receipt, chain_id, verifying_contract)
        expected_signer = active_device_signers.get(device_hash, "").lower()
        if not expected_signer or recovered != expected_signer:
            raise ReceiptValidationError("receipt signer is inactive or does not match device")
        accepted[device_hash] = receipt

    if nonce_journal is not None:
        nonce_journal.consume(
            (device_hash, int(receipt["nonce"])) for device_hash, receipt in accepted.items()
        )

    ordered = [accepted[device_hash] for device_hash in sorted(accepted)]
    leaves = [receipt_leaf(receipt) for receipt in ordered]
    counts = {name: 0 for name in sorted(OUTCOMES)}
    for receipt in ordered:
        counts[receipt["outcome"]] += 1

    received = len(ordered)
    missing = context.expected_count - received
    terminal_records = canonical_terminal_records(context=context, accepted_receipts=accepted)
    summary = {
        "protocol_version": "V2",
        "releaseId": context.release_id,
        "rolloutId": context.rollout_id.lower(),
        "epoch": context.epoch,
        "cohortId": context.cohort_id.lower(),
        "cohortCommitment": context.commitment,
        "deadline": context.deadline,
        "expectedCount": context.expected_count,
        "receivedValidCount": received,
        "successCount": counts["SUCCESS"],
        "rollbackCount": counts["ROLLBACK"],
        "failCount": counts["FAIL"],
        "rejectedCount": counts["REJECTED"],
        "missingCount": missing,
        "receiptRoot": "0x" + _merkle_root(leaves).hex(),
        "terminalOutcomeRoot": terminal_outcome_merkle_root(terminal_records),
        "successRateExpectedCohort": counts["SUCCESS"] / context.expected_count,
    }
    if summary["receivedValidCount"] + summary["missingCount"] != summary["expectedCount"]:
        raise ReceiptValidationError("summary does not reconcile expected cohort")
    if len(terminal_records) != summary["expectedCount"]:
        raise ReceiptValidationError("terminal outcome set does not cover expected cohort")
    return summary


def assert_witness_agreement(aggregator_summary: dict[str, Any], witness_summary: dict[str, Any]) -> None:
    if canonical_json(aggregator_summary) != canonical_json(witness_summary):
        raise ReceiptValidationError("aggregator and witness summaries differ")


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", required=True)
    parser.add_argument("--receipts", required=True)
    parser.add_argument("--identities", required=True)
    parser.add_argument("--chain-id", type=int, required=True)
    parser.add_argument("--verifying-contract", required=True)
    parser.add_argument("--nonce-journal")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    context_data = _load_json(args.context)
    context = CohortContext(
        release_id=int(context_data["releaseId"]),
        rollout_id=context_data["rolloutId"],
        epoch=int(context_data["epoch"]),
        cohort_id=context_data["cohortId"],
        deadline=int(context_data["deadline"]),
        target_version=int(context_data["targetVersion"]),
        expected_device_ids=tuple(context_data["expectedDeviceIds"]),
    )
    receipts = [json.loads(line) for line in Path(args.receipts).read_text(encoding="utf-8").splitlines() if line]
    identities = {key.lower(): value.lower() for key, value in _load_json(args.identities).items()}
    summary = aggregate_receipts(
        context=context,
        signed_receipts=receipts,
        active_device_signers=identities,
        chain_id=args.chain_id,
        verifying_contract=args.verifying_contract,
        nonce_journal=ConsumedNonceJournal(Path(args.nonce_journal)) if args.nonce_journal else None,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

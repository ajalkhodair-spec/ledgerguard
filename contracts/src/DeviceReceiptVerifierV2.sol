// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {DeviceIdentityRegistryV2} from "./DeviceIdentityRegistryV2.sol";

/// @title DeviceReceiptVerifierV2
/// @notice EIP-712 verifier for software-emulated LedgerGuard V2 device receipts.
contract DeviceReceiptVerifierV2 {
    enum Outcome {
        NONE,
        SUCCESS,
        ROLLBACK,
        FAIL,
        REJECTED
    }

    struct DeviceReceipt {
        bytes32 deviceIdHash;
        uint256 releaseId;
        bytes32 rolloutId;
        uint32 epoch;
        bytes32 cohortId;
        uint64 deadline;
        uint64 targetVersion;
        Outcome outcome;
        uint64 observedAt;
        uint256 nonce;
    }

    bytes32 public constant RECEIPT_TYPEHASH = keccak256(
        "DeviceReceipt(bytes32 deviceIdHash,uint256 releaseId,bytes32 rolloutId,uint32 epoch,bytes32 cohortId,uint64 deadline,uint64 targetVersion,uint8 outcome,uint64 observedAt,uint256 nonce)"
    );
    bytes32 private constant DOMAIN_TYPEHASH = keccak256(
        "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    );
    bytes32 private constant NAME_HASH = keccak256("LedgerGuardDeviceReceipt");
    bytes32 private constant VERSION_HASH = keccak256("2");
    uint256 private constant SECP256K1N_HALF =
        0x7fffffffffffffffffffffffffffffff5d576e7357a4501ddfe92f46681b20a0;

    DeviceIdentityRegistryV2 public immutable identityRegistry;

    constructor(address identityRegistry_) {
        require(identityRegistry_ != address(0), "DeviceReceiptVerifierV2: zero registry");
        identityRegistry = DeviceIdentityRegistryV2(identityRegistry_);
    }

    function domainSeparator() public view returns (bytes32) {
        return keccak256(abi.encode(DOMAIN_TYPEHASH, NAME_HASH, VERSION_HASH, block.chainid, address(this)));
    }

    function receiptStructHash(DeviceReceipt calldata receipt) public pure returns (bytes32) {
        return keccak256(
            abi.encode(
                RECEIPT_TYPEHASH,
                receipt.deviceIdHash,
                receipt.releaseId,
                receipt.rolloutId,
                receipt.epoch,
                receipt.cohortId,
                receipt.deadline,
                receipt.targetVersion,
                uint8(receipt.outcome),
                receipt.observedAt,
                receipt.nonce
            )
        );
    }

    function receiptDigest(DeviceReceipt calldata receipt) public view returns (bytes32) {
        return keccak256(abi.encodePacked("\x19\x01", domainSeparator(), receiptStructHash(receipt)));
    }

    function recoverSigner(DeviceReceipt calldata receipt, bytes calldata signature) public view returns (address) {
        if (signature.length != 65) return address(0);

        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := calldataload(signature.offset)
            s := calldataload(add(signature.offset, 32))
            v := byte(0, calldataload(add(signature.offset, 64)))
        }
        if (v < 27) v += 27;
        if (v != 27 && v != 28) return address(0);
        if (uint256(s) > SECP256K1N_HALF) return address(0);
        return ecrecover(receiptDigest(receipt), v, r, s);
    }

    function verifyReceipt(DeviceReceipt calldata receipt, bytes calldata signature) external view returns (bool) {
        if (receipt.deviceIdHash == bytes32(0)) return false;
        if (receipt.releaseId == 0 || receipt.rolloutId == bytes32(0) || receipt.epoch == 0) return false;
        if (receipt.cohortId == bytes32(0) || receipt.deadline == 0) return false;
        if (receipt.outcome == Outcome.NONE || receipt.observedAt > receipt.deadline) return false;

        address signer = recoverSigner(receipt, signature);
        if (signer == address(0)) return false;
        return identityRegistry.isActiveSigner(receipt.deviceIdHash, signer);
    }
}

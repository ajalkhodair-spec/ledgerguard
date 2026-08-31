// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {KeyManager} from "./KeyManager.sol";

/// @title NaiveDeviceReporting
/// @notice Baseline contract that records one outcome commitment per device.
/// @dev This is intentionally inefficient and exists only for strong_eval
///      accountability comparison against Merkle-root aggregation.
contract NaiveDeviceReporting {
    KeyManager public immutable keyManager;

    struct DeviceOutcome {
        bytes32 deviceIdHash;
        uint256 releaseId;
        uint32 epoch;
        uint8 status;
        bytes32 receiptHash;
        uint64 submittedAt;
    }

    DeviceOutcome[] public outcomes;
    mapping(bytes32 => bool) public seenReceipt;

    event DeviceOutcomeSubmitted(
        uint256 indexed index,
        uint256 indexed releaseId,
        uint32 indexed epoch,
        bytes32 deviceIdHash,
        uint8 status,
        bytes32 receiptHash
    );

    modifier onlyOperator() {
        (KeyManager.Role role, bool active) = keyManager.getSigner(msg.sender);
        require(active, "NaiveDeviceReporting: signer inactive");
        require(role == KeyManager.Role.OPERATOR, "NaiveDeviceReporting: not operator");
        _;
    }

    constructor(address keyManager_) {
        require(keyManager_ != address(0), "NaiveDeviceReporting: zero KeyManager");
        keyManager = KeyManager(keyManager_);
    }

    function submitDeviceOutcome(
        uint256 releaseId,
        uint32 epoch,
        bytes32 deviceIdHash,
        uint8 status,
        bytes32 receiptHash
    ) external onlyOperator returns (uint256 index) {
        require(deviceIdHash != bytes32(0), "NaiveDeviceReporting: empty device");
        require(receiptHash != bytes32(0), "NaiveDeviceReporting: empty receipt");
        require(!seenReceipt[receiptHash], "NaiveDeviceReporting: duplicate receipt");

        seenReceipt[receiptHash] = true;
        outcomes.push(DeviceOutcome({
            deviceIdHash: deviceIdHash,
            releaseId: releaseId,
            epoch: epoch,
            status: status,
            receiptHash: receiptHash,
            submittedAt: uint64(block.timestamp)
        }));
        index = outcomes.length - 1;
        emit DeviceOutcomeSubmitted(index, releaseId, epoch, deviceIdHash, status, receiptHash);
    }

    function outcomeCount() external view returns (uint256) {
        return outcomes.length;
    }
}

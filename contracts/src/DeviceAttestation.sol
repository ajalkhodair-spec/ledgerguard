// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {KeyManager} from "./KeyManager.sol";

/// @title DeviceAttestation
/// @notice Storage-bounded attestation: commit Merkle roots of per-device receipts.
/// @dev In a production system, this could be coupled with per-group policies and L2 anchoring.
contract DeviceAttestation {
    KeyManager public immutable keyManager;

    struct OutcomeRoot {
        bytes32 merkleRoot;
        uint32 successCount;
        uint32 failCount;
        uint32 rollbackCount;
        uint64 committedAt;
    }

    mapping(uint256 => mapping(uint32 => OutcomeRoot)) public outcomes;
    mapping(uint256 => uint32) public lastEpoch;

    event OutcomeRootCommitted(
        uint256 indexed releaseId,
        uint32 indexed epoch,
        bytes32 merkleRoot,
        uint32 successCount,
        uint32 failCount,
        uint32 rollbackCount
    );

    modifier onlyActiveRole(KeyManager.Role role) {
        (KeyManager.Role r, bool active) = keyManager.getSigner(msg.sender);
        require(active, "DeviceAttestation: signer inactive");
        require(r == role, "DeviceAttestation: wrong role");
        _;
    }

    constructor(address keyManager_) {
        require(keyManager_ != address(0), "DeviceAttestation: zero KeyManager");
        keyManager = KeyManager(keyManager_);
    }

    function submitOutcomeRoot(
        uint256 releaseId,
        uint32 epoch,
        bytes32 merkleRoot,
        uint32 successCount,
        uint32 failCount,
        uint32 rollbackCount
    ) external onlyActiveRole(KeyManager.Role.OPERATOR) {
        require(epoch == lastEpoch[releaseId] + 1, "DeviceAttestation: epoch must increment");
        outcomes[releaseId][epoch] = OutcomeRoot({
            merkleRoot: merkleRoot,
            successCount: successCount,
            failCount: failCount,
            rollbackCount: rollbackCount,
            committedAt: uint64(block.timestamp)
        });
        lastEpoch[releaseId] = epoch;

        emit OutcomeRootCommitted(releaseId, epoch, merkleRoot, successCount, failCount, rollbackCount);
    }
}

// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {KeyManager} from "./KeyManager.sol";
import {FirmwareRegistry} from "./FirmwareRegistry.sol";

/// @title RolloutCoordinatorV2
/// @notice Rollout state machine with optimistic phase/nonce concurrency control.
contract RolloutCoordinatorV2 {
    enum Phase { NONE, CANARY, BATCH, GLOBAL, COMPLETED, HALTED }

    struct Rollout {
        bytes32 deviceType;
        Phase phase;
        uint16 minimumSuccessBps;
        uint64 transitionNonce;
        uint64 startedAt;
        uint64 updatedAt;
    }

    KeyManager public immutable keyManager;
    FirmwareRegistry public immutable registry;
    mapping(uint256 => Rollout) private _rollouts;

    event RolloutStarted(uint256 indexed releaseId, bytes32 indexed deviceType, uint64 transitionNonce);
    event RolloutAdvanced(uint256 indexed releaseId, Phase previousPhase, Phase newPhase, uint64 transitionNonce, uint16 successRateBps);
    event RolloutHalted(uint256 indexed releaseId, Phase previousPhase, uint64 transitionNonce);

    modifier onlyActiveRole(KeyManager.Role expectedRole) {
        (KeyManager.Role role, bool active) = keyManager.getSigner(msg.sender);
        require(active, "RolloutCoordinatorV2: signer inactive");
        require(role == expectedRole, "RolloutCoordinatorV2: wrong role");
        _;
    }

    modifier onlyOperatorOrSecurity() {
        (KeyManager.Role role, bool active) = keyManager.getSigner(msg.sender);
        require(active, "RolloutCoordinatorV2: signer inactive");
        require(role == KeyManager.Role.OPERATOR || role == KeyManager.Role.SECURITY, "RolloutCoordinatorV2: role denied");
        _;
    }

    constructor(address keyManager_, address registry_) {
        require(keyManager_ != address(0), "RolloutCoordinatorV2: zero KeyManager");
        require(registry_ != address(0), "RolloutCoordinatorV2: zero registry");
        keyManager = KeyManager(keyManager_);
        registry = FirmwareRegistry(registry_);
    }

    function startRollout(uint256 releaseId, bytes32 deviceType, uint16 minimumSuccessBps)
        external onlyActiveRole(KeyManager.Role.OPERATOR)
    {
        require(_rollouts[releaseId].phase == Phase.NONE, "RolloutCoordinatorV2: already started");
        require(minimumSuccessBps > 0 && minimumSuccessBps <= 10_000, "RolloutCoordinatorV2: bad threshold");
        require(registry.isApproved(releaseId), "RolloutCoordinatorV2: release not approved");
        require(registry.latestApproved(deviceType) == releaseId, "RolloutCoordinatorV2: release not eligible");
        _rollouts[releaseId] = Rollout(deviceType, Phase.CANARY, minimumSuccessBps, 1, uint64(block.timestamp), uint64(block.timestamp));
        emit RolloutStarted(releaseId, deviceType, 1);
    }

    function advanceRollout(
        uint256 releaseId,
        Phase expectedPhase,
        uint64 expectedTransitionNonce,
        uint32 successCount,
        uint32 rollbackCount,
        uint32 failCount,
        uint32 rejectedCount,
        uint32 missingCount
    ) external onlyActiveRole(KeyManager.Role.OPERATOR) {
        Rollout storage rollout = _rollouts[releaseId];
        require(rollout.phase == expectedPhase, "RolloutCoordinatorV2: stale phase");
        require(rollout.transitionNonce == expectedTransitionNonce, "RolloutCoordinatorV2: stale transition nonce");
        require(registry.latestApproved(rollout.deviceType) == releaseId, "RolloutCoordinatorV2: release no longer eligible");
        require(rollout.phase == Phase.CANARY || rollout.phase == Phase.BATCH || rollout.phase == Phase.GLOBAL, "RolloutCoordinatorV2: terminal phase");
        uint256 expectedCount = uint256(successCount) + rollbackCount + failCount + rejectedCount + missingCount;
        require(expectedCount > 0, "RolloutCoordinatorV2: empty outcome set");
        uint16 successRateBps = uint16((uint256(successCount) * 10_000) / expectedCount);
        require(successRateBps >= rollout.minimumSuccessBps, "RolloutCoordinatorV2: success threshold not met");
        Phase previous = rollout.phase;
        if (previous == Phase.CANARY) rollout.phase = Phase.BATCH;
        else if (previous == Phase.BATCH) rollout.phase = Phase.GLOBAL;
        else rollout.phase = Phase.COMPLETED;
        rollout.transitionNonce += 1;
        rollout.updatedAt = uint64(block.timestamp);
        emit RolloutAdvanced(releaseId, previous, rollout.phase, rollout.transitionNonce, successRateBps);
    }

    function haltRollout(uint256 releaseId, Phase expectedPhase, uint64 expectedTransitionNonce)
        external onlyOperatorOrSecurity
    {
        Rollout storage rollout = _rollouts[releaseId];
        require(rollout.phase == expectedPhase, "RolloutCoordinatorV2: stale phase");
        require(rollout.transitionNonce == expectedTransitionNonce, "RolloutCoordinatorV2: stale transition nonce");
        require(rollout.phase != Phase.NONE && rollout.phase != Phase.HALTED, "RolloutCoordinatorV2: not active");
        Phase previous = rollout.phase;
        rollout.phase = Phase.HALTED;
        rollout.transitionNonce += 1;
        rollout.updatedAt = uint64(block.timestamp);
        emit RolloutHalted(releaseId, previous, rollout.transitionNonce);
    }

    function getRollout(uint256 releaseId) external view returns (Rollout memory) {
        return _rollouts[releaseId];
    }
}

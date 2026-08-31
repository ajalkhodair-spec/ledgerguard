// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {KeyManager} from "./KeyManager.sol";
import {FirmwareRegistry} from "./FirmwareRegistry.sol";

/// @title RolloutCoordinator
/// @notice Minimal staged rollout state machine (canary -> batch -> global) with halt.
contract RolloutCoordinator {
    KeyManager public immutable keyManager;
    FirmwareRegistry public immutable registry;
    uint16 public constant DEFAULT_MIN_SUCCESS_BPS = 9500;

    enum Phase {
        NONE,
        CANARY,
        BATCH,
        GLOBAL,
        COMPLETED,
        HALTED
    }

    struct Rollout {
        uint8 canaryPercent; // 0..100
        uint8 batchPercent;  // 0..100
        uint16 minSuccessBps;
        Phase phase;
        uint64 startedAt;
        uint64 updatedAt;
    }

    mapping(uint256 => Rollout) public rollouts;

    event RolloutStarted(uint256 indexed releaseId, uint8 canaryPercent, uint8 batchPercent, uint16 minSuccessBps);
    event RolloutAdvanced(uint256 indexed releaseId, Phase oldPhase, Phase newPhase, uint256 successRateBps);
    event RolloutHalted(uint256 indexed releaseId);

    modifier onlyActiveRole(KeyManager.Role role) {
        (KeyManager.Role r, bool active) = keyManager.getSigner(msg.sender);
        require(active, "RolloutCoordinator: signer inactive");
        require(r == role, "RolloutCoordinator: wrong role");
        _;
    }

    modifier onlyAnyActiveRole2(KeyManager.Role r1, KeyManager.Role r2) {
        (KeyManager.Role r, bool active) = keyManager.getSigner(msg.sender);
        require(active, "RolloutCoordinator: signer inactive");
        require(r == r1 || r == r2, "RolloutCoordinator: role denied");
        _;
    }

    constructor(address keyManager_, address registry_) {
        require(keyManager_ != address(0), "RolloutCoordinator: zero KeyManager");
        require(registry_ != address(0), "RolloutCoordinator: zero Registry");
        keyManager = KeyManager(keyManager_);
        registry = FirmwareRegistry(registry_);
    }

    function startRollout(uint256 releaseId, uint8 canaryPercent, uint8 batchPercent)
        external
        onlyActiveRole(KeyManager.Role.OPERATOR)
    {
        require(registry.isApproved(releaseId), "RolloutCoordinator: release not approved");
        require(canaryPercent > 0 && canaryPercent <= 100, "RolloutCoordinator: bad canary");
        require(batchPercent >= canaryPercent && batchPercent <= 100, "RolloutCoordinator: bad batch");

        Rollout storage r = rollouts[releaseId];
        require(r.phase == Phase.NONE, "RolloutCoordinator: already started");

        r.canaryPercent = canaryPercent;
        r.batchPercent = batchPercent;
        r.minSuccessBps = DEFAULT_MIN_SUCCESS_BPS;
        r.phase = Phase.CANARY;
        r.startedAt = uint64(block.timestamp);
        r.updatedAt = uint64(block.timestamp);

        emit RolloutStarted(releaseId, canaryPercent, batchPercent, DEFAULT_MIN_SUCCESS_BPS);
    }

    /// @notice Backward-compatible advance path for older PoC commands.
    /// @dev Q1 results use advanceWithMetrics so success-rate gating is measured.
    function advance(uint256 releaseId) external onlyActiveRole(KeyManager.Role.OPERATOR) {
        _advance(releaseId, 10000);
    }

    function canAdvance(uint256 releaseId, uint32 successCount, uint32 failCount, uint32 rollbackCount)
        public
        view
        returns (bool allowed, uint256 successRateBps, uint16 minSuccessBps)
    {
        Rollout storage r = rollouts[releaseId];
        minSuccessBps = r.minSuccessBps;
        uint256 totalReports = uint256(successCount) + uint256(failCount) + uint256(rollbackCount);
        if (totalReports == 0) return (false, 0, minSuccessBps);
        successRateBps = (uint256(successCount) * 10000) / totalReports;
        if (r.phase == Phase.NONE || r.phase == Phase.HALTED || r.phase == Phase.COMPLETED) {
            return (false, successRateBps, minSuccessBps);
        }
        return (successRateBps >= minSuccessBps, successRateBps, minSuccessBps);
    }

    function advanceWithMetrics(uint256 releaseId, uint32 successCount, uint32 failCount, uint32 rollbackCount)
        external
        onlyActiveRole(KeyManager.Role.OPERATOR)
    {
        (bool allowed, uint256 successRateBps, uint16 minSuccessBps) =
            canAdvance(releaseId, successCount, failCount, rollbackCount);
        require(allowed, "RolloutCoordinator: success below threshold");
        require(successRateBps >= minSuccessBps, "RolloutCoordinator: success below threshold");
        _advance(releaseId, successRateBps);
    }

    function _advance(uint256 releaseId, uint256 successRateBps) internal {
        Rollout storage r = rollouts[releaseId];
        require(r.phase != Phase.NONE, "RolloutCoordinator: not started");
        require(r.phase != Phase.HALTED, "RolloutCoordinator: halted");
        require(r.phase != Phase.COMPLETED, "RolloutCoordinator: completed");

        Phase oldPhase = r.phase;
        if (r.phase == Phase.CANARY) {
            r.phase = Phase.BATCH;
        } else if (r.phase == Phase.BATCH) {
            r.phase = Phase.GLOBAL;
        } else if (r.phase == Phase.GLOBAL) {
            r.phase = Phase.COMPLETED;
        }
        r.updatedAt = uint64(block.timestamp);
        emit RolloutAdvanced(releaseId, oldPhase, r.phase, successRateBps);
    }

    function halt(uint256 releaseId) external onlyAnyActiveRole2(KeyManager.Role.OPERATOR, KeyManager.Role.SECURITY) {
        Rollout storage r = rollouts[releaseId];
        require(r.phase != Phase.NONE, "RolloutCoordinator: not started");
        r.phase = Phase.HALTED;
        r.updatedAt = uint64(block.timestamp);
        emit RolloutHalted(releaseId);
    }

    function getRollout(uint256 releaseId)
        external
        view
        returns (uint8 canaryPercent, uint8 batchPercent, uint16 minSuccessBps, Phase phase, uint64 startedAt, uint64 updatedAt)
    {
        Rollout memory r = rollouts[releaseId];
        return (r.canaryPercent, r.batchPercent, r.minSuccessBps, r.phase, r.startedAt, r.updatedAt);
    }
}

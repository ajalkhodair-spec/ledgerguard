// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {KeyManager} from "./KeyManager.sol";

/// @title DeviceAttestationV2
/// @notice Completeness-aware outcome commitments with independent witness confirmation.
contract DeviceAttestationV2 {
    enum SummaryState {
        NONE,
        PROPOSED,
        FINALIZED
    }

    struct Cohort {
        uint256 releaseId;
        bytes32 rolloutId;
        uint32 epoch;
        bytes32 cohortId;
        bytes32 cohortCommitment;
        uint32 expectedCount;
        uint64 deadline;
        bool exists;
    }

    struct OutcomeSummary {
        bytes32 receiptRoot;
        bytes32 terminalOutcomeRoot;
        uint32 receivedValidCount;
        uint32 successCount;
        uint32 rollbackCount;
        uint32 failCount;
        uint32 rejectedCount;
        uint32 missingCount;
        address aggregator;
        address witness;
        uint64 proposedAt;
        uint64 finalizedAt;
        SummaryState state;
    }

    KeyManager public immutable keyManager;

    mapping(bytes32 => Cohort) private _cohorts;
    mapping(bytes32 => OutcomeSummary) private _summaries;
    mapping(uint256 => mapping(bytes32 => uint32)) public lastFinalizedEpoch;

    event CohortRegistered(
        bytes32 indexed cohortKey,
        uint256 indexed releaseId,
        bytes32 indexed rolloutId,
        uint32 epoch,
        bytes32 cohortId,
        bytes32 cohortCommitment,
        uint32 expectedCount,
        uint64 deadline
    );
    event OutcomeSummaryProposed(
        bytes32 indexed cohortKey,
        bytes32 receiptRoot,
        bytes32 terminalOutcomeRoot,
        uint32 receivedValidCount,
        uint32 successCount,
        uint32 rollbackCount,
        uint32 failCount,
        uint32 rejectedCount,
        uint32 missingCount,
        address indexed aggregator
    );
    event OutcomeSummaryFinalized(bytes32 indexed cohortKey, bytes32 summaryHash, address indexed witness);

    modifier onlyActiveRole(KeyManager.Role expectedRole) {
        (KeyManager.Role role, bool active) = keyManager.getSigner(msg.sender);
        require(active, "DeviceAttestationV2: signer inactive");
        require(role == expectedRole, "DeviceAttestationV2: wrong role");
        _;
    }

    constructor(address keyManager_) {
        require(keyManager_ != address(0), "DeviceAttestationV2: zero KeyManager");
        keyManager = KeyManager(keyManager_);
    }

    function cohortKey(uint256 releaseId, bytes32 rolloutId, uint32 epoch) public pure returns (bytes32) {
        return keccak256(abi.encode(releaseId, rolloutId, epoch));
    }

    function registerCohort(
        uint256 releaseId,
        bytes32 rolloutId,
        uint32 epoch,
        bytes32 cohortId,
        bytes32 cohortCommitment,
        uint32 expectedCount,
        uint64 deadline
    ) external onlyActiveRole(KeyManager.Role.OPERATOR) returns (bytes32 key) {
        require(releaseId != 0, "DeviceAttestationV2: zero release");
        require(rolloutId != bytes32(0), "DeviceAttestationV2: empty rollout");
        require(cohortId != bytes32(0), "DeviceAttestationV2: empty cohort");
        require(cohortCommitment != bytes32(0), "DeviceAttestationV2: empty cohort commitment");
        require(expectedCount > 0, "DeviceAttestationV2: empty expected cohort");
        require(deadline >= block.timestamp, "DeviceAttestationV2: deadline passed");
        require(epoch == lastFinalizedEpoch[releaseId][rolloutId] + 1, "DeviceAttestationV2: nonsequential epoch");

        key = cohortKey(releaseId, rolloutId, epoch);
        require(!_cohorts[key].exists, "DeviceAttestationV2: cohort already registered");
        _cohorts[key] = Cohort({
            releaseId: releaseId,
            rolloutId: rolloutId,
            epoch: epoch,
            cohortId: cohortId,
            cohortCommitment: cohortCommitment,
            expectedCount: expectedCount,
            deadline: deadline,
            exists: true
        });

        emit CohortRegistered(
            key,
            releaseId,
            rolloutId,
            epoch,
            cohortId,
            cohortCommitment,
            expectedCount,
            deadline
        );
    }

    function proposeSummary(
        bytes32 key,
        bytes32 receiptRoot,
        bytes32 terminalOutcomeRoot,
        uint32 receivedValidCount,
        uint32 successCount,
        uint32 rollbackCount,
        uint32 failCount,
        uint32 rejectedCount,
        uint32 missingCount
    ) external onlyActiveRole(KeyManager.Role.OPERATOR) {
        Cohort memory cohort = _cohorts[key];
        require(cohort.exists, "DeviceAttestationV2: unknown cohort");
        require(_summaries[key].state == SummaryState.NONE, "DeviceAttestationV2: summary already proposed");
        require(
            receivedValidCount == successCount + rollbackCount + failCount + rejectedCount,
            "DeviceAttestationV2: received count mismatch"
        );
        require(
            receivedValidCount + missingCount == cohort.expectedCount,
            "DeviceAttestationV2: expected count mismatch"
        );
        require(receivedValidCount == 0 || receiptRoot != bytes32(0), "DeviceAttestationV2: empty receipt root");
        require(terminalOutcomeRoot != bytes32(0), "DeviceAttestationV2: empty terminal root");
        require(block.timestamp >= cohort.deadline || missingCount == 0, "DeviceAttestationV2: missing before deadline");

        _summaries[key] = OutcomeSummary({
            receiptRoot: receiptRoot,
            terminalOutcomeRoot: terminalOutcomeRoot,
            receivedValidCount: receivedValidCount,
            successCount: successCount,
            rollbackCount: rollbackCount,
            failCount: failCount,
            rejectedCount: rejectedCount,
            missingCount: missingCount,
            aggregator: msg.sender,
            witness: address(0),
            proposedAt: uint64(block.timestamp),
            finalizedAt: 0,
            state: SummaryState.PROPOSED
        });

        emit OutcomeSummaryProposed(
            key,
            receiptRoot,
            terminalOutcomeRoot,
            receivedValidCount,
            successCount,
            rollbackCount,
            failCount,
            rejectedCount,
            missingCount,
            msg.sender
        );
    }

    function confirmSummary(
        bytes32 key,
        bytes32 receiptRoot,
        bytes32 terminalOutcomeRoot,
        uint32 receivedValidCount,
        uint32 successCount,
        uint32 rollbackCount,
        uint32 failCount,
        uint32 rejectedCount,
        uint32 missingCount
    ) external onlyActiveRole(KeyManager.Role.AUDITOR) {
        Cohort memory cohort = _cohorts[key];
        OutcomeSummary storage summary = _summaries[key];
        require(cohort.exists, "DeviceAttestationV2: unknown cohort");
        require(summary.state == SummaryState.PROPOSED, "DeviceAttestationV2: summary not proposed");
        require(summary.aggregator != msg.sender, "DeviceAttestationV2: witness not independent");

        bytes32 proposedHash = _summaryHash(key, summary);
        bytes32 witnessHash = _summaryHashFromFields(
            key,
            receiptRoot,
            terminalOutcomeRoot,
            receivedValidCount,
            successCount,
            rollbackCount,
            failCount,
            rejectedCount,
            missingCount
        );
        require(proposedHash == witnessHash, "DeviceAttestationV2: witness mismatch");

        summary.witness = msg.sender;
        summary.finalizedAt = uint64(block.timestamp);
        summary.state = SummaryState.FINALIZED;
        lastFinalizedEpoch[cohort.releaseId][cohort.rolloutId] = cohort.epoch;

        emit OutcomeSummaryFinalized(key, proposedHash, msg.sender);
    }

    function getCohort(bytes32 key) external view returns (Cohort memory) {
        return _cohorts[key];
    }

    function getSummary(bytes32 key) external view returns (OutcomeSummary memory) {
        return _summaries[key];
    }

    function summaryHash(bytes32 key) external view returns (bytes32) {
        OutcomeSummary storage summary = _summaries[key];
        require(summary.state != SummaryState.NONE, "DeviceAttestationV2: missing summary");
        return _summaryHash(key, summary);
    }

    function successRateBps(bytes32 key) external view returns (uint16) {
        Cohort memory cohort = _cohorts[key];
        OutcomeSummary memory summary = _summaries[key];
        require(cohort.exists && summary.state == SummaryState.FINALIZED, "DeviceAttestationV2: not finalized");
        return uint16((uint256(summary.successCount) * 10_000) / cohort.expectedCount);
    }

    function _summaryHash(bytes32 key, OutcomeSummary storage summary) internal view returns (bytes32) {
        return _summaryHashFromFields(
            key,
            summary.receiptRoot,
            summary.terminalOutcomeRoot,
            summary.receivedValidCount,
            summary.successCount,
            summary.rollbackCount,
            summary.failCount,
            summary.rejectedCount,
            summary.missingCount
        );
    }

    function _summaryHashFromFields(
        bytes32 key,
        bytes32 receiptRoot,
        bytes32 terminalOutcomeRoot,
        uint32 receivedValidCount,
        uint32 successCount,
        uint32 rollbackCount,
        uint32 failCount,
        uint32 rejectedCount,
        uint32 missingCount
    ) internal pure returns (bytes32) {
        return keccak256(
            abi.encode(
                key,
                receiptRoot,
                terminalOutcomeRoot,
                receivedValidCount,
                successCount,
                rollbackCount,
                failCount,
                rejectedCount,
                missingCount
            )
        );
    }
}

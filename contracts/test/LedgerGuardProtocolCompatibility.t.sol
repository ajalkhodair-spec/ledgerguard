// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {KeyManager} from "../src/KeyManager.sol";
import {DeviceAttestation} from "../src/DeviceAttestation.sol";
import {DeviceAttestationV2} from "../src/DeviceAttestationV2.sol";

contract CompatibilityOperator {
    function submitV1(
        DeviceAttestation attestation,
        uint256 releaseId,
        uint32 epoch,
        bytes32 root,
        uint32 success,
        uint32 fail,
        uint32 rollback
    ) external {
        attestation.submitOutcomeRoot(releaseId, epoch, root, success, fail, rollback);
    }

    function proposeV2WithoutCohort(DeviceAttestationV2 attestation, bytes32 key, bytes32 root) external {
        attestation.proposeSummary(key, root, keccak256("terminal-root"), 100, 98, 1, 1, 0, 0);
    }
}

contract LedgerGuardProtocolCompatibilityTest {
    bytes32 private constant V1_ROOT = keccak256("preserved-v1-root");
    bytes32 private constant ROLLOUT_ID = keccak256("fresh-v2-rollout");

    function testV1EvidenceRemainsReadableAndV2StartsFresh() public {
        KeyManager keyManager = new KeyManager();
        DeviceAttestation v1 = new DeviceAttestation(address(keyManager));
        DeviceAttestationV2 v2 = new DeviceAttestationV2(address(keyManager));
        CompatibilityOperator operator = new CompatibilityOperator();
        keyManager.setSigner(address(operator), KeyManager.Role.OPERATOR, true);

        operator.submitV1(v1, 7, 1, V1_ROOT, 98, 1, 1);
        (
            bytes32 preservedRoot,
            uint32 success,
            uint32 fail,
            uint32 rollback,
            uint64 committedAt
        ) = v1.outcomes(7, 1);
        require(preservedRoot == V1_ROOT, "V1 root changed");
        require(success == 98 && fail == 1 && rollback == 1, "V1 counters changed");
        require(committedAt != 0, "V1 commit timestamp missing");
        require(v2.lastFinalizedEpoch(7, ROLLOUT_ID) == 0, "V2 inherited V1 epoch state");
    }

    function testV1RootCannotBeInterpretedAsV2Summary() public {
        KeyManager keyManager = new KeyManager();
        DeviceAttestationV2 v2 = new DeviceAttestationV2(address(keyManager));
        CompatibilityOperator operator = new CompatibilityOperator();
        keyManager.setSigner(address(operator), KeyManager.Role.OPERATOR, true);

        bytes32 unregisteredV2Key = v2.cohortKey(7, ROLLOUT_ID, 1);
        bool failed;
        try operator.proposeV2WithoutCohort(v2, unregisteredV2Key, V1_ROOT) {
            failed = false;
        } catch {
            failed = true;
        }
        require(failed, "V1 root accepted without V2 cohort semantics");
    }
}

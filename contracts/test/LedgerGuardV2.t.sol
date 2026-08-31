// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {KeyManager} from "../src/KeyManager.sol";
import {DeviceIdentityRegistryV2} from "../src/DeviceIdentityRegistryV2.sol";
import {DeviceReceiptVerifierV2} from "../src/DeviceReceiptVerifierV2.sol";
import {DeviceAttestationV2} from "../src/DeviceAttestationV2.sol";

interface VmV2 {
    function addr(uint256 privateKey) external returns (address);
    function sign(uint256 privateKey, bytes32 digest) external returns (uint8 v, bytes32 r, bytes32 s);
    function warp(uint256 timestamp) external;
    function chainId(uint256 newChainId) external;
}

contract V2RoleActor {
    function registerCohort(
        DeviceAttestationV2 attestation,
        uint256 releaseId,
        bytes32 rolloutId,
        uint32 epoch,
        bytes32 cohortId,
        bytes32 cohortCommitment,
        uint32 expectedCount,
        uint64 deadline
    ) external returns (bytes32) {
        return attestation.registerCohort(
            releaseId,
            rolloutId,
            epoch,
            cohortId,
            cohortCommitment,
            expectedCount,
            deadline
        );
    }

    function propose(
        DeviceAttestationV2 attestation,
        bytes32 key,
        bytes32 root,
        bytes32 terminalRoot,
        uint32 received,
        uint32 success,
        uint32 rollback,
        uint32 fail,
        uint32 rejected,
        uint32 missing
    ) external {
        attestation.proposeSummary(key, root, terminalRoot, received, success, rollback, fail, rejected, missing);
    }

    function confirm(
        DeviceAttestationV2 attestation,
        bytes32 key,
        bytes32 root,
        bytes32 terminalRoot,
        uint32 received,
        uint32 success,
        uint32 rollback,
        uint32 fail,
        uint32 rejected,
        uint32 missing
    ) external {
        attestation.confirmSummary(key, root, terminalRoot, received, success, rollback, fail, rejected, missing);
    }
}

contract LedgerGuardV2Test {
    VmV2 private constant vm = VmV2(address(uint160(uint256(keccak256("hevm cheat code")))));

    uint256 private constant DEVICE_PRIVATE_KEY = 0xA11CE;
    uint256 private constant REPLACEMENT_DEVICE_PRIVATE_KEY = 0xB0B;
    bytes32 private constant DEVICE_ID = keccak256("device-0001");
    bytes32 private constant ROLLOUT_ID = keccak256("rollout-1");
    bytes32 private constant COHORT_ID = keccak256("cohort-1");
    bytes32 private constant COHORT_ROOT = keccak256("cohort-root");
    bytes32 private constant RECEIPT_ROOT = keccak256("receipt-root");
    bytes32 private constant TERMINAL_ROOT = keccak256("terminal-root");

    KeyManager private keyManager;
    DeviceIdentityRegistryV2 private identities;
    DeviceReceiptVerifierV2 private verifier;
    DeviceAttestationV2 private attestation;
    V2RoleActor private aggregator;
    V2RoleActor private witness;

    function setUp() public {
        keyManager = new KeyManager();
        identities = new DeviceIdentityRegistryV2(address(keyManager));
        verifier = new DeviceReceiptVerifierV2(address(identities));
        attestation = new DeviceAttestationV2(address(keyManager));
        aggregator = new V2RoleActor();
        witness = new V2RoleActor();

        keyManager.setSigner(address(aggregator), KeyManager.Role.OPERATOR, true);
        keyManager.setSigner(address(witness), KeyManager.Role.AUDITOR, true);
        identities.setDeviceIdentity(DEVICE_ID, vm.addr(DEVICE_PRIVATE_KEY), true);
    }

    function testValidAuthenticatedReceiptPasses() public {
        setUp();
        DeviceReceiptVerifierV2.DeviceReceipt memory receipt = _receipt(1, 1);
        bytes memory signature = _sign(receipt);
        require(verifier.verifyReceipt(receipt, signature), "valid receipt rejected");
    }

    function testRevokedDeviceReceiptFails() public {
        setUp();
        DeviceReceiptVerifierV2.DeviceReceipt memory receipt = _receipt(1, 1);
        bytes memory signature = _sign(receipt);
        identities.revokeDeviceIdentity(DEVICE_ID);
        require(!verifier.verifyReceipt(receipt, signature), "revoked device accepted");
    }

    function testDeviceKeyRotationRejectsOldKeyAndAcceptsReplacement() public {
        setUp();
        DeviceReceiptVerifierV2.DeviceReceipt memory receipt = _receipt(1, 1);
        bytes memory oldSignature = _sign(receipt);

        identities.setDeviceIdentity(DEVICE_ID, vm.addr(REPLACEMENT_DEVICE_PRIVATE_KEY), true);
        (, bool active, uint64 revision) = identities.getDeviceIdentity(DEVICE_ID);
        require(active && revision == 2, "rotation revision not recorded");
        require(!verifier.verifyReceipt(receipt, oldSignature), "old key accepted after rotation");
        require(
            verifier.verifyReceipt(receipt, _signWithKey(receipt, REPLACEMENT_DEVICE_PRIVATE_KEY)),
            "replacement key rejected"
        );
    }

    function testReplacementAfterRevocationRestoresOnlyNewKey() public {
        setUp();
        DeviceReceiptVerifierV2.DeviceReceipt memory receipt = _receipt(1, 1);
        bytes memory oldSignature = _sign(receipt);
        identities.revokeDeviceIdentity(DEVICE_ID);
        identities.setDeviceIdentity(DEVICE_ID, vm.addr(REPLACEMENT_DEVICE_PRIVATE_KEY), true);
        (, bool active, uint64 revision) = identities.getDeviceIdentity(DEVICE_ID);
        require(active && revision == 3, "replacement revision not recorded");
        require(!verifier.verifyReceipt(receipt, oldSignature), "revoked key accepted after replacement");
        require(
            verifier.verifyReceipt(receipt, _signWithKey(receipt, REPLACEMENT_DEVICE_PRIVATE_KEY)),
            "replacement key not active"
        );
    }

    function testCrossContractReplayFails() public {
        setUp();
        DeviceReceiptVerifierV2.DeviceReceipt memory receipt = _receipt(1, 1);
        bytes memory signature = _sign(receipt);
        DeviceReceiptVerifierV2 otherVerifier = new DeviceReceiptVerifierV2(address(identities));
        require(!otherVerifier.verifyReceipt(receipt, signature), "cross-contract replay accepted");
    }

    function testCrossChainReplayFails() public {
        setUp();
        DeviceReceiptVerifierV2.DeviceReceipt memory receipt = _receipt(1, 1);
        bytes memory signature = _sign(receipt);
        vm.chainId(block.chainid + 1);
        require(!verifier.verifyReceipt(receipt, signature), "cross-chain replay accepted");
    }

    function testCrossReleaseReplayFails() public {
        setUp();
        DeviceReceiptVerifierV2.DeviceReceipt memory receipt = _receipt(1, 1);
        bytes memory signature = _sign(receipt);
        receipt.releaseId = 2;
        require(!verifier.verifyReceipt(receipt, signature), "cross-release replay accepted");
    }

    function testCrossRolloutReplayFails() public {
        setUp();
        DeviceReceiptVerifierV2.DeviceReceipt memory receipt = _receipt(1, 1);
        bytes memory signature = _sign(receipt);
        receipt.rolloutId = keccak256("other-rollout");
        require(!verifier.verifyReceipt(receipt, signature), "cross-rollout replay accepted");
    }

    function testCrossEpochReplayFails() public {
        setUp();
        DeviceReceiptVerifierV2.DeviceReceipt memory receipt = _receipt(1, 1);
        bytes memory signature = _sign(receipt);
        receipt.epoch = 2;
        require(!verifier.verifyReceipt(receipt, signature), "cross-epoch replay accepted");
    }

    function testCrossCohortReplayFails() public {
        setUp();
        DeviceReceiptVerifierV2.DeviceReceipt memory receipt = _receipt(1, 1);
        bytes memory signature = _sign(receipt);
        receipt.cohortId = keccak256("other-cohort");
        require(!verifier.verifyReceipt(receipt, signature), "cross-cohort replay accepted");
    }

    function testNonceMutationInvalidatesSignature() public {
        setUp();
        DeviceReceiptVerifierV2.DeviceReceipt memory receipt = _receipt(1, 1);
        bytes memory signature = _sign(receipt);
        receipt.nonce = 2;
        require(!verifier.verifyReceipt(receipt, signature), "nonce mutation accepted");
    }

    function testReceiptAfterDeadlineFails() public {
        setUp();
        DeviceReceiptVerifierV2.DeviceReceipt memory receipt = _receipt(1, 1);
        receipt.observedAt = receipt.deadline + 1;
        bytes memory signature = _sign(receipt);
        require(!verifier.verifyReceipt(receipt, signature), "late receipt accepted");
    }

    function testCompletenessUsesExpectedCohortDenominator() public {
        setUp();
        uint64 deadline = uint64(block.timestamp + 10);
        bytes32 key = aggregator.registerCohort(
            attestation, 1, ROLLOUT_ID, 1, COHORT_ID, COHORT_ROOT, 100, deadline
        );
        vm.warp(deadline);
        aggregator.propose(attestation, key, RECEIPT_ROOT, TERMINAL_ROOT, 90, 90, 0, 0, 0, 10);
        witness.confirm(attestation, key, RECEIPT_ROOT, TERMINAL_ROOT, 90, 90, 0, 0, 0, 10);

        require(attestation.successRateBps(key) == 9000, "success denominator is not expected cohort");
        DeviceAttestationV2.OutcomeSummary memory summary = attestation.getSummary(key);
        require(summary.state == DeviceAttestationV2.SummaryState.FINALIZED, "summary not finalized");
        require(summary.missingCount == 10, "missing devices not committed");
    }

    function testExpectedCountMismatchReverts() public {
        setUp();
        uint64 deadline = uint64(block.timestamp);
        bytes32 key = aggregator.registerCohort(
            attestation, 1, ROLLOUT_ID, 1, COHORT_ID, COHORT_ROOT, 100, deadline
        );
        bool failed;
        try aggregator.propose(attestation, key, RECEIPT_ROOT, TERMINAL_ROOT, 90, 90, 0, 0, 0, 5) {
            failed = false;
        } catch {
            failed = true;
        }
        require(failed, "incomplete counters accepted");
    }

    function testMissingBeforeDeadlineReverts() public {
        setUp();
        uint64 deadline = uint64(block.timestamp + 100);
        bytes32 key = aggregator.registerCohort(
            attestation, 1, ROLLOUT_ID, 1, COHORT_ID, COHORT_ROOT, 100, deadline
        );
        bool failed;
        try aggregator.propose(attestation, key, RECEIPT_ROOT, TERMINAL_ROOT, 90, 90, 0, 0, 0, 10) {
            failed = false;
        } catch {
            failed = true;
        }
        require(failed, "missing devices finalized before deadline");
    }

    function testWitnessCounterMismatchReverts() public {
        setUp();
        uint64 deadline = uint64(block.timestamp);
        bytes32 key = aggregator.registerCohort(
            attestation, 1, ROLLOUT_ID, 1, COHORT_ID, COHORT_ROOT, 100, deadline
        );
        aggregator.propose(attestation, key, RECEIPT_ROOT, TERMINAL_ROOT, 100, 98, 1, 1, 0, 0);
        bool failed;
        try witness.confirm(attestation, key, RECEIPT_ROOT, TERMINAL_ROOT, 100, 99, 0, 1, 0, 0) {
            failed = false;
        } catch {
            failed = true;
        }
        require(failed, "conflicting witness counters accepted");
    }

    function testWitnessTerminalRootMismatchReverts() public {
        setUp();
        uint64 deadline = uint64(block.timestamp);
        bytes32 key = aggregator.registerCohort(
            attestation, 1, ROLLOUT_ID, 1, COHORT_ID, COHORT_ROOT, 10, deadline
        );
        aggregator.propose(attestation, key, RECEIPT_ROOT, TERMINAL_ROOT, 10, 10, 0, 0, 0, 0);
        bool failed;
        try witness.confirm(
            attestation, key, RECEIPT_ROOT, keccak256("different-terminal-root"), 10, 10, 0, 0, 0, 0
        ) {
            failed = false;
        } catch {
            failed = true;
        }
        require(failed, "conflicting terminal root accepted");
    }

    function testEmptyTerminalRootReverts() public {
        setUp();
        bytes32 key = aggregator.registerCohort(
            attestation, 1, ROLLOUT_ID, 1, COHORT_ID, COHORT_ROOT, 1, uint64(block.timestamp)
        );
        bool failed;
        try aggregator.propose(attestation, key, RECEIPT_ROOT, bytes32(0), 1, 1, 0, 0, 0, 0) {
            failed = false;
        } catch {
            failed = true;
        }
        require(failed, "empty terminal root accepted");
    }

    function testConflictingRootForSameEpochReverts() public {
        setUp();
        uint64 deadline = uint64(block.timestamp);
        bytes32 key = aggregator.registerCohort(
            attestation, 1, ROLLOUT_ID, 1, COHORT_ID, COHORT_ROOT, 10, deadline
        );
        aggregator.propose(attestation, key, RECEIPT_ROOT, TERMINAL_ROOT, 10, 10, 0, 0, 0, 0);
        witness.confirm(attestation, key, RECEIPT_ROOT, TERMINAL_ROOT, 10, 10, 0, 0, 0, 0);

        bool failed;
        try aggregator.propose(attestation, key, keccak256("conflict"), TERMINAL_ROOT, 10, 10, 0, 0, 0, 0) {
            failed = false;
        } catch {
            failed = true;
        }
        require(failed, "conflicting root accepted");
    }

    function testNonsequentialEpochReverts() public {
        setUp();
        bool failed;
        try aggregator.registerCohort(
            attestation, 1, ROLLOUT_ID, 2, COHORT_ID, COHORT_ROOT, 10, uint64(block.timestamp)
        ) {
            failed = false;
        } catch {
            failed = true;
        }
        require(failed, "nonsequential epoch accepted");
    }

    function testFuzzCompletenessReconciliation(uint16 expectedRaw, uint16 missingRaw) public {
        setUp();
        uint32 expected = uint32(expectedRaw % 1000) + 1;
        uint32 missing = uint32(missingRaw) % (expected + 1);
        uint32 received = expected - missing;
        uint64 deadline = uint64(block.timestamp);
        bytes32 key = aggregator.registerCohort(
            attestation, 1, ROLLOUT_ID, 1, COHORT_ID, COHORT_ROOT, expected, deadline
        );
        aggregator.propose(
            attestation,
            key,
            received == 0 ? bytes32(0) : RECEIPT_ROOT,
            TERMINAL_ROOT,
            received,
            received,
            0,
            0,
            0,
            missing
        );
        witness.confirm(
            attestation,
            key,
            received == 0 ? bytes32(0) : RECEIPT_ROOT,
            TERMINAL_ROOT,
            received,
            received,
            0,
            0,
            0,
            missing
        );
        DeviceAttestationV2.OutcomeSummary memory summary = attestation.getSummary(key);
        require(summary.receivedValidCount + summary.missingCount == expected, "fuzz reconciliation failed");
    }

    function _receipt(uint256 releaseId, uint256 nonce)
        internal
        view
        returns (DeviceReceiptVerifierV2.DeviceReceipt memory)
    {
        return DeviceReceiptVerifierV2.DeviceReceipt({
            deviceIdHash: DEVICE_ID,
            releaseId: releaseId,
            rolloutId: ROLLOUT_ID,
            epoch: 1,
            cohortId: COHORT_ID,
            deadline: uint64(block.timestamp + 100),
            targetVersion: 2,
            outcome: DeviceReceiptVerifierV2.Outcome.SUCCESS,
            observedAt: uint64(block.timestamp),
            nonce: nonce
        });
    }

    function _sign(DeviceReceiptVerifierV2.DeviceReceipt memory receipt) internal returns (bytes memory) {
        return _signWithKey(receipt, DEVICE_PRIVATE_KEY);
    }

    function _signWithKey(DeviceReceiptVerifierV2.DeviceReceipt memory receipt, uint256 privateKey)
        internal
        returns (bytes memory)
    {
        bytes32 digest = verifier.receiptDigest(receipt);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(privateKey, digest);
        return abi.encodePacked(r, s, v);
    }
}

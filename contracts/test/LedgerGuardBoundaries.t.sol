// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {KeyManager} from "../src/KeyManager.sol";
import {FirmwareRegistry} from "../src/FirmwareRegistry.sol";
import {RolloutCoordinatorV2} from "../src/RolloutCoordinatorV2.sol";
import {DeviceAttestationV2} from "../src/DeviceAttestationV2.sol";
import {DeviceIdentityRegistryV2} from "../src/DeviceIdentityRegistryV2.sol";
import {DeviceReceiptVerifierV2} from "../src/DeviceReceiptVerifierV2.sol";
import {DeviceAttestation} from "../src/DeviceAttestation.sol";
import {NaiveDeviceReporting} from "../src/NaiveDeviceReporting.sol";
import {RolloutCoordinator} from "../src/RolloutCoordinator.sol";

interface VmBoundary {
    function prank(address) external;
    function expectRevert(bytes calldata) external;
    function warp(uint256) external;
    function addr(uint256) external returns (address);
    function sign(uint256, bytes32) external returns (uint8, bytes32, bytes32);
}

contract LedgerGuardBoundariesTest {
    VmBoundary constant vm = VmBoundary(address(uint160(uint256(keccak256("hevm cheat code")))));
    address constant VENDOR = address(11);
    address constant SECURITY = address(12);
    address constant REGULATOR = address(13);
    address constant OPERATOR = address(14);
    address constant WITNESS = address(15);
    bytes32 constant DEVICE = bytes32("device");
    bytes32 constant ROOT = bytes32(uint256(1));
    KeyManager km;
    FirmwareRegistry registry;
    RolloutCoordinatorV2 rollout;
    DeviceAttestationV2 attestation;
    DeviceIdentityRegistryV2 identities;
    DeviceReceiptVerifierV2 verifier;

    function setUp() public {
        vm.warp(1000);
        km = new KeyManager();
        registry = new FirmwareRegistry(address(km));
        rollout = new RolloutCoordinatorV2(address(km), address(registry));
        attestation = new DeviceAttestationV2(address(km));
        identities = new DeviceIdentityRegistryV2(address(km));
        verifier = new DeviceReceiptVerifierV2(address(identities));
        km.setSigner(VENDOR, KeyManager.Role.VENDOR, true);
        km.setSigner(SECURITY, KeyManager.Role.SECURITY, true);
        km.setSigner(REGULATOR, KeyManager.Role.REGULATOR, true);
        km.setSigner(OPERATOR, KeyManager.Role.OPERATOR, true);
        km.setSigner(WITNESS, KeyManager.Role.AUDITOR, true);
        km.setPolicy(DEVICE, 12, 2);
    }

    function deny(address actor, string memory reason) internal {
        vm.expectRevert(bytes(reason));
        vm.prank(actor);
    }

    function release(uint64 version, uint64 expiry) internal returns (uint256 id) {
        vm.prank(VENDOR);
        id = registry.registerRelease(DEVICE, version, "cid", ROOT, 1, ROOT, ROOT, 0, expiry);
        vm.prank(SECURITY); registry.approveRelease(id);
        vm.prank(REGULATOR); registry.approveRelease(id);
    }

    function cohort(uint64 deadline) internal returns (bytes32 key) {
        vm.prank(OPERATOR);
        key = attestation.registerCohort(1, ROOT, 1, ROOT, ROOT, 10, deadline);
    }

    function propose(bytes32 key) internal {
        vm.prank(OPERATOR);
        attestation.proposeSummary(key, ROOT, ROOT, 10, 10, 0, 0, 0, 0);
    }

    function testConstructorZeroAddressesRejected() public {
        vm.expectRevert(bytes("FirmwareRegistry: zero KeyManager")); new FirmwareRegistry(address(0));
        vm.expectRevert(bytes("RolloutCoordinatorV2: zero KeyManager")); new RolloutCoordinatorV2(address(0), address(registry));
        vm.expectRevert(bytes("RolloutCoordinatorV2: zero registry")); new RolloutCoordinatorV2(address(km), address(0));
        vm.expectRevert(bytes("DeviceAttestationV2: zero KeyManager")); new DeviceAttestationV2(address(0));
        vm.expectRevert(bytes("DeviceIdentityRegistryV2: zero KeyManager")); new DeviceIdentityRegistryV2(address(0));
        vm.expectRevert(bytes("DeviceReceiptVerifierV2: zero registry")); new DeviceReceiptVerifierV2(address(0));
        vm.expectRevert(bytes("DeviceAttestation: zero KeyManager")); new DeviceAttestation(address(0));
        vm.expectRevert(bytes("NaiveDeviceReporting: zero KeyManager")); new NaiveDeviceReporting(address(0));
    }

    function testOwnershipPolicyAndSignerBoundaries() public {
        deny(VENDOR, "KeyManager: not owner"); km.setSigner(VENDOR, KeyManager.Role.VENDOR, true);
        vm.expectRevert(bytes("KeyManager: zero signer")); km.setSigner(address(0), KeyManager.Role.VENDOR, true);
        vm.expectRevert(bytes("KeyManager: invalid role")); km.setSigner(VENDOR, KeyManager.Role.NONE, true);
        vm.expectRevert(bytes("KeyManager: unknown signer")); km.revokeSigner(address(99));
        vm.expectRevert(bytes("KeyManager: zero owner")); km.transferOwnership(address(0));
        vm.expectRevert(bytes("KeyManager: empty deviceType")); km.setPolicy(0, 12, 2);
        vm.expectRevert(bytes("KeyManager: empty mask")); km.setPolicy(DEVICE, 0, 1);
        vm.expectRevert(bytes("KeyManager: bad threshold")); km.setPolicy(DEVICE, 12, 0);
        vm.expectRevert(bytes("KeyManager: bad threshold")); km.setPolicy(DEVICE, 12, 3);
        require(km.isActive(VENDOR) && km.roleOf(VENDOR) == KeyManager.Role.VENDOR);
        km.transferOwnership(VENDOR);
        require(km.owner() == VENDOR);
        vm.prank(VENDOR); km.revokeSigner(OPERATOR);
        require(!km.isActive(OPERATOR));
    }

    function testDeviceIdentityAuthorizationAndInputGuards() public {
        deny(VENDOR, "DeviceIdentityRegistryV2: not governance owner"); identities.setDeviceIdentity(DEVICE, VENDOR, true);
        vm.expectRevert(bytes("DeviceIdentityRegistryV2: empty device id")); identities.setDeviceIdentity(0, VENDOR, true);
        vm.expectRevert(bytes("DeviceIdentityRegistryV2: zero signer")); identities.setDeviceIdentity(DEVICE, address(0), true);
        vm.expectRevert(bytes("DeviceIdentityRegistryV2: unknown device")); identities.revokeDeviceIdentity(DEVICE);
        identities.setDeviceIdentity(DEVICE, VENDOR, true);
        require(!identities.isActiveSigner(DEVICE, SECURITY));
        identities.revokeDeviceIdentity(DEVICE);
        require(!identities.isActiveSigner(DEVICE, VENDOR));
    }

    function testRegistrationRoleAndMetadataGuards() public {
        deny(SECURITY, "FirmwareRegistry: wrong role"); registry.registerRelease(DEVICE, 1, "cid", ROOT, 1, ROOT, ROOT, 0, 0);
        deny(VENDOR, "FirmwareRegistry: empty deviceType"); registry.registerRelease(0, 1, "cid", ROOT, 1, ROOT, ROOT, 0, 0);
        deny(VENDOR, "FirmwareRegistry: empty CID"); registry.registerRelease(DEVICE, 1, "", ROOT, 1, ROOT, ROOT, 0, 0);
        deny(VENDOR, "FirmwareRegistry: expiresAt in past"); registry.registerRelease(DEVICE, 1, "cid", ROOT, 1, ROOT, ROOT, 0, 1000);
        deny(VENDOR, "FirmwareRegistry: missing policy"); registry.registerRelease(ROOT, 1, "cid", ROOT, 1, ROOT, ROOT, 0, 0);
    }

    function testExpiryBoundaryAndDeprecation() public {
        require(registry.latestApproved(DEVICE) == 0);
        uint256 id = release(1, 1010);
        vm.warp(1010); require(registry.latestApproved(DEVICE) == id);
        vm.warp(1011); require(registry.latestApproved(DEVICE) == 0);
        uint256 newer = release(2, 0);
        release(1, 0); require(registry.latestApproved(DEVICE) == newer);
        deny(VENDOR, "FirmwareRegistry: wrong role"); registry.deprecateRelease(newer);
        deny(SECURITY, "FirmwareRegistry: unknown release"); registry.deprecateRelease(999);
        vm.prank(SECURITY); registry.deprecateRelease(newer);
        require(!registry.isApproved(newer) && registry.latestApproved(DEVICE) == 0);
        (bytes32 d, uint64 version, string memory cid, bytes32 hash, uint32 size,,) = registry.getReleaseContent(newer);
        require(d == DEVICE && version == 2 && bytes(cid).length == 3 && hash == ROOT && size == 1);
    }

    function testApprovalCountsRolesRatherThanSigners() public {
        vm.prank(VENDOR); uint256 id = registry.registerRelease(DEVICE, 1, "cid", ROOT, 1, ROOT, ROOT, 0, 0);
        deny(VENDOR, "FirmwareRegistry: role not eligible"); registry.approveRelease(id);
        vm.prank(SECURITY); registry.approveRelease(id);
        deny(SECURITY, "FirmwareRegistry: already approved by signer"); registry.approveRelease(id);
        km.setSigner(address(99), KeyManager.Role.SECURITY, true);
        vm.prank(address(99)); registry.approveRelease(id);
        require(!registry.isApproved(id));
        vm.prank(REGULATOR); registry.approveRelease(id);
        require(registry.isApproved(id));
        deny(REGULATOR, "FirmwareRegistry: not proposed"); registry.approveRelease(id);
    }

    function testKillSwitchAuthorizationAndReleaseRestoration() public {
        uint256 id = release(1, 0);
        deny(VENDOR, "FirmwareRegistry: role denied"); registry.setKillSwitch(DEVICE, true);
        km.revokeSigner(SECURITY);
        deny(SECURITY, "FirmwareRegistry: signer inactive"); registry.setKillSwitch(DEVICE, true);
        vm.prank(REGULATOR); registry.setKillSwitch(DEVICE, true);
        require(registry.latestApproved(DEVICE) == 0);
        vm.prank(REGULATOR); registry.setKillSwitch(DEVICE, false);
        require(registry.latestApproved(DEVICE) == id);
    }

    function testCohortRegistrationBoundaries() public {
        deny(VENDOR, "DeviceAttestationV2: wrong role"); attestation.registerCohort(1, ROOT, 1, ROOT, ROOT, 10, 1000);
        deny(OPERATOR, "DeviceAttestationV2: zero release"); attestation.registerCohort(0, ROOT, 1, ROOT, ROOT, 10, 1000);
        deny(OPERATOR, "DeviceAttestationV2: empty rollout"); attestation.registerCohort(1, 0, 1, ROOT, ROOT, 10, 1000);
        deny(OPERATOR, "DeviceAttestationV2: empty cohort"); attestation.registerCohort(1, ROOT, 1, 0, ROOT, 10, 1000);
        deny(OPERATOR, "DeviceAttestationV2: empty cohort commitment"); attestation.registerCohort(1, ROOT, 1, ROOT, 0, 10, 1000);
        deny(OPERATOR, "DeviceAttestationV2: empty expected cohort"); attestation.registerCohort(1, ROOT, 1, ROOT, ROOT, 0, 1000);
        deny(OPERATOR, "DeviceAttestationV2: deadline passed"); attestation.registerCohort(1, ROOT, 1, ROOT, ROOT, 10, 999);
        bytes32 key = cohort(1000);
        require(attestation.getCohort(key).expectedCount == 10);
        deny(OPERATOR, "DeviceAttestationV2: cohort already registered"); attestation.registerCohort(1, ROOT, 1, ROOT, ROOT, 10, 1000);
        km.revokeSigner(OPERATOR);
        deny(OPERATOR, "DeviceAttestationV2: signer inactive"); attestation.registerCohort(2, ROOT, 1, ROOT, ROOT, 10, 1000);
    }

    function testSummaryCounterRootAndDeadlineGuards() public {
        deny(OPERATOR, "DeviceAttestationV2: unknown cohort"); attestation.proposeSummary(ROOT, ROOT, ROOT, 10, 10, 0, 0, 0, 0);
        bytes32 key = cohort(1010);
        deny(OPERATOR, "DeviceAttestationV2: received count mismatch"); attestation.proposeSummary(key, ROOT, ROOT, 10, 9, 0, 0, 0, 0);
        deny(OPERATOR, "DeviceAttestationV2: empty receipt root"); attestation.proposeSummary(key, 0, ROOT, 10, 10, 0, 0, 0, 0);
        deny(OPERATOR, "DeviceAttestationV2: missing before deadline"); attestation.proposeSummary(key, ROOT, ROOT, 9, 9, 0, 0, 0, 1);
        vm.warp(1010);
        vm.prank(OPERATOR); attestation.proposeSummary(key, 0, ROOT, 0, 0, 0, 0, 0, 10);
        vm.prank(WITNESS); attestation.confirmSummary(key, 0, ROOT, 0, 0, 0, 0, 0, 10);
        require(attestation.successRateBps(key) == 0);
    }

    function testSummaryReadAndConfirmationStates() public {
        vm.expectRevert(bytes("DeviceAttestationV2: missing summary")); attestation.summaryHash(ROOT);
        vm.expectRevert(bytes("DeviceAttestationV2: not finalized")); attestation.successRateBps(ROOT);
        deny(WITNESS, "DeviceAttestationV2: unknown cohort"); attestation.confirmSummary(ROOT, ROOT, ROOT, 10, 10, 0, 0, 0, 0);
        bytes32 key = cohort(1000);
        deny(WITNESS, "DeviceAttestationV2: summary not proposed"); attestation.confirmSummary(key, ROOT, ROOT, 10, 10, 0, 0, 0, 0);
        propose(key);
        require(attestation.summaryHash(key) != 0);
        vm.expectRevert(bytes("DeviceAttestationV2: not finalized")); attestation.successRateBps(key);
        deny(WITNESS, "DeviceAttestationV2: witness mismatch"); attestation.confirmSummary(key, bytes32(uint256(2)), ROOT, 10, 10, 0, 0, 0, 0);
        vm.prank(WITNESS); attestation.confirmSummary(key, ROOT, ROOT, 10, 10, 0, 0, 0, 0);
        require(attestation.successRateBps(key) == 10000);
        deny(WITNESS, "DeviceAttestationV2: summary not proposed"); attestation.confirmSummary(key, ROOT, ROOT, 10, 10, 0, 0, 0, 0);
    }

    function testAggregatorCannotConfirmAfterRoleReplacement() public {
        bytes32 key = cohort(1000); propose(key);
        km.setSigner(OPERATOR, KeyManager.Role.AUDITOR, true);
        deny(OPERATOR, "DeviceAttestationV2: witness not independent"); attestation.confirmSummary(key, ROOT, ROOT, 10, 10, 0, 0, 0, 0);
    }

    function testRolloutThresholdEligibilityAndAuthorization() public {
        uint256 id = release(1, 0);
        deny(VENDOR, "RolloutCoordinatorV2: wrong role"); rollout.startRollout(id, DEVICE, 9500);
        deny(OPERATOR, "RolloutCoordinatorV2: bad threshold"); rollout.startRollout(id, DEVICE, 0);
        deny(OPERATOR, "RolloutCoordinatorV2: bad threshold"); rollout.startRollout(id, DEVICE, 10001);
        deny(OPERATOR, "RolloutCoordinatorV2: release not approved"); rollout.startRollout(99, DEVICE, 9500);
        deny(OPERATOR, "RolloutCoordinatorV2: release not eligible"); rollout.startRollout(id, ROOT, 9500);
        km.revokeSigner(OPERATOR);
        deny(OPERATOR, "RolloutCoordinatorV2: signer inactive"); rollout.startRollout(id, DEVICE, 9500);
    }

    function testRolloutEmptyCountersNonceAndCompletedPhase() public {
        uint256 id = release(1, 0);
        vm.prank(OPERATOR); rollout.startRollout(id, DEVICE, 9500);
        deny(OPERATOR, "RolloutCoordinatorV2: stale transition nonce"); rollout.advanceRollout(id, RolloutCoordinatorV2.Phase.CANARY, 0, 10, 0, 0, 0, 0);
        deny(OPERATOR, "RolloutCoordinatorV2: empty outcome set"); rollout.advanceRollout(id, RolloutCoordinatorV2.Phase.CANARY, 1, 0, 0, 0, 0, 0);
        vm.prank(OPERATOR); rollout.advanceRollout(id, RolloutCoordinatorV2.Phase.CANARY, 1, 10, 0, 0, 0, 0);
        vm.prank(OPERATOR); rollout.advanceRollout(id, RolloutCoordinatorV2.Phase.BATCH, 2, 10, 0, 0, 0, 0);
        vm.prank(OPERATOR); rollout.advanceRollout(id, RolloutCoordinatorV2.Phase.GLOBAL, 3, 10, 0, 0, 0, 0);
        require(rollout.getRollout(id).phase == RolloutCoordinatorV2.Phase.COMPLETED);
        deny(OPERATOR, "RolloutCoordinatorV2: terminal phase"); rollout.advanceRollout(id, RolloutCoordinatorV2.Phase.COMPLETED, 4, 10, 0, 0, 0, 0);
    }

    function testHaltRoleStateAndNonceGuards() public {
        deny(VENDOR, "RolloutCoordinatorV2: role denied"); rollout.haltRollout(1, RolloutCoordinatorV2.Phase.NONE, 0);
        deny(OPERATOR, "RolloutCoordinatorV2: not active"); rollout.haltRollout(1, RolloutCoordinatorV2.Phase.NONE, 0);
        uint256 id = release(1, 0);
        vm.prank(OPERATOR); rollout.startRollout(id, DEVICE, 9500);
        deny(SECURITY, "RolloutCoordinatorV2: stale phase"); rollout.haltRollout(id, RolloutCoordinatorV2.Phase.BATCH, 1);
        deny(SECURITY, "RolloutCoordinatorV2: stale transition nonce"); rollout.haltRollout(id, RolloutCoordinatorV2.Phase.CANARY, 0);
        vm.prank(SECURITY); rollout.haltRollout(id, RolloutCoordinatorV2.Phase.CANARY, 1);
        deny(OPERATOR, "RolloutCoordinatorV2: not active"); rollout.haltRollout(id, RolloutCoordinatorV2.Phase.HALTED, 2);
        km.revokeSigner(SECURITY);
        deny(SECURITY, "RolloutCoordinatorV2: signer inactive"); rollout.haltRollout(id, RolloutCoordinatorV2.Phase.HALTED, 2);
    }

    function receipt() internal pure returns (DeviceReceiptVerifierV2.DeviceReceipt memory) {
        return DeviceReceiptVerifierV2.DeviceReceipt(DEVICE, 1, ROOT, 1, ROOT, 1000, 2, DeviceReceiptVerifierV2.Outcome.SUCCESS, 1000, 1);
    }

    function testReceiptMandatoryFieldsAndDeadline() public view {
        for (uint256 i; i < 8; i++) {
            DeviceReceiptVerifierV2.DeviceReceipt memory r = receipt();
            if (i == 0) r.deviceIdHash = 0;
            else if (i == 1) r.releaseId = 0;
            else if (i == 2) r.rolloutId = 0;
            else if (i == 3) r.epoch = 0;
            else if (i == 4) r.cohortId = 0;
            else if (i == 5) r.deadline = 0;
            else if (i == 6) r.outcome = DeviceReceiptVerifierV2.Outcome.NONE;
            else r.observedAt = 1001;
            require(!verifier.verifyReceipt(r, new bytes(65)));
        }
    }

    function testMalformedSignaturesAndNormalizedV() public {
        DeviceReceiptVerifierV2.DeviceReceipt memory r = receipt();
        address signer = vm.addr(123);
        identities.setDeviceIdentity(DEVICE, signer, true);
        (uint8 v, bytes32 rs, bytes32 ss) = vm.sign(123, verifier.receiptDigest(r));
        require(verifier.verifyReceipt(r, abi.encodePacked(rs, ss, v)));
        require(verifier.verifyReceipt(r, abi.encodePacked(rs, ss, uint8(v - 27))));
        require(verifier.recoverSigner(r, new bytes(64)) == address(0));
        require(verifier.recoverSigner(r, abi.encodePacked(rs, ss, uint8(29))) == address(0));
        require(verifier.recoverSigner(r, abi.encodePacked(rs, bytes32(type(uint256).max), v)) == address(0));
        require(!verifier.verifyReceipt(r, abi.encodePacked(bytes32(0), bytes32(0), uint8(27))));
    }

    function testLegacyAdvanceCompletionAndHaltGuards() public {
        RolloutCoordinator legacy = new RolloutCoordinator(address(km), address(registry));
        uint256 id = release(1, 0);
        deny(OPERATOR, "RolloutCoordinator: not started"); legacy.advance(id);
        vm.prank(OPERATOR); legacy.startRollout(id, 10, 50);
        vm.prank(OPERATOR); legacy.advance(id);
        vm.prank(OPERATOR); legacy.advance(id);
        vm.prank(OPERATOR); legacy.advance(id);
        (,,,RolloutCoordinator.Phase phase,,) = legacy.getRollout(id);
        require(phase == RolloutCoordinator.Phase.COMPLETED);
        (bool allowed,,) = legacy.canAdvance(id, 100, 0, 0);
        require(!allowed);
        deny(OPERATOR, "RolloutCoordinator: completed"); legacy.advance(id);
        uint256 second = release(2, 0);
        deny(SECURITY, "RolloutCoordinator: not started"); legacy.halt(second);
        vm.prank(OPERATOR); legacy.startRollout(second, 10, 50);
        vm.prank(SECURITY); legacy.halt(second);
        deny(OPERATOR, "RolloutCoordinator: halted"); legacy.advance(second);
    }

    function testLegacyRolloutConfigurationAndRoles() public {
        RolloutCoordinator legacy = new RolloutCoordinator(address(km), address(registry));
        uint256 id = release(1, 0);
        deny(OPERATOR, "RolloutCoordinator: bad canary"); legacy.startRollout(id, 0, 50);
        deny(OPERATOR, "RolloutCoordinator: bad batch"); legacy.startRollout(id, 50, 10);
        deny(VENDOR, "RolloutCoordinator: role denied"); legacy.halt(id);
        km.revokeSigner(SECURITY);
        deny(SECURITY, "RolloutCoordinator: signer inactive"); legacy.halt(id);
        vm.expectRevert(bytes("RolloutCoordinator: zero KeyManager")); new RolloutCoordinator(address(0), address(registry));
        vm.expectRevert(bytes("RolloutCoordinator: zero Registry")); new RolloutCoordinator(address(km), address(0));
    }

    function testNaiveComparisonReadbackAndInputGuards() public {
        NaiveDeviceReporting naive = new NaiveDeviceReporting(address(km));
        deny(OPERATOR, "NaiveDeviceReporting: empty device"); naive.submitDeviceOutcome(1, 1, 0, 1, ROOT);
        deny(OPERATOR, "NaiveDeviceReporting: empty receipt"); naive.submitDeviceOutcome(1, 1, DEVICE, 1, 0);
        deny(VENDOR, "NaiveDeviceReporting: not operator"); naive.submitDeviceOutcome(1, 1, DEVICE, 1, ROOT);
        vm.prank(OPERATOR); naive.submitDeviceOutcome(1, 1, DEVICE, 1, ROOT);
        require(naive.outcomeCount() == 1);
        deny(OPERATOR, "NaiveDeviceReporting: duplicate receipt"); naive.submitDeviceOutcome(1, 1, DEVICE, 1, ROOT);
        km.revokeSigner(OPERATOR);
        deny(OPERATOR, "NaiveDeviceReporting: signer inactive"); naive.submitDeviceOutcome(1, 1, DEVICE, 1, ROOT);
    }
}

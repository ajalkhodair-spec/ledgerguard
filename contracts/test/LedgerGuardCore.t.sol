// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {KeyManager} from "../src/KeyManager.sol";
import {FirmwareRegistry} from "../src/FirmwareRegistry.sol";
import {RolloutCoordinator} from "../src/RolloutCoordinator.sol";
import {DeviceAttestation} from "../src/DeviceAttestation.sol";
import {NaiveDeviceReporting} from "../src/NaiveDeviceReporting.sol";

contract Actor {
    function registerRelease(FirmwareRegistry fr, bytes32 device, uint64 version, bytes32 h) external returns (uint256) {
        return fr.registerRelease(device, version, "bafy", h, 1, h, h, 0, 0);
    }

    function approve(FirmwareRegistry fr, uint256 releaseId) external {
        fr.approveRelease(releaseId);
    }

    function start(RolloutCoordinator rc, uint256 releaseId) external {
        rc.startRollout(releaseId, 10, 50);
    }

    function advanceWithMetrics(RolloutCoordinator rc, uint256 releaseId, uint32 success, uint32 fail, uint32 rollback) external {
        rc.advanceWithMetrics(releaseId, success, fail, rollback);
    }
}

contract LedgerGuardCoreTest {
    KeyManager km;
    FirmwareRegistry fr;
    RolloutCoordinator rc;
    DeviceAttestation da;
    NaiveDeviceReporting naiveReporter;
    Actor vendor;
    Actor security;
    Actor regulator;
    Actor operator;
    Actor unauthorized;

    bytes32 constant DEVICE = bytes32("M4");
    bytes32 constant HASH = bytes32(uint256(1));

    function setUp() public {
        km = new KeyManager();
        fr = new FirmwareRegistry(address(km));
        rc = new RolloutCoordinator(address(km), address(fr));
        da = new DeviceAttestation(address(km));
        naiveReporter = new NaiveDeviceReporting(address(km));
        vendor = new Actor();
        security = new Actor();
        regulator = new Actor();
        operator = new Actor();
        unauthorized = new Actor();

        km.setSigner(address(vendor), KeyManager.Role.VENDOR, true);
        km.setSigner(address(security), KeyManager.Role.SECURITY, true);
        km.setSigner(address(regulator), KeyManager.Role.REGULATOR, true);
        km.setSigner(address(operator), KeyManager.Role.OPERATOR, true);
        km.setPolicy(
            DEVICE,
            km.roleBit(KeyManager.Role.SECURITY) | km.roleBit(KeyManager.Role.REGULATOR),
            2
        );
    }

    function _approvedRelease() internal returns (uint256 releaseId) {
        releaseId = vendor.registerRelease(fr, DEVICE, 1, HASH);
        security.approve(fr, releaseId);
        regulator.approve(fr, releaseId);
        require(fr.isApproved(releaseId), "release should be approved");
    }

    function testApprovalThresholdRequiredBeforeFinalApproval() public {
        setUp();
        uint256 releaseId = vendor.registerRelease(fr, DEVICE, 1, HASH);
        security.approve(fr, releaseId);
        require(!fr.isApproved(releaseId), "approved before threshold");
        regulator.approve(fr, releaseId);
        require(fr.isApproved(releaseId), "threshold approval failed");
    }

    function testRevokedSignerCannotApprove() public {
        setUp();
        uint256 releaseId = vendor.registerRelease(fr, DEVICE, 1, HASH);
        km.revokeSigner(address(security));
        bool failed;
        try security.approve(fr, releaseId) {
            failed = false;
        } catch {
            failed = true;
        }
        require(failed, "revoked signer approved");
    }

    function testGovernanceSignerRevocationAndReplacementLifecycle() public {
        setUp();
        uint256 firstRelease = vendor.registerRelease(fr, DEVICE, 1, HASH);
        security.approve(fr, firstRelease);

        km.revokeSigner(address(security));
        uint256 secondRelease = vendor.registerRelease(fr, DEVICE, 2, bytes32(uint256(2)));
        bool oldSignerRejected;
        try security.approve(fr, secondRelease) {
            oldSignerRejected = false;
        } catch {
            oldSignerRejected = true;
        }
        require(oldSignerRejected, "revoked signer approved a new release");

        Actor replacementSecurity = new Actor();
        km.setSigner(address(replacementSecurity), KeyManager.Role.SECURITY, true);
        replacementSecurity.approve(fr, secondRelease);
        regulator.approve(fr, secondRelease);
        require(fr.isApproved(secondRelease), "replacement signer approval not accepted");

        uint256 thirdRelease = vendor.registerRelease(fr, DEVICE, 3, bytes32(uint256(3)));
        bool staleOldSignerRejected;
        try security.approve(fr, thirdRelease) {
            staleOldSignerRejected = false;
        } catch {
            staleOldSignerRejected = true;
        }
        require(staleOldSignerRejected, "stale approval from revoked signer accepted");
        replacementSecurity.approve(fr, thirdRelease);
        regulator.approve(fr, thirdRelease);
        require(fr.isApproved(thirdRelease), "replacement signer did not remain active");
    }

    function testRevokedVendorCannotRegister() public {
        setUp();
        km.revokeSigner(address(vendor));
        bool failed;
        try vendor.registerRelease(fr, DEVICE, 1, HASH) {
            failed = false;
        } catch {
            failed = true;
        }
        require(failed, "revoked vendor registered release");
    }

    function testDuplicateApprovalDoesNotCountTwice() public {
        setUp();
        uint256 releaseId = vendor.registerRelease(fr, DEVICE, 1, HASH);
        security.approve(fr, releaseId);
        bool failed;
        try security.approve(fr, releaseId) {
            failed = false;
        } catch {
            failed = true;
        }
        require(failed, "duplicate approval accepted");
        require(!fr.isApproved(releaseId), "duplicate approval counted toward threshold");
    }

    function testReleaseCannotRollOutBeforeApproval() public {
        setUp();
        uint256 releaseId = vendor.registerRelease(fr, DEVICE, 1, HASH);
        bool failed;
        try operator.start(rc, releaseId) {
            failed = false;
        } catch {
            failed = true;
        }
        require(failed, "unapproved release rollout started");
    }

    function testUnauthorizedOperatorCannotStartRollout() public {
        setUp();
        uint256 releaseId = _approvedRelease();
        bool failed;
        try unauthorized.start(rc, releaseId) {
            failed = false;
        } catch {
            failed = true;
        }
        require(failed, "unauthorized operator started rollout");
    }

    function testRolloutCannotAdvanceBelowSuccessThreshold() public {
        setUp();
        uint256 releaseId = _approvedRelease();
        operator.start(rc, releaseId);
        bool failed;
        try operator.advanceWithMetrics(rc, releaseId, 90, 10, 0) {
            failed = false;
        } catch {
            failed = true;
        }
        require(failed, "low-success rollout advanced");
    }

    function testRolloutCanAdvanceWhenThresholdSatisfied() public {
        setUp();
        uint256 releaseId = _approvedRelease();
        operator.start(rc, releaseId);
        operator.advanceWithMetrics(rc, releaseId, 98, 1, 1);
        (,,, RolloutCoordinator.Phase phase,,) = rc.getRollout(releaseId);
        require(phase == RolloutCoordinator.Phase.BATCH, "rollout did not advance");
    }

    function testKillSwitchDisablesLatestApproved() public {
        setUp();
        uint256 releaseId = _approvedRelease();
        require(fr.latestApproved(DEVICE) == releaseId, "latestApproved mismatch");
        km.setSigner(address(this), KeyManager.Role.SECURITY, true);
        fr.setKillSwitch(DEVICE, true);
        require(fr.latestApproved(DEVICE) == 0, "kill switch did not disable latest");
    }

    function testOutcomeRootAppendOnlyPerEpoch() public {
        setUp();
        km.setSigner(address(this), KeyManager.Role.OPERATOR, true);
        da.submitOutcomeRoot(1, 1, HASH, 1, 0, 0);
        bool failed;
        try da.submitOutcomeRoot(1, 1, HASH, 1, 0, 0) {
            failed = false;
        } catch {
            failed = true;
        }
        require(failed, "duplicate outcome root accepted");
    }

    function testNaiveReportingRejectsDuplicateReceipt() public {
        setUp();
        km.setSigner(address(this), KeyManager.Role.OPERATOR, true);
        naiveReporter.submitDeviceOutcome(1, 1, bytes32("device-1"), 1, HASH);
        bool failed;
        try naiveReporter.submitDeviceOutcome(1, 1, bytes32("device-1"), 1, HASH) {
            failed = false;
        } catch {
            failed = true;
        }
        require(failed, "duplicate receipt accepted");
    }

    function testValidMerkleProofPasses() public pure {
        bytes32 leaf = keccak256(abi.encodePacked("device-1", uint8(1)));
        bytes32 sibling = keccak256(abi.encodePacked("device-2", uint8(2)));
        bytes32 root = _hashPair(leaf, sibling);
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = sibling;
        require(_verify(proof, root, leaf), "valid Merkle proof failed");
    }

    function testTamperedMerkleProofFails() public pure {
        bytes32 leaf = keccak256(abi.encodePacked("device-1", uint8(1)));
        bytes32 sibling = keccak256(abi.encodePacked("device-2", uint8(2)));
        bytes32 root = _hashPair(leaf, sibling);
        bytes32[] memory proof = new bytes32[](1);
        proof[0] = keccak256(abi.encodePacked("tampered"));
        require(!_verify(proof, root, leaf), "tampered Merkle proof passed");
    }

    function _verify(bytes32[] memory proof, bytes32 root, bytes32 leaf) internal pure returns (bool) {
        bytes32 computed = leaf;
        for (uint256 i = 0; i < proof.length; i++) {
            computed = _hashPair(computed, proof[i]);
        }
        return computed == root;
    }

    function _hashPair(bytes32 a, bytes32 b) internal pure returns (bytes32) {
        return a < b ? keccak256(abi.encodePacked(a, b)) : keccak256(abi.encodePacked(b, a));
    }
}

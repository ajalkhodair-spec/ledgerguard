// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {KeyManager} from "../src/KeyManager.sol";
import {FirmwareRegistry} from "../src/FirmwareRegistry.sol";
import {RolloutCoordinatorV2} from "../src/RolloutCoordinatorV2.sol";

contract ConcurrencyActorV2 {
    function register(FirmwareRegistry registry, bytes32 deviceType) external returns (uint256) {
        return registry.registerRelease(deviceType, 2, "bafy-v2", bytes32(uint256(1)), 1, bytes32(uint256(2)), bytes32(uint256(3)), 0, 0);
    }
    function approve(FirmwareRegistry registry, uint256 releaseId) external { registry.approveRelease(releaseId); }
    function start(RolloutCoordinatorV2 coordinator, uint256 releaseId, bytes32 deviceType) external {
        coordinator.startRollout(releaseId, deviceType, 9500);
    }
    function advance(RolloutCoordinatorV2 coordinator, uint256 releaseId, RolloutCoordinatorV2.Phase phase, uint64 nonce) external {
        coordinator.advanceRollout(releaseId, phase, nonce, 98, 1, 1, 0, 0);
    }
    function advanceWithCounts(
        RolloutCoordinatorV2 coordinator,
        uint256 releaseId,
        RolloutCoordinatorV2.Phase phase,
        uint64 nonce,
        uint32 success,
        uint32 rollback,
        uint32 fail,
        uint32 rejected,
        uint32 missing
    ) external {
        coordinator.advanceRollout(releaseId, phase, nonce, success, rollback, fail, rejected, missing);
    }
    function halt(RolloutCoordinatorV2 coordinator, uint256 releaseId, RolloutCoordinatorV2.Phase phase, uint64 nonce) external {
        coordinator.haltRollout(releaseId, phase, nonce);
    }
    function enableKillSwitch(FirmwareRegistry registry, bytes32 deviceType) external {
        registry.setKillSwitch(deviceType, true);
    }
}

contract LedgerGuardV2ConcurrencyTest {
    bytes32 private constant DEVICE = bytes32("M4");
    KeyManager private keyManager;
    FirmwareRegistry private registry;
    RolloutCoordinatorV2 private coordinator;
    ConcurrencyActorV2 private vendor;
    ConcurrencyActorV2 private security;
    ConcurrencyActorV2 private regulator;
    ConcurrencyActorV2 private operator;
    ConcurrencyActorV2 private haltActor;

    function setUp() public {
        keyManager = new KeyManager();
        registry = new FirmwareRegistry(address(keyManager));
        coordinator = new RolloutCoordinatorV2(address(keyManager), address(registry));
        vendor = new ConcurrencyActorV2();
        security = new ConcurrencyActorV2();
        regulator = new ConcurrencyActorV2();
        operator = new ConcurrencyActorV2();
        haltActor = new ConcurrencyActorV2();
        keyManager.setSigner(address(vendor), KeyManager.Role.VENDOR, true);
        keyManager.setSigner(address(security), KeyManager.Role.SECURITY, true);
        keyManager.setSigner(address(regulator), KeyManager.Role.REGULATOR, true);
        keyManager.setSigner(address(operator), KeyManager.Role.OPERATOR, true);
        keyManager.setSigner(address(haltActor), KeyManager.Role.SECURITY, true);
        keyManager.setPolicy(DEVICE, keyManager.roleBit(KeyManager.Role.SECURITY) | keyManager.roleBit(KeyManager.Role.REGULATOR), 2);
    }

    function approvedRelease() internal returns (uint256 releaseId) {
        releaseId = vendor.register(registry, DEVICE);
        security.approve(registry, releaseId);
        regulator.approve(registry, releaseId);
    }

    function testTwoStartTransactionsYieldOneTransitionAndOneRevert() public {
        setUp();
        uint256 releaseId = approvedRelease();
        operator.start(coordinator, releaseId, DEVICE);
        bool failed;
        try operator.start(coordinator, releaseId, DEVICE) { failed = false; } catch { failed = true; }
        require(failed, "second start transaction accepted");
    }

    function testTwoStaleAdvanceTransactionsYieldOneTransitionAndOneRevert() public {
        setUp();
        uint256 releaseId = approvedRelease();
        operator.start(coordinator, releaseId, DEVICE);
        operator.advance(coordinator, releaseId, RolloutCoordinatorV2.Phase.CANARY, 1);
        bool failed;
        try operator.advance(coordinator, releaseId, RolloutCoordinatorV2.Phase.CANARY, 1) { failed = false; } catch { failed = true; }
        require(failed, "stale phase transition accepted");
        require(coordinator.getRollout(releaseId).phase == RolloutCoordinatorV2.Phase.BATCH, "unexpected final phase");
    }

    function testHaltWinsAgainstStaleAdvance() public {
        setUp();
        uint256 releaseId = approvedRelease();
        operator.start(coordinator, releaseId, DEVICE);
        haltActor.halt(coordinator, releaseId, RolloutCoordinatorV2.Phase.CANARY, 1);
        bool failed;
        try operator.advance(coordinator, releaseId, RolloutCoordinatorV2.Phase.CANARY, 1) { failed = false; } catch { failed = true; }
        require(failed, "advance restored state after halt");
    }

    function testKillSwitchBlocksSubsequentAdvance() public {
        setUp();
        uint256 releaseId = approvedRelease();
        operator.start(coordinator, releaseId, DEVICE);
        haltActor.enableKillSwitch(registry, DEVICE);
        bool failed;
        try operator.advance(coordinator, releaseId, RolloutCoordinatorV2.Phase.CANARY, 1) { failed = false; } catch { failed = true; }
        require(failed, "advance accepted after kill switch");
    }

    function testMissingDevicesReduceRolloutSuccessRate() public {
        setUp();
        uint256 releaseId = approvedRelease();
        operator.start(coordinator, releaseId, DEVICE);
        bool failed;
        try operator.advanceWithCounts(
            coordinator, releaseId, RolloutCoordinatorV2.Phase.CANARY, 1, 90, 0, 0, 0, 10
        ) {
            failed = false;
        } catch { failed = true; }
        require(failed, "missing devices excluded from success denominator");
    }
}

// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {KeyManager} from "../src/KeyManager.sol";
import {DeviceAttestationV2} from "../src/DeviceAttestationV2.sol";

contract V2WitnessActor {
    function confirm(
        DeviceAttestationV2 attestation,
        bytes32 key,
        bytes32 root,
        bytes32 terminalRoot,
        uint32 received,
        uint32 success,
        uint32 missing
    ) external {
        attestation.confirmSummary(key, root, terminalRoot, received, success, 0, 0, 0, missing);
    }
}

contract V2InvariantHandler {
    DeviceAttestationV2 public immutable attestation;
    V2WitnessActor public immutable witness;
    bytes32 public lastKey;
    uint32 public lastExpected;

    constructor(DeviceAttestationV2 attestation_, V2WitnessActor witness_) {
        attestation = attestation_;
        witness = witness_;
    }

    function createAndFinalize(uint16 expectedRaw, uint16 missingRaw, bytes32 salt) external {
        if (lastKey != bytes32(0)) return;
        uint32 expected = uint32(expectedRaw % 1000) + 1;
        uint32 missing = uint32(missingRaw) % (expected + 1);
        uint32 received = expected - missing;
        bytes32 rolloutId = keccak256(abi.encode("invariant-rollout", salt));
        bytes32 root = received == 0 ? bytes32(0) : keccak256(abi.encode("invariant-root", salt));
        bytes32 terminalRoot = keccak256(abi.encode("invariant-terminal-root", salt));

        bytes32 key = attestation.registerCohort(
            1,
            rolloutId,
            1,
            keccak256(abi.encode("cohort", salt)),
            keccak256(abi.encode("cohort-root", salt)),
            expected,
            uint64(block.timestamp)
        );
        attestation.proposeSummary(key, root, terminalRoot, received, received, 0, 0, 0, missing);
        witness.confirm(attestation, key, root, terminalRoot, received, received, missing);
        lastKey = key;
        lastExpected = expected;
    }
}

contract LedgerGuardV2InvariantTest {
    struct FuzzSelector { address addr; bytes4[] selectors; }
    struct FuzzArtifactSelector { string artifact; bytes4[] selectors; }
    struct FuzzInterface { address addr; string[] artifacts; }

    KeyManager private keyManager;
    DeviceAttestationV2 private attestation;
    V2WitnessActor private witness;
    V2InvariantHandler private handler;
    address[] private invariantTargets;

    function setUp() public {
        keyManager = new KeyManager();
        attestation = new DeviceAttestationV2(address(keyManager));
        witness = new V2WitnessActor();
        handler = new V2InvariantHandler(attestation, witness);
        keyManager.setSigner(address(handler), KeyManager.Role.OPERATOR, true);
        keyManager.setSigner(address(witness), KeyManager.Role.AUDITOR, true);
        invariantTargets.push(address(handler));
    }

    function targetContracts() public view returns (address[] memory) {
        return invariantTargets;
    }

    function targetArtifactSelectors() public pure returns (FuzzArtifactSelector[] memory values) {
        values = new FuzzArtifactSelector[](0);
    }

    function targetArtifacts() public pure returns (string[] memory values) { values = new string[](0); }
    function excludeArtifacts() public pure returns (string[] memory values) { values = new string[](0); }
    function targetSenders() public pure returns (address[] memory values) { values = new address[](0); }
    function excludeSenders() public pure returns (address[] memory values) { values = new address[](0); }
    function excludeContracts() public pure returns (address[] memory values) { values = new address[](0); }
    function targetInterfaces() public pure returns (FuzzInterface[] memory values) {
        values = new FuzzInterface[](0);
    }
    function targetSelectors() public pure returns (FuzzSelector[] memory values) {
        values = new FuzzSelector[](0);
    }
    function excludeSelectors() public pure returns (FuzzSelector[] memory values) {
        values = new FuzzSelector[](0);
    }

    function invariantFinalizedCountersReconcileExpectedCohort() public view {
        bytes32 key = handler.lastKey();
        if (key == bytes32(0)) return;

        DeviceAttestationV2.OutcomeSummary memory summary = attestation.getSummary(key);
        require(summary.state == DeviceAttestationV2.SummaryState.FINALIZED, "summary not finalized");
        require(
            summary.receivedValidCount + summary.missingCount == handler.lastExpected(),
            "finalized counts do not reconcile"
        );
        require(summary.terminalOutcomeRoot != bytes32(0), "terminal outcome root missing");
    }
}

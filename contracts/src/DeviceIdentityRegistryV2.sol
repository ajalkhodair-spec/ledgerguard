// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {KeyManager} from "./KeyManager.sol";

/// @title DeviceIdentityRegistryV2
/// @notice Governance-controlled software device signer enrollment for V2 receipts.
/// @dev This PoC registry does not claim hardware-backed identity or production PKI.
contract DeviceIdentityRegistryV2 {
    KeyManager public immutable keyManager;

    struct DeviceIdentity {
        address signer;
        bool active;
        uint64 revision;
    }

    mapping(bytes32 => DeviceIdentity) private _identities;

    event DeviceIdentitySet(bytes32 indexed deviceIdHash, address indexed signer, bool active, uint64 revision);

    modifier onlyGovernanceOwner() {
        require(msg.sender == keyManager.owner(), "DeviceIdentityRegistryV2: not governance owner");
        _;
    }

    constructor(address keyManager_) {
        require(keyManager_ != address(0), "DeviceIdentityRegistryV2: zero KeyManager");
        keyManager = KeyManager(keyManager_);
    }

    function setDeviceIdentity(bytes32 deviceIdHash, address signer, bool active) external onlyGovernanceOwner {
        require(deviceIdHash != bytes32(0), "DeviceIdentityRegistryV2: empty device id");
        require(signer != address(0), "DeviceIdentityRegistryV2: zero signer");

        DeviceIdentity storage identity = _identities[deviceIdHash];
        identity.signer = signer;
        identity.active = active;
        identity.revision += 1;

        emit DeviceIdentitySet(deviceIdHash, signer, active, identity.revision);
    }

    function revokeDeviceIdentity(bytes32 deviceIdHash) external onlyGovernanceOwner {
        DeviceIdentity storage identity = _identities[deviceIdHash];
        require(identity.signer != address(0), "DeviceIdentityRegistryV2: unknown device");
        identity.active = false;
        identity.revision += 1;
        emit DeviceIdentitySet(deviceIdHash, identity.signer, false, identity.revision);
    }

    function getDeviceIdentity(bytes32 deviceIdHash)
        external
        view
        returns (address signer, bool active, uint64 revision)
    {
        DeviceIdentity memory identity = _identities[deviceIdHash];
        return (identity.signer, identity.active, identity.revision);
    }

    function isActiveSigner(bytes32 deviceIdHash, address signer) external view returns (bool) {
        DeviceIdentity memory identity = _identities[deviceIdHash];
        return identity.active && identity.signer == signer;
    }
}

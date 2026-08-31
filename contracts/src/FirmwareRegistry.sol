// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import {KeyManager} from "./KeyManager.sol";

/// @title FirmwareRegistry
/// @notice On-chain release metadata registry with role-threshold approvals.
/// @dev Stores only compact metadata: CID + hashes + policy fields.
contract FirmwareRegistry {
    KeyManager public immutable keyManager;

    enum ReleaseStatus {
        NONE,
        PROPOSED,
        APPROVED,
        DEPRECATED
    }

    struct Release {
        bytes32 deviceType;
        uint64 version;      // monotonically increasing (PoC uses an integer)
        string cidFw;        // IPFS CID (string)
        bytes32 sha256Fw;    // sha256 of payload
        uint32 size;         // bytes
        bytes32 sbomHash;    // sha256 (or other) of SBOM
        bytes32 provHash;    // sha256 (or other) of provenance statement
        uint32 minBootloader;
        uint64 expiresAt;
        ReleaseStatus status;
        uint8 requiredRolesMask;
        uint8 threshold;
        uint8 approvalsCount; // distinct roles
        uint8 approvalsMask;  // which roles have approved
    }

    uint256 public nextReleaseId = 1;

    mapping(uint256 => Release) public releases;
    mapping(uint256 => mapping(address => bool)) public approvedBy;

    mapping(bytes32 => uint256) public latestApprovedId;
    mapping(bytes32 => bool) public killSwitchActive;

    event ReleaseRegistered(
        uint256 indexed releaseId,
        bytes32 indexed deviceType,
        uint64 version,
        string cidFw,
        bytes32 sha256Fw,
        uint32 size,
        bytes32 sbomHash,
        bytes32 provHash,
        uint64 expiresAt
    );

    event ReleaseApprovalRecorded(uint256 indexed releaseId, address indexed signer, KeyManager.Role role);
    event ReleaseApproved(uint256 indexed releaseId, bytes32 indexed deviceType, uint64 version);
    event ReleaseDeprecated(uint256 indexed releaseId, bytes32 indexed deviceType);
    event KillSwitchSet(bytes32 indexed deviceType, bool active);

    modifier onlyActiveRole(KeyManager.Role role) {
        (KeyManager.Role r, bool active) = keyManager.getSigner(msg.sender);
        require(active, "FirmwareRegistry: signer inactive");
        require(r == role, "FirmwareRegistry: wrong role");
        _;
    }

    modifier onlyAnyActiveRole2(KeyManager.Role r1, KeyManager.Role r2) {
        (KeyManager.Role r, bool active) = keyManager.getSigner(msg.sender);
        require(active, "FirmwareRegistry: signer inactive");
        require(r == r1 || r == r2, "FirmwareRegistry: role denied");
        _;
    }

    constructor(address keyManager_) {
        require(keyManager_ != address(0), "FirmwareRegistry: zero KeyManager");
        keyManager = KeyManager(keyManager_);
    }

    function registerRelease(
        bytes32 deviceType,
        uint64 version,
        string calldata cidFw,
        bytes32 sha256Fw,
        uint32 size,
        bytes32 sbomHash,
        bytes32 provHash,
        uint32 minBootloader,
        uint64 expiresAt
    ) external onlyActiveRole(KeyManager.Role.VENDOR) returns (uint256 releaseId) {
        require(deviceType != bytes32(0), "FirmwareRegistry: empty deviceType");
        require(bytes(cidFw).length != 0, "FirmwareRegistry: empty CID");
        require(expiresAt == 0 || expiresAt > block.timestamp, "FirmwareRegistry: expiresAt in past");

        (uint8 mask, uint8 threshold, bool exists) = keyManager.getPolicy(deviceType);
        require(exists, "FirmwareRegistry: missing policy");

        releaseId = nextReleaseId;
        nextReleaseId = releaseId + 1;

        releases[releaseId] = Release({
            deviceType: deviceType,
            version: version,
            cidFw: cidFw,
            sha256Fw: sha256Fw,
            size: size,
            sbomHash: sbomHash,
            provHash: provHash,
            minBootloader: minBootloader,
            expiresAt: expiresAt,
            status: ReleaseStatus.PROPOSED,
            requiredRolesMask: mask,
            threshold: threshold,
            approvalsCount: 0,
            approvalsMask: 0
        });

        emit ReleaseRegistered(
            releaseId,
            deviceType,
            version,
            cidFw,
            sha256Fw,
            size,
            sbomHash,
            provHash,
            expiresAt
        );
    }

    function approveRelease(uint256 releaseId) external {
        Release storage rel = releases[releaseId];
        require(rel.status == ReleaseStatus.PROPOSED, "FirmwareRegistry: not proposed");

        (KeyManager.Role role, bool active) = keyManager.getSigner(msg.sender);
        require(active, "FirmwareRegistry: signer inactive");

        uint8 bit = keyManager.roleBit(role);
        require((rel.requiredRolesMask & bit) != 0, "FirmwareRegistry: role not eligible");
        require(!approvedBy[releaseId][msg.sender], "FirmwareRegistry: already approved by signer");

        approvedBy[releaseId][msg.sender] = true;
        emit ReleaseApprovalRecorded(releaseId, msg.sender, role);

        // count a role only once
        if ((rel.approvalsMask & bit) == 0) {
            rel.approvalsMask |= bit;
            rel.approvalsCount += 1;
        }

        if (rel.approvalsCount >= rel.threshold) {
            rel.status = ReleaseStatus.APPROVED;

            uint256 current = latestApprovedId[rel.deviceType];
            if (current == 0 || releases[current].version < rel.version) {
                latestApprovedId[rel.deviceType] = releaseId;
            }
            emit ReleaseApproved(releaseId, rel.deviceType, rel.version);
        }
    }

    function deprecateRelease(uint256 releaseId) external onlyActiveRole(KeyManager.Role.SECURITY) {
        Release storage rel = releases[releaseId];
        require(rel.status != ReleaseStatus.NONE, "FirmwareRegistry: unknown release");
        rel.status = ReleaseStatus.DEPRECATED;
        emit ReleaseDeprecated(releaseId, rel.deviceType);

        // If this was latestApprovedId, we don't auto-recompute (PoC simplification).
        // Operators can register a newer release or deactivate kill switch as needed.
    }

    function setKillSwitch(bytes32 deviceType, bool active) external onlyAnyActiveRole2(KeyManager.Role.SECURITY, KeyManager.Role.REGULATOR) {
        killSwitchActive[deviceType] = active;
        emit KillSwitchSet(deviceType, active);
    }

    /// @notice Returns the latest approved release id for deviceType, or 0 if none/disabled/expired.
    function latestApproved(bytes32 deviceType) external view returns (uint256 releaseId) {
        if (killSwitchActive[deviceType]) return 0;

        uint256 rid = latestApprovedId[deviceType];
        if (rid == 0) return 0;

        Release memory rel = releases[rid];
        if (rel.status != ReleaseStatus.APPROVED) return 0;
        if (rel.expiresAt != 0 && block.timestamp > rel.expiresAt) return 0;

        return rid;
    }

    /// @notice Convenience getter for the content integrity-relevant fields.
    function getReleaseContent(uint256 releaseId)
        external
        view
        returns (bytes32 deviceType, uint64 version, string memory cidFw, bytes32 sha256Fw, uint32 size, bytes32 sbomHash, bytes32 provHash)
    {
        Release memory rel = releases[releaseId];
        return (rel.deviceType, rel.version, rel.cidFw, rel.sha256Fw, rel.size, rel.sbomHash, rel.provHash);
    }

    function isApproved(uint256 releaseId) external view returns (bool) {
        return releases[releaseId].status == ReleaseStatus.APPROVED;
    }
}

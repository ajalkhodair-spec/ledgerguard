// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @title KeyManager
/// @notice Minimal on-chain key registry and policy store for the LedgerGuard PoC.
///         It enforces signer activation/revocation and per-device-class approval policies.
/// @dev This contract is intentionally small (no external dependencies) for auditability.
contract KeyManager {
    address public owner;

    /// @notice Roles used for approval governance and operational actions.
    /// @dev Values are used as bit positions in policy masks: (1 << uint8(role)).
    enum Role {
        NONE,
        VENDOR,
        SECURITY,
        REGULATOR,
        OPERATOR,
        AUDITOR
    }

    struct Signer {
        Role role;
        bool active;
    }

    /// @notice (signer address) -> role + active flag
    mapping(address => Signer) private _signers;

    struct Policy {
        uint8 requiredRolesMask; // bitmask of allowed roles for approval
        uint8 threshold;         // number of distinct roles required (role-unique)
        bool exists;
    }

    /// @notice deviceType -> policy
    mapping(bytes32 => Policy) private _policies;

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event SignerSet(address indexed signer, Role role, bool active);
    event PolicySet(bytes32 indexed deviceType, uint8 requiredRolesMask, uint8 threshold);

    modifier onlyOwner() {
        require(msg.sender == owner, "KeyManager: not owner");
        _;
    }

    constructor() {
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "KeyManager: zero owner");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    /// @notice Set or update a signer.
    function setSigner(address signer, Role role, bool active) external onlyOwner {
        require(signer != address(0), "KeyManager: zero signer");
        require(role != Role.NONE, "KeyManager: invalid role");
        _signers[signer] = Signer({role: role, active: active});
        emit SignerSet(signer, role, active);
    }

    /// @notice Convenience revocation.
    function revokeSigner(address signer) external onlyOwner {
        Signer storage s = _signers[signer];
        require(s.role != Role.NONE, "KeyManager: unknown signer");
        s.active = false;
        emit SignerSet(signer, s.role, false);
    }

    /// @notice Configure approval policy for a device class.
    /// @param deviceType A bytes32 device class identifier (e.g., bytes32("M4")).
    /// @param requiredRolesMask Bitmask of roles eligible to approve.
    /// @param threshold Number of distinct roles required for approval.
    function setPolicy(bytes32 deviceType, uint8 requiredRolesMask, uint8 threshold) external onlyOwner {
        require(deviceType != bytes32(0), "KeyManager: empty deviceType");
        require(requiredRolesMask != 0, "KeyManager: empty mask");
        uint8 pop = _popcount(requiredRolesMask);
        require(threshold > 0 && threshold <= pop, "KeyManager: bad threshold");

        _policies[deviceType] = Policy({
            requiredRolesMask: requiredRolesMask,
            threshold: threshold,
            exists: true
        });
        emit PolicySet(deviceType, requiredRolesMask, threshold);
    }

    function getPolicy(bytes32 deviceType) external view returns (uint8 requiredRolesMask, uint8 threshold, bool exists) {
        Policy memory p = _policies[deviceType];
        return (p.requiredRolesMask, p.threshold, p.exists);
    }

    function getSigner(address signer) external view returns (Role role, bool active) {
        Signer memory s = _signers[signer];
        return (s.role, s.active);
    }

    function isActive(address signer) external view returns (bool) {
        return _signers[signer].active;
    }

    function roleOf(address signer) external view returns (Role) {
        return _signers[signer].role;
    }

    function roleBit(Role role) public pure returns (uint8) {
        return uint8(1) << uint8(role);
    }

    function _popcount(uint8 x) internal pure returns (uint8) {
        // Kernighan popcount for 8-bit
        uint8 c = 0;
        while (x != 0) {
            x &= (x - 1);
            c++;
        }
        return c;
    }
}

# LedgerGuard PoC Scope

LedgerGuard is a proof-of-concept implementation for a firmware governance framework built around a permissioned DLT control plane, content-addressed firmware artifacts, staged rollout policy, and Merkle-rooted outcome accountability.

## Implemented in the PoC

- Permissioned Besu IBFT2 network for local control-plane validation.
- Solidity contracts for signer management, firmware metadata registration, rollout coordination, and outcome attestation.
- IPFS-backed content-addressed artifact publication.
- Threshold approval and revocation flows for vendor, security, regulator, and operator roles.
- Canary, batch, and global rollout progression.
- Authenticated software-device fleet for signed terminal receipts and rollback outcomes.
- Receipt-root and complete expected-cohort terminal-outcome commitments.
- Structured adversarial checks for substitution, unavailable artifacts, revoked signers, kill switch behavior, and downgrade rejection.
- Reviewer-revision evidence pipeline that produces raw records, CSV summaries, publication figures, validation reports, checksums, and a release archive.

## Not Executed or Simplified

- Real MCU, SBC, or gateway hardware execution.
- Secure boot enforcement and hardware anti-rollback counters.
- Physical A/B partition writes and bootloader state transitions.
- mTLS deployment and production identity provisioning.
- Sigstore, DSSE, or in-toto verification against a production CI system.
- Packet-level or physical-WAN shaping for latency, bandwidth, jitter, and packet loss.

Analytical scaling rows are explicitly separated from local Besu measurements,
application-shaped IPFS fetches, and authenticated software emulation. They are
framework-evaluation evidence, not physical-hardware or production-network results.

## Evidence boundary

The PoC supports claims about local governance correctness, policy checks,
metadata anchoring, control-plane transaction flow, authenticated receipt
aggregation, complete-cohort commitments, and reproducible result generation. It
does not support claims that embedded hardware or a production deployment has
been validated.

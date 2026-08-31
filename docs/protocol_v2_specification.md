# LedgerGuard V2 Protocol Specification

Status: design baseline for reviewer-revision implementation

## Purpose

LedgerGuard V2 preserves the V1 release-governance architecture and replaces the
integrity-only outcome commitment with a completeness-aware, authenticated,
independently witnessed commitment. V1 evidence remains V1 evidence.

## Actors

- Governance owner: enrolls and revokes device signing identities.
- Fleet operator/aggregator: proposes a cohort and an outcome summary.
- Independent auditor/witness: recomputes the summary from the same frozen cohort
  using an independently received append-only journal and confirms exactly
  matching fields.
- Software-emulated device: signs one terminal receipt for a rollout epoch.

The operator and witness must use distinct active role accounts. The protocol does
not claim resistance to their collusion; collusion is a residual trust assumption.
The local PoC combines fleet-operator and outcome-aggregator duties in one account.
This is a tested role combination, not a claim of organizational independence.

## Contract Roles

The framework retains four core governance modules:

```text
KeyManager
FirmwareRegistry
RolloutCoordinatorV2
DeviceAttestationV2
```

`DeviceIdentityRegistryV2` and `DeviceReceiptVerifierV2` are supporting contracts
for authenticated software-device evidence. Legacy `DeviceAttestation` and
`NaiveDeviceReporting` are experimental comparison contracts; they are not
additional V2 core governance modules.

## Receipt Schema

Each V2 receipt is an EIP-712 typed message with:

```text
deviceIdHash
releaseId
rolloutId
epoch
cohortId
deadline
targetVersion
outcome
observedAt
nonce
```

The EIP-712 domain binds the signature to:

```text
name = LedgerGuardDeviceReceipt
version = 2
chainId
verifyingContract
```

This prevents a signature from being moved across chains, verifier contracts,
releases, rollouts, epochs, or cohorts. Each observer also keeps an append-only
`(deviceIdHash, nonce)` journal; reuse of a previously consumed positive nonce is
rejected before aggregation.

## Outcomes

Terminal outcomes are:

```text
SUCCESS
ROLLBACK
FAIL
REJECTED
MISSING
```

`MISSING` is not device-signed. It is derived at cohort finalization for expected
devices without a valid terminal receipt by the deadline.

## Cohort Commitment

Before accepting a summary, the operator registers:

```text
releaseId
rolloutId
epoch
cohortId
cohortCommitment
expectedCount
deadline
```

The off-chain cohort commitment is a SHA-256 Merkle root over device identity
hashes sorted lexicographically as raw 32-byte values. Duplicate identities are
invalid. The commitment and count are immutable after registration.

## Summary Reconciliation

The aggregator proposes:

```text
receiptRoot
terminalOutcomeRoot
receivedValidCount
successCount
rollbackCount
failCount
rejectedCount
missingCount
```

The contract requires:

```text
receivedValidCount = success + rollback + fail + rejected
receivedValidCount + missing = expectedCount
```

`receiptRoot` commits the received signed receipts. `terminalOutcomeRoot` commits
one deterministic, lexicographically ordered terminal record for every expected
device. A received record binds its signed-receipt hash, outcome, observation
time, and nonce. A non-reporting device receives a deterministic `MISSING` record
with the cohort deadline, zero nonce, and zero receipt hash.

The reported success rate is always `successCount / expectedCount`. Selectively
omitting an expected device changes its complete-cohort leaf to `MISSING` and
increases `missingCount`; it cannot reduce the denominator or leave the committed
terminal set unchanged.

## Witness Confirmation

The witness submits the complete summary fields, not only a Boolean approval. The
contract hashes and compares every bound cohort and summary field. A mismatch
reverts. A matching confirmation finalizes the epoch and prevents replacement.

## Receipt Validation Pipeline

Both aggregator and witness run in separate processes over separately received,
append-only receipt journals. Each independently:

1. load the immutable cohort;
2. reject duplicate device identities;
3. verify device enrollment and active status;
4. verify the EIP-712 signature and all domain fields;
5. reject observations after the deadline;
6. require one terminal outcome per received device;
7. calculate missing expected devices;
8. reject a device nonce already consumed in that observer's journal;
9. sort canonical signed-receipt leaves and rebuild the receipt root;
10. generate one terminal record for every expected device and rebuild the
    complete-cohort terminal root;
11. calculate counters and expected-cohort success rate;
12. submit matching summaries from distinct role accounts.

## State Machine

```text
UNCONFIGURED -> COHORT_REGISTERED -> PROPOSED -> FINALIZED
```

- Cohort fields are immutable after registration.
- Only one proposal is accepted per cohort epoch.
- Only a distinct active witness can confirm.
- Conflicting confirmation reverts.
- Finalized summaries are append-only.
- Epochs must increase sequentially for each release/rollout pair.

Rollout transitions use both an expected phase and an expected transition nonce.
Concurrent actions from the same initial state therefore produce one valid
transition and stale-phase/nonce reverts for later conflicting transactions. Each
advance rechecks release eligibility, so an earlier kill-switch action blocks a
stale advance.

The transaction receipts establish which same-block transaction succeeded and
which reverted. Human-readable revert reasons are probed afterward with a
historical `eth_call` at the containing block. That probe uses post-block state;
it is not transaction-index-aware replay of the reverted transaction's exact
intermediate pre-state. The reason text is therefore supporting interpretation,
while receipt status and final state are the primary concurrency evidence.

## Security Scope

V2 is intended to test authenticity, replay separation, completeness accounting,
counter reconciliation, deterministic race outcomes, and witnessed commitment.
It does not claim hardware-backed keys, secure boot, HSM protection, physical
device identity, production PKI, or resistance to aggregator-witness collusion or
common omission before both independent journals observe a receipt.

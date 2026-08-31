# Experimental Setup

## Execution Host

The final reviewer-revision campaign was executed on one Apple MacBook Pro
(Mac14,6) with an Apple M2 Max processor (12 CPU cores) and 32 GB memory, running
macOS 26.5.2. All Besu validators, IPFS, role clients, the HTTP/SQLite comparison,
and software-device processes ran on this host. This is a controlled local
research environment, not a multi-host or production deployment.

Key tool versions were Hyperledger Besu 25.12.0, Solidity 0.8.24, Foundry
1.5.1-stable, Slither 0.11.6, Python 3.14.6, and Docker 24.0.7. Version output is
preserved with the evidence package.

## Control Plane

The control plane used four local Besu validator processes with IBFT2 consensus,
chain ID 1337, a two-second configured block period, and zero minimum gas price.
Submission-to-receipt latency includes waiting for block production and receipt
polling; it is not EVM execution time. Gas units are reported directly. No
currency conversion is made.

The four core governance modules are `KeyManager`, `FirmwareRegistry`,
`RolloutCoordinatorV2`, and `DeviceAttestationV2`. `DeviceIdentityRegistryV2` and
`DeviceReceiptVerifierV2` support authenticated device evidence. Legacy
`DeviceAttestation` and `NaiveDeviceReporting` are comparison contracts.

Local role accounts represent vendor/deployer, security, regulator, fleet
operator/outcome aggregator, and auditor/witness duties. Keys are generated for
local execution and stored only in ignored `.env` and generated network files.
The operator and aggregator are combined in this PoC. The witness uses a distinct
active role account and a separate process. Organizational separation between
operator and aggregator remains a deployment-level extension. This does not
establish hardware-backed key custody.

## Final V2 Timing Campaign

Each valid path executes seven state-changing operations against one final V2
deployment and ABI:

1. register a firmware release;
2. submit the security approval;
3. submit the regulator approval;
4. start the rollout;
5. register the expected cohort commitment;
6. propose receipt and complete terminal-outcome roots with counters;
7. confirm the same summary from the witness role.

Fifty complete paths contribute 350 analyzed transaction rows. One additional
attempt is retained in all-attempt raw evidence but excluded because a client
polling error followed an otherwise successful receipt and the path did not
complete. The exclusion is deterministic: an analyzed path must contain exactly
one successful row for all seven required operations. The canonical analysis CSV
contains only the 50 complete paths.

These transactions use fixture cohort commitments and counters. They exercise
the final governance ABI, not an integrated deployment of the 96,000 fleet
receipts. Retrospective compilation matches the exact runtime of all six final
contracts, including metadata and bound immutable addresses. Every timing
transaction is linked to its target address, selector, successful receipt, gas,
block, and historical runtime. The fingerprint records ABI, runtime, source,
storage-layout, and receipt-schema hashes. No Git commit existed for the original
execution, so historical Git provenance is explicitly unavailable; see
`docs/evidence_freeze.md`.

Deployment gas covers the six final V2 contracts plus legacy
`DeviceAttestation` and `NaiveDeviceReporting`. Operation gas uses 50 successful
receipts per operation for the seven timing operations and four lifecycle
operations: kill-switch activation, release deprecation, governance-signer
replacement, and device-identity replacement. Each row reports minimum, Q1,
median, Q3, maximum, IQR, mean, sample standard deviation, calldata bytes, and
event count.

## Persistent Comparison

The centralized comparison is an HTTP service backed by SQLite. It implements
the comparable authorization, release, threshold-approval, rollout, outcome,
and audit workflow with persistent state. It does not provide distributed
consensus or replicated tamper evidence. Fifty repetitions are retained per
operation. Comparisons are limited to semantically matched operations.

## Authenticated Software Fleet

The fleet matrix crosses three cohort sizes (100, 500, and 1,000 devices), three
configured failure rates (1%, 2%, and 5%), and 20 fixed seeds per configuration.
This produces 180 runs and 96,000 signed receipts. Each software device has a
distinct ECDSA key and signs an EIP-712 receipt bound to chain, verifier contract,
release, rollout, epoch, cohort, deadline, version, outcome, observation time,
and nonce.

The fleet runner iterates software identities sequentially; fleet size is not a
count of simultaneously running physical devices. Keys and the verifier-domain
address are deterministic test fixtures. Signature generation and verification
are real cryptographic operations, but firmware installation is not performed.
After sampling a failure, the runner assigns it to `ROLLBACK` with conditional
probability 0.3 and otherwise to `FAIL`. Therefore `100 - SUCCESS share` combines
rollback and failure; it is not the rollback share alone.

Both observers verify signatures and active identities, reject replay or
duplicate identities, and reconstruct two roots. `receiptRoot` covers received
signed receipts. `terminalOutcomeRoot` covers exactly one canonical terminal
record for every expected device, including deterministic `MISSING` records.
The validator rebuilds all feasible roots and counters from preserved receipts.

The aggregator and witness run as separate processes over independently populated
append-only journals. Neither journal is copied from the other. Six cases cover
dual delivery, unilateral omission in either direction, common omission as a
residual boundary, one-sided alteration, and duplication.

The harness populates the journals independently; it does not demonstrate
device-originated mTLS delivery. Independent reconstruction detects unilateral
omission or alteration. It does not protect against common upstream omission
before both observers receive evidence, or collusion between aggregator and
witness. Identity-level completeness is reconstructed off-chain. The contract
enforces matching commitments and counter constraints, not proof of every leaf.

## Content Delivery and Cache

IPFS artifacts are fetched from a local gateway. Three profiles apply configured
application-level delay and read-rate limits. Each profile has 20 independent
fetches with SHA-256 and byte-count verification. These controls do not reproduce
packet loss, congestion, routing, jitter, TCP dynamics, or a physical WAN.

The cache experiment has cache OFF and cache ON modes, with ten independently
reset trials per mode and 1,000 requests per trial. Each ON trial starts empty,
performs one cold origin fetch, and serves subsequent requests from the local
cache. Trial evidence records cold-fetch time, median warm-hit time, total time,
origin requests and bytes, cache hits, and integrity failures.

## Fault and Security Campaigns

Five fresh four-validator networks exercise normal progress, progress with one
stopped validator, loss of progress with two stopped validators, and restoration
after one validator restarts. Restoration timing begins at process restart and
ends separately at the first new block and first successful transaction receipt.
These are process-crash observations; active Byzantine behavior is not injected.

The final Foundry run executes 62 tests, including a fixed-seed 10,000-case dedicated fuzz
property and a 256-run, depth-500 stateful invariant campaign with 128,000 calls.
Lifecycle tests cover governance-signer and device-key revocation and replacement.
The final coverage report is 99.04% line, 98.03% statement, 100.00% function, and
26.13% branch. The viaIR minimum-optimization report warns about inaccurate
source mappings and missing instruction anchors; the non-IR coverage probe
fails with stack-too-deep. Unresolved branch records remain in the denominator.
The branch-by-branch inventory and residual categories are in
`results/reviewer_revision/validation/coverage_review.md`. Neither high line
coverage nor the invariant call count establishes exhaustive testing; the
stateful handler targets `createAndFinalize` only.
It creates at most one cohort per run, then returns early on subsequent calls;
the 128,000 handler invocations must not be read as distinct constructive paths.
The critical-branch matrix maps direct tests separately from randomized valid
counter reconciliation and does not claim fuzz coverage for every guard.

Thirty-five Python tests cover the persistent baseline, receipt authentication,
terminal identity uniqueness, all five terminal states, missing identities,
canonical ordering, root sensitivity, replay protection, metadata handling, and
regressions in outcome, outlier, and gas-summary definitions.
Closure tests additionally check gas break-even arithmetic and sanitized genesis
capture.
Named test results are preserved in `raw/security/python_final.txt` under the
reviewer results directory.
Slither runs its default detector set over nine contracts; no detector or finding
is suppressed. Its 15 findings (zero high, one medium, thirteen low, one
informational) each have a source location, disposition, rationale, related test,
and residual risk in `validation/slither_triage.csv`. No protocol-source change
was made for this triage. Mythril and formal verification are not run.

Same-block race receipts and final contract state are the primary concurrency
evidence. Revert text is obtained with historical `eth_call` at the containing
block, which uses post-block state and is not exact transaction-index-aware replay.

## Statistical and Evidence Protocol

Continuous results report sample count, minimum, Q1, median, Q3, maximum, IQR,
mean, and sample standard deviation. Timing and fleet summaries use fixed-seed
10,000-resample bootstrap confidence intervals where specified. No unsupported
monotonic fleet-size conclusion is inferred from point estimates alone.

Figure 7 reports separate SUCCESS, ROLLBACK, and FAIL shares for the fixed
500-device cohort, using means and bootstrap 95% confidence intervals over 20
seeds per failure rate. REJECTED and MISSING are retained in the summary CSV
and are zero in these runs. Figure 8 uses horizontal quartile box plots with all
20 fetches per profile visible on a logarithmic time axis. The P3 maximum of
915.736736 seconds is retained in both raw and summary evidence.

Accountability scaling uses one transaction per device for naive reporting,
`ceil(N/B)` transactions for V1, and `3*ceil(N/B)` for V2. At N=500 and B=50,
the counts are 500, 10, and 30, respectively, or 98% V1 and 94% V2 reduction
relative to naive reporting. Gas projections multiply the number of complete
paths by the median of measured path totals, not the sum of operation medians.
The current V2 path median is 434,143 gas. Storage-slot projections exclude
blockchain database, trie, log, replication, and off-chain receipt overhead.

Raw receipts, logs, transaction identities, CSV summaries, status files, figures,
and checksums are generated from the runners. A validation gate checks sample
counts, unique transaction hashes, signatures, roots, counters, evidence labels,
claim boundaries, and required negative cases before packaging.

## Scope Boundary

The setup supports a research proof of concept for local governance correctness,
authenticated software-device evidence, completeness-aware accountability, and
reproducible analysis. It does not establish physical firmware installation,
secure boot, A/B partition recovery, HSM or secure-element custody, production
PKI, WAN behavior, active Byzantine tolerance, formal verification, or production
readiness.

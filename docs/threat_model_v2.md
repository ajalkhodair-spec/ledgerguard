# LedgerGuard V2 Threat Model

## Protected Properties

- An inactive or unregistered device signer cannot authenticate a receipt.
- A receipt cannot be replayed into a different domain or rollout context.
- One device contributes at most one terminal receipt to one cohort epoch.
- A positive device nonce cannot be consumed twice by the same observer.
- Missing expected devices remain in the outcome denominator.
- Every expected device identity is represented in the terminal-outcome root.
- A conflicting root or counter set cannot replace a finalized epoch.
- Operator and witness summaries must match exactly.
- A stale transaction cannot restore an earlier cohort or summary state.

## Tested Adversaries

- substituted receipt fields;
- wrong signer or revoked device signer;
- old-key use after device-key rotation and replacement-key activation;
- cross-chain and cross-contract replay;
- cross-release, rollout, epoch, and cohort replay;
- duplicate device receipt;
- replay of an already consumed device nonce;
- selective receipt omission;
- conflicting aggregate counters;
- conflicting Merkle roots;
- stale epoch submission;
- simultaneous proposal/confirmation and conflicting transactions;
- operator action after governance revocation;
- invalid Merkle proof and altered canonical leaf.

## Trust Assumptions

The local PoC combines fleet-operator and outcome-aggregator authority in one
software account. The witness is represented by a separate account and process.
Organizational separation between operator and aggregator remains a
deployment-level extension.

- The governance owner enrolls the intended software-emulated device public keys.
- At least one of the aggregator or witness follows the verification procedure
  and receives the relevant authenticated receipt through its own journal.
- The expected cohort is committed correctly before outcome collection.
- Besu consensus assumptions hold for the configured validator topology.
- Host clocks are adequate for the controlled local deadline experiment.
- Consensus block timestamps remain within the validator behavior assumed by the
  permissioned network; deadline and expiry checks are not independent of this
  assumption.

## Residual Risks

Independent reconstruction detects unilateral omission or alteration. It does
not protect against common upstream omission before both observers receive
evidence, or collusion between the aggregator and witness. Complete leaf sets
are verified off-chain; matching on-chain commitments do not prove that both
observers followed the verification procedure.

- Aggregator-witness collusion or common upstream omission can produce matching
  summaries that classify an unobserved receipt as `MISSING`.
- Compromised enrolled device keys can produce authentic but false receipts.
- V2 does not provide remote attestation of device software state.
- Local four-validator execution is not evidence of WAN or multi-host behavior.
- Software-emulated keys are not evidence of hardware key protection.
- A quorum capable of manipulating block timestamps can influence deadline and
  expiry boundaries; this PoC does not add an external trusted-time oracle.

## Claim Boundary

The strongest intended claim is:

> Under the tested expected-cohort and dual-journal witness model, selective
> omission visible to only one observer prevents finalization. Common omission
> cannot increase the expected-cohort success rate because missing identities
> remain in the denominator and complete-cohort terminal commitment.

The implementation must not claim that the system is secure against colluding
aggregator and witness roles or compromised device signing keys.

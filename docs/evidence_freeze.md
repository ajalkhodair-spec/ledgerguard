# Final Reviewer-Evidence Checkpoint

## Status

The narrow evidence-cleanup work is complete. The protocol source has not been
changed. The final checkpoint is identified by the post-campaign local revision
commit in `release/revision-v2-evidence-manifest.json`. Its `FROZEN` status requires
a clean public worktree. This repository had no commit at campaign execution;
the later commit cannot establish contemporaneous provenance. Nothing has been
pushed to GitHub as part of this cleanup.

The machine-readable status is
`results/reviewer_revision/validation/evidence_freeze_status.json`.

## Source and Deployment Traceability

`validation/protocol_fingerprint.json` under the reviewer results directory
records the protocol version (V2), receipt schema (2), compiler settings,
addresses, deployment transaction identities, source SHA-256 hashes, ABI hashes,
storage-layout hashes, and deployed runtime SHA-256 and Keccak-256 hashes.

Solidity 0.8.24, optimizer 200, viaIR, Berlin EVM, and IPFS metadata were used to
recompile the unchanged source. Immutable constructor addresses were bound using
the compiler's immutable references. All six final core/support contract runtimes
matched exactly, including metadata. All 350 complete-path timing transactions
matched the final ABI selectors and addresses, successful receipts, recorded gas
and block numbers, and the runtime retrieved at their historical blocks.
Compiler inputs/outputs, runtime bytes, and full transaction/receipt bindings are
preserved under `raw/protocol_fingerprint/`.

This demonstrates source/bytecode consistency, not an original Git execution
record or integration of the software fleet with the timing fixture campaign.
The older all-attempt evidence and pre-cleanup archive are retained locally.

## Security Evidence

| Evidence | Final checkpoint |
|---|---|
| Foundry tests | 62 passed |
| Dedicated fuzz cases | 10,000 |
| Stateful invariant calls | 128,000; 256 runs, depth 500 |
| Python tests | 35 passed |
| Line / statement coverage | 99.04% / 98.03% |
| Function / branch coverage | 100.00% / 26.13% |
| Slither findings | 0 high, 1 medium, 13 low, 1 informational |

The 19 added Foundry tests target authorization, revoked signers, role-unique
approvals, exact deadline/expiry boundaries, invalid roots/counters, missing
outcomes, witness mismatch, nonce/state transitions, kill switches, signature
edge cases, and legacy/comparison guards. Three added Python tests explicitly
check changed terminal states, duplicate expected identities, and exactly one
terminal record for each expected identity across all five terminal outcomes.
Eight summary/closure-regression tests check rollback separation, cohort
reconciliation, extreme observations, gas metrics, strict break-even arithmetic,
and removal of private genesis fields.

Coverage remains non-exhaustive. The report retains its original denominator
and the viaIR source-mapping warnings. A separate source-only LCOV inventory
does not replace the headline percentages. The invariant handler exercises one
selector and creates at most one cohort per run; subsequent handler calls return
without state changes. The 128,000 calls are not 128,000 distinct constructive
paths. See `critical_branch_matrix.csv` for 12 explicitly mapped conditions:
randomized evidence covers valid counter reconciliation, not all negative guards
or identity-level completeness. See also `coverage_review.md`,
`coverage_branches.csv`, and `coverage_source_summary.csv` in `validation/`.

Slither's medium strict-equality finding is triaged as a false positive for
the enum-state check. Timestamp-related low findings retain the permissioned
validator timestamp assumption. Each of all 15 findings has an explicit
disposition, source reference, rationale, related test, and residual risk in
`validation/slither_triage.csv`; none was suppressed.

## Corrected Figures and Formulas

Figure 7 now separates SUCCESS, ROLLBACK, and FAIL, rather than labeling
`100 - adoption` as rollback. It fixes fleet size at 500 and reports mean outcome
shares with 95% bootstrap intervals across 20 seeds at each configured failure
rate. All five outcome categories remain in `statistics/fleet_outcome_categories.csv`.

Figure 8 is horizontal, showing quartile boxes and all 20 observations per
profile on a logarithmic axis. P3's 915.736736-second observation is not removed.
`statistics/network_full_distribution.csv` includes n, min, Q1, median, Q3,
max, IQR, mean, and sample standard deviation for all three profiles.

At N=500 and B=50, naive reporting uses 500 transactions, V1 uses 10, and V2
uses 30. Reductions are 98% and 94%, respectively. The difference is **four
percentage points**, not six: V2's total cohort/proposal/confirmation sequence
has three operations per batch rather than V1's single root submission.
The additional accountability cost does not imply a defect in either formula.

Gas projections use complete logical-path medians: 169,245 for naive reporting,
97,836 for V1, and 434,143 for V2. The 36 fleet/batch/mode rows are analytical
projections, not 36 large on-chain campaigns. Gas tables separately identify
four core governance, two supporting verification, and two comparison contract
deployments, plus eleven operations with 50 observations each. Raw transactions
and receipts support recalculation of gas, calldata bytes, and event counts.

## Required Manuscript Boundaries

The analytical gas break-even result uses `434143 < B*169245`: a full V2 batch
of at least three devices is cheaper in gas than separate per-device reports
under the recorded medians. This is not another execution campaign. For a
partially filled last batch, check `ceil(N/B)*434143 < N*169245` for the entire
fleet; the full-batch threshold alone does not guarantee the fleet total.
See `statistics/gas_break_even.csv`.

The IPFS outlier investigation found matching bytes, HTTP 200, and valid
integrity, but no preserved per-request wall-clock timestamps or synchronized
host/Docker/gateway diagnostic trace. Its cause remains undetermined. No host
contention, gateway stall, or pacing defect is asserted without supporting
evidence; see `validation/network_outlier_review.json`.

- Independent reconstruction detects unilateral omission or alteration. It does
  not protect against common upstream omission before both observers receive
  evidence, or collusion between aggregator and witness.
- The local PoC combines fleet-operator and outcome-aggregator authority in one
  software account. The witness uses a separate account and process;
  organizational separation remains a deployment-level extension.
- Receipt status and final state are primary race evidence; reconstructed revert
  reasons use post-block `eth_call`, not exact intermediate-state replay.
- Fleet execution is sequential software emulation. Timing inputs are fixtures.
  IPFS shaping is application-level local execution, not a physical WAN.
- Five local process-crash trials are not active Byzantine-fault validation.
- No physical installation, A/B recovery, HSM, production PKI, formal verification,
  or production-readiness claim is supported.

Carry these boundaries into the threat model, discussion, limitations,
conclusion, and reviewer response. The final manuscript, verified literature
comparisons, author contribution roles, and page/line integration remain author
tasks; they are not marked complete by the implementation checks.

## Recheck and Package

Run `scripts/reproduce_reviewer_revision.sh --analysis-only` with the preserved
raw evidence and required dependencies to rebuild analyses, tests, figures,
metadata, checksums, and the full local archive. This path reads the existing
fingerprint without requiring the original chain to be online. Use
`verify_protocol_fingerprint.py --solc <solc-0.8.24>` with the original local chain
available for a fresh read-only historical-bytecode verification.

The full archive and generated raw evidence remain ignored by Git. The compact
`results_sample/` is the public representative subset, not the entire evidence
campaign. `release/evidence_manifest.json` records source traceability and
per-file hashes; `release/SHA256SUMS` permits independent integrity checking.

The expanded `release/revision-v2-evidence-manifest.json` records the revision
commit/tree, campaign boundaries, ABI/runtime/address fingerprints, receipt-schema
hash, experiment-configuration hashes, analysis-script hashes, and raw evidence
hashes. The local genesis contains demo private fields, so only a sanitized
snapshot is archived, alongside hashes identifying the original and sanitized
representations. Its capture is retrospective, not an original campaign record.

After committing the public snapshot, use
`python -m experiments.reviewer_revision.generate_evidence_package --preserve-public-sample --require-frozen`
to rebuild the full archive without modifying tracked sample files. Sample
manifests retain their own generation-time provenance; the full archive binds
their exact bytes to the later frozen revision. This avoids a self-referential
Git commit hash inside the same commit.

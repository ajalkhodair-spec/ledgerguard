# Response to Reviewer 1 Draft

Page and line references are `TBD` until the revision manuscript is supplied.

## R1-1

Reviewer Comment:
Evidence qualification throughout outputs

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: Evidence types and claim boundaries are machine-validated.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: results/reviewer_revision/validation/validation_report.json
Summary CSV: results/reviewer_revision/validation/claim_registry.yaml
Analysis script: `experiments/reviewer_revision/`
Validation status: PASS

## R1-2

Reviewer Comment:
Explain block-period and uniform latency

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: Local 1/2/4-second sensitivity only.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: results/reviewer_revision/raw/block_period/
Summary CSV: results/reviewer_revision/statistics/block_period_sensitivity_summary.csv
Analysis script: `experiments/reviewer_revision/`
Validation status: PASS

## R1-3

Reviewer Comment:
Adequate repetitions and statistics

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: 350 transactions retrospectively bound to exact final V2 runtime and ABI. No contemporaneous Git commit was recorded; the post-campaign checkpoint is identified in release/revision-v2-evidence-manifest.json.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: results/reviewer_revision/raw/protocol_fingerprint/
Summary CSV: results/reviewer_revision/validation/protocol_fingerprint.json
Analysis script: `experiments/reviewer_revision/`
Validation status: PASS

## R1-4

Reviewer Comment:
Representative persistent centralized baseline

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: The baseline does not provide consensus or replicated tamper evidence.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: results/reviewer_revision/raw/baseline/
Summary CSV: results/reviewer_revision/validation/baseline_equivalence_matrix.csv
Analysis script: `experiments/reviewer_revision/`
Validation status: PASS

## R1-5

Reviewer Comment:
Batch-size and accountability sensitivity

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: Per-device, V1 integrity-only, and V2 witnessed paths are measured; fleet/batch scaling remains analytical.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: results/reviewer_revision/raw/accountability/
Summary CSV: results/reviewer_revision/csv/accountability_path_statistics.csv
Analysis script: `experiments/reviewer_revision/`
Validation status: PASS

## R1-6

Reviewer Comment:
Separate evidence classes

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: Evidence classes are explicit in reviewer-revision artifacts.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: results/reviewer_revision/raw/
Summary CSV: results/reviewer_revision/validation/validation_report.json
Analysis script: `experiments/reviewer_revision/`
Validation status: PASS

## R1-7

Reviewer Comment:
Comparative novelty table support

Response:
We agree that this point requires explicit evidence and scope control. The repository work addresses part of the request, but the item is not complete. Remaining limitation: Primary literature cells require manual verification.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: Not available
Summary CSV: Not available
Analysis script: `experiments/reviewer_revision/`
Validation status: PARTIAL

## R1-8

Reviewer Comment:
Gas-cost analysis

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: Eight deployments and eleven operation types are reported; gas price was zero and no currency conversion was performed.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: results/reviewer_revision/raw/besu_v2_final/deployment_receipts.json
Summary CSV: results/reviewer_revision/statistics/gas_summary_final.csv
Analysis script: `experiments/reviewer_revision/`
Validation status: PASS

## R1-9

Reviewer Comment:
Fuzz invariant coverage and static analysis

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: All 15 findings have individual dispositions. Branch coverage and viaIR instrumentation limits remain explicit; testing is not exhaustive and Mythril was not run.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: results/reviewer_revision/raw/security/
Summary CSV: results/reviewer_revision/validation/slither_triage.csv
Analysis script: `experiments/reviewer_revision/`
Validation status: PASS

## R1-10

Reviewer Comment:
Collusion key validator and quorum assumptions

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: Crash faults were executed; Byzantine validator and aggregator/witness collusion remain outside tested guarantees.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: results/reviewer_revision/raw/validator_faults/
Summary CSV: results/reviewer_revision/validation/validator_fault_status.json
Analysis script: `experiments/reviewer_revision/`
Validation status: PASS

## R1-M1

Reviewer Comment:
Abstract qualifiers

Response:
We agree that this point requires explicit evidence and scope control. The repository work addresses part of the request, but the item is not complete. Remaining limitation: Final abstract text and page/line placement require the revision manuscript.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: Not available
Summary CSV: results/reviewer_revision/validation/claim_registry.yaml
Analysis script: `experiments/reviewer_revision/`
Validation status: PARTIAL

## R1-M2

Reviewer Comment:
Comparison table placement

Response:
We agree that this point requires explicit evidence and scope control. The repository work addresses part of the request, but the item is not complete. Remaining limitation: Comparison placement requires the revision manuscript and verified literature table.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: Not available
Summary CSV: Not available
Analysis script: `experiments/reviewer_revision/`
Validation status: PARTIAL

## R1-M3

Reviewer Comment:
Uniform Table 1 evidence terminology

Response:
We agree that this point requires explicit evidence and scope control. The repository work addresses part of the request, but the item is not complete. Remaining limitation: Reviewer-revision tables still require final manuscript integration.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: Not available
Summary CSV: results/reviewer_revision/validation/claim_registry.yaml
Analysis script: `experiments/reviewer_revision/`
Validation status: PARTIAL

## R1-M4

Reviewer Comment:
Validator configuration disclosure

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: Topology is a local four-validator configuration.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: results/reviewer_revision/raw/besu_v2_final/deployment.json
Summary CSV: results/reviewer_revision/validation/block_period_status.json
Analysis script: `experiments/reviewer_revision/`
Validation status: PASS

## R1-M5

Reviewer Comment:
Timing dispersion

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: Dispersion and bootstrap intervals are reported over fifty complete paths.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: results/reviewer_revision/csv/besu_v2_final_timing_complete.csv
Summary CSV: results/reviewer_revision/statistics/besu_v2_final_timing_summary.csv
Analysis script: `experiments/reviewer_revision/`
Validation status: PASS

## R1-M6

Reviewer Comment:
Fleet-seed dispersion

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: No unsupported monotonic fleet-size trend is inferred.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: results/reviewer_revision/raw/fleet/
Summary CSV: results/reviewer_revision/statistics/fleet_multiseed_summary.csv
Analysis script: `experiments/reviewer_revision/`
Validation status: PASS

## R1-M7

Reviewer Comment:
Expand or narrow adversarial validation

Response:
We agree that this point requires explicit evidence and scope control. The repository work addresses part of the request, but the item is not complete. Remaining limitation: Five race families were executed through parallel RPC; additional listed endorsement-order permutations remain property-test evidence or not run.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: results/reviewer_revision/raw/concurrency/
Summary CSV: results/reviewer_revision/validation/concurrency_status.json
Analysis script: `experiments/reviewer_revision/`
Validation status: PARTIAL

## R1-M8

Reviewer Comment:
Early limitations disclosure

Response:
We agree that this point requires explicit evidence and scope control. The repository work addresses part of the request, but the item is not complete. Remaining limitation: Final limitations placement requires the revision manuscript.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: Not available
Summary CSV: results/reviewer_revision/validation/claim_registry.yaml
Analysis script: `experiments/reviewer_revision/`
Validation status: PARTIAL

## R1-M9

Reviewer Comment:
Bounded conclusion wording

Response:
We agree that this point requires explicit evidence and scope control. The repository work addresses part of the request, but the item is not complete. Remaining limitation: Final conclusion text requires the revision manuscript.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: Not available
Summary CSV: results/reviewer_revision/validation/claim_registry.yaml
Analysis script: `experiments/reviewer_revision/`
Validation status: PARTIAL

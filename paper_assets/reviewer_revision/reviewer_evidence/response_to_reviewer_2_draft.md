# Response to Reviewer 2 Draft

Page and line references are `TBD` until the revision manuscript is supplied.

## R2-1

Reviewer Comment:
DLT necessity versus alternatives

Response:
We agree that this point requires explicit evidence and scope control. The repository work addresses part of the request, but the item is not complete. Remaining limitation: TUF, Uptane, and transparency-log comparison requires manual primary-source verification.

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

## R2-2

Reviewer Comment:
Aggregator trust and omission mitigation

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: Independent reconstruction detects unilateral omission or alteration, not common upstream omission or aggregator/witness collusion. Operator and aggregator share one software account; witness has a separate account/process.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: results/reviewer_revision/raw/independent_witness/
Summary CSV: results/reviewer_revision/csv/independent_witness_tests.csv
Analysis script: `experiments/reviewer_revision/`
Validation status: PASS

## R2-3

Reviewer Comment:
Consistent evidence qualification

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: Controlled evidence vocabulary is enforced for the reviewer package.

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

## R2-4

Reviewer Comment:
Block-period and gas reporting

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: Results are final-ABI local submission-to-receipt and gas observations.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: results/reviewer_revision/raw/besu_v2_final/
Summary CSV: results/reviewer_revision/statistics/gas_summary_final.csv
Analysis script: `experiments/reviewer_revision/`
Validation status: PASS

## R2-5

Reviewer Comment:
Representative centralized baseline

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: Consensus-specific properties are intentionally absent from SQLite.

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

## R2-6

Reviewer Comment:
Statistical and reproducibility configuration

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: The one-command full path requires Docker, native Besu, Foundry, and local runtime.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: Not available
Summary CSV: results/reviewer_revision/validation/statistical_protocol.json
Analysis script: `experiments/reviewer_revision/`
Validation status: PASS

## R2-7

Reviewer Comment:
Property and invariant governance validation

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: Claims are bounded to tested properties and race families.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: results/reviewer_revision/raw/concurrency/
Summary CSV: results/reviewer_revision/validation/concurrency_status.json
Analysis script: `experiments/reviewer_revision/`
Validation status: PASS

## R2-8

Reviewer Comment:
Figure and table consistency

Response:
We agree that this point requires explicit evidence and scope control. The repository work addresses part of the request, but the item is not complete. Remaining limitation: Final manuscript figure/table numbering and placement remain pending.

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

## R2-9

Reviewer Comment:
Canonical receipt-size definition

Response:
We agree that this point requires explicit evidence and scope control. The requested implementation and validation evidence has been added. Remaining limitation: Sizes use canonical compact JSON and include the 65-byte signature.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: results/reviewer_revision/raw/fleet/
Summary CSV: results/reviewer_revision/statistics/receipt_size.csv
Analysis script: `experiments/reviewer_revision/`
Validation status: PASS

## R2-10

Reviewer Comment:
Author Contributions checklist

Response:
We agree that this point requires explicit evidence and scope control. The repository work addresses part of the request, but the item is not complete. Remaining limitation: Author contribution data was not provided.

Changes in the Manuscript:
Section: TBD
Page: TBD
Lines: TBD
Table/Figure: See manuscript change map.

Supporting Evidence:
Raw evidence: Not available
Summary CSV: Not available
Analysis script: `experiments/reviewer_revision/`
Validation status: BLOCKED

# Evidence Release Directory

Run `python experiments/reviewer_revision/generate_evidence_package.py` after validation to create:

- `LedgerGuard_Reviewer_Revision_Evidence.zip`
- `evidence_manifest.json`
- `SHA256SUMS`

These generated files are excluded from Git. Publish the ZIP and checksums as release assets when an immutable repository revision is available.

For `v2.0.0-poc`, also attach:

- `LedgerGuard_Comprehensive_Results.xlsx`
- a ZIP containing the final PDF/SVG/PNG Results figures and plot data
- the release evidence ZIP
- `SHA256SUMS`
- `evidence_manifest.json`

Do not attach the pre-freeze evidence archive or obsolete figure archive.

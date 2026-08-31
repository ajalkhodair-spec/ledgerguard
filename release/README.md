# Evidence Release Directory

Run `python experiments/reviewer_revision/generate_evidence_package.py` after validation to create:

- `LedgerGuard_Reviewer_Revision_Evidence.zip`
- `evidence_manifest.json`
- `SHA256SUMS`

These generated files are excluded from Git. Publish the ZIP and checksums as release assets when an immutable repository revision is available.

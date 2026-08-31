# Public Evidence Sample

This compact sample is derived from the preserved reviewer-revision evidence. It includes one successful local Besu control-plane run, one HTTP/SQLite comparison run, one authenticated software-fleet run with signed receipts, all completeness cases, the selective-omission case, gas examples, and the consolidated validation report.

The full raw evidence archive is generated locally with `python experiments/reviewer_revision/generate_evidence_package.py` and is intentionally excluded from Git because it contains large execution artifacts. No physical-device or production-deployment evidence is claimed.

This sample retains generation-time provenance. Its generation can precede the final revision commit; the full release manifest additionally binds the archived sample bytes to that later checkpoint.

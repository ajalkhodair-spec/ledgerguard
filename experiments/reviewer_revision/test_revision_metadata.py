"""Versioned metadata must work on a clean output tree and preserve local edits."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.reviewer_revision import update_revision_metadata as metadata


class RevisionMetadataTest(unittest.TestCase):
    def test_initializes_missing_analysis_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "validation"
            with patch.object(metadata, "VALIDATION", target):
                metadata.initialize_metadata()
            for name in (
                "claim_registry.yaml", "statistical_protocol.json",
                "baseline_equivalence_matrix.csv", "reviewer_1_acceptance_matrix.csv",
                "reviewer_2_acceptance_matrix.csv",
            ):
                self.assertTrue((target / name).is_file(), name)

    def test_preserves_existing_local_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            local = target / "claim_registry.yaml"
            local.write_text("local_revision: true\n", encoding="utf-8")
            with patch.object(metadata, "VALIDATION", target):
                metadata.initialize_metadata()
            self.assertEqual(local.read_text(encoding="utf-8"), "local_revision: true\n")


if __name__ == "__main__":
    unittest.main()

"""Regression checks for the corrected figure and gas-summary definitions."""

import unittest

from experiments.reviewer_revision.collect_gas import summary_row
from experiments.reviewer_revision.summarize_final_distributions import describe, outcome_shares
from experiments.reviewer_revision.build_revision_closures import minimum_profitable_batch, strip_private_fields


class EvidenceSummaryTest(unittest.TestCase):
    def test_v2_gas_break_even_requires_three_devices(self):
        self.assertEqual(minimum_profitable_batch(169245, 434143), 3)

    def test_break_even_equality_is_not_strictly_lower(self):
        self.assertEqual(minimum_profitable_batch(100, 200), 3)

    def test_break_even_rejects_nonpositive_gas(self):
        with self.assertRaises(ValueError):
            minimum_profitable_batch(0, 200)

    def test_genesis_snapshot_strips_nested_private_fields(self):
        original = {"alloc": {"address": {"privateKey": "fixture-secret", "balance": "100"}},
                    "nested": [{"secret_key": "fixture-secret", "chainId": 1337}]}
        public = strip_private_fields(original)
        self.assertEqual(public, {"alloc": {"address": {"balance": "100"}}, "nested": [{"chainId": 1337}]})
        self.assertIn("privateKey", original["alloc"]["address"])

    def test_rollback_is_not_combined_nonadoption(self):
        shares = outcome_shares({"expected_count": 100, "success_count": 90,
                                 "rollback_count": 3, "fail_count": 7,
                                 "rejected_count": 0, "missing_count": 0})
        self.assertEqual(shares["ROLLBACK"], 3)
        self.assertEqual(shares["FAIL"], 7)
        self.assertNotEqual(shares["ROLLBACK"], 100 - shares["SUCCESS"])

    def test_outcome_counts_must_reconcile(self):
        with self.assertRaises(ValueError):
            outcome_shares({"expected_count": 100, "success_count": 90,
                            "rollback_count": 3, "fail_count": 6,
                            "rejected_count": 0, "missing_count": 0})

    def test_distribution_retains_extreme_observation(self):
        result = describe([17.0] * 19 + [915.736736])
        self.assertEqual(result["n"], 20)
        self.assertEqual(result["maximum"], 915.736736)
        self.assertEqual(result["median"], 17.0)
        self.assertGreater(result["mean"], result["median"])

    def test_gas_summary_reports_sample_dispersion_and_auxiliary_metrics(self):
        result = summary_row("operation", "test", [
            {"gas": 10, "calldata": 4, "events": 1},
            {"gas": 30, "calldata": 8, "events": 3},
        ], "fixture")
        self.assertEqual(result["median_gas"], "20.000")
        self.assertEqual(result["q1_gas"], "15.000")
        self.assertEqual(result["q3_gas"], "25.000")
        self.assertEqual(result["sample_standard_deviation_gas"], "14.142")
        self.assertEqual(result["median_calldata_bytes"], "6.000")
        self.assertEqual(result["median_event_count"], "2.000")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Unit tests for core/user_corrections_engine.py."""

import json
import tempfile
import unittest
from pathlib import Path

from core.user_corrections_engine import UserCorrectionsEngine


class TestUserCorrectionsEngine(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.log_path = Path(self.td.name) / "test_corrections.json"
        self.engine = UserCorrectionsEngine(log_path=self.log_path)

    def tearDown(self):
        self.td.cleanup()

    def test_log_correction_records_entry(self):
        entry = self.engine.log_user_correction(
            category="phone_digits_only",
            user_directive="Enter digits only. Do not include country code.",
            prompt_or_context="Phone input validation",
            severity="critical",
        )
        self.assertEqual(entry["category"], "phone_digits_only")
        self.assertEqual(entry["recurrence_count"], 1)
        self.assertTrue(entry["promoted_to_frontier"])  # Critical triggers immediate promotion

        summary = self.engine.get_corrections_summary()
        self.assertEqual(summary["total_corrections"], 1)
        self.assertIn("phone_digits_only", summary["promoted_categories"])
        self.assertTrue(self.engine.is_category_promoted("phone_digits_only"))

    def test_recurrence_increments_and_promotes(self):
        self.engine.log_user_correction(
            category="custom_field",
            user_directive="Use format X",
            severity="medium",
        )
        # 1 medium is not promoted
        self.assertFalse(self.engine.is_category_promoted("custom_field"))

        # 2nd medium
        self.engine.log_user_correction(
            category="custom_field",
            user_directive="Use format X always",
            severity="medium",
        )
        self.assertFalse(self.engine.is_category_promoted("custom_field"))

        # 3rd recurrence reaches total_corrections threshold (>= 3)
        self.engine.log_user_correction(
            category="custom_field",
            user_directive="Why didn't you use format X?!",
            severity="medium",
        )
        self.assertTrue(self.engine.is_category_promoted("custom_field"))


if __name__ == "__main__":
    unittest.main()

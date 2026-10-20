#!/usr/bin/env python3
"""Unit tests for ATS discovery pollers and filtering rules."""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from discovery.ats_discovery.filters import matches_role, matches_location, evaluate_posting
from discovery.ats_discovery.boards import POLLERS, extract_salary


class TestATSBoards(unittest.TestCase):
    def test_poller_registry(self):
        expected = {"greenhouse", "lever", "ashby", "smartrecruiters", "workable"}
        self.assertTrue(expected.issubset(set(POLLERS.keys())), f"Missing expected pollers: {POLLERS.keys()}")

    def test_salary_extraction(self):
        # LPA test
        lo, hi = extract_salary("Salary range is 20 - 28 LPA based on experience.")
        self.assertEqual(lo, 2000000)
        self.assertEqual(hi, 2800000)

        # Single LPA test
        lo, hi = extract_salary("Compensation: 24 LPA")
        self.assertEqual(lo, 2400000)
        self.assertEqual(hi, 2400000)

        # USD test
        lo, hi = extract_salary("Base compensation is $140,000 - $180,000 USD per year.")
        self.assertEqual(lo, 140000)
        self.assertEqual(hi, 180000)

    def test_role_filtering(self):
        self.assertTrue(matches_role("Senior Data Engineer"))
        self.assertTrue(matches_role("AI Systems & Automation Engineer"))
        self.assertTrue(matches_role("Analytics Engineer II"))
        self.assertFalse(matches_role("Frontend React Developer"))
        self.assertFalse(matches_role("Technical Recruiter"))
        self.assertFalse(matches_role("HR Operations Specialist"))

    def test_location_filtering(self):
        ok, tier = matches_location("Bengaluru, India")
        self.assertTrue(ok)
        self.assertEqual(tier, "Bangalore")

        ok, tier = matches_location("Gurugram / Noida", "Hybrid")
        self.assertTrue(ok)
        self.assertEqual(tier, "Delhi NCR (Preferred)")

        ok, tier = matches_location("Remote", "Remote")
        self.assertTrue(ok)
        self.assertEqual(tier, "100% Remote")

        ok, tier = matches_location("London, UK", "Onsite")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""
Tests for hierarchical address resolution (1-line, 2-line, 3-line)
and standard geographical components (city, state, country, pincode).
Uses standard library unittest.TestCase for full compatibility with GitHub CI unittest runner and pytest.
"""
import unittest
from automation.browser import resolve_address_components, DEFAULT_CANDIDATE


class TestAddressHierarchy(unittest.TestCase):
    def test_resolve_address_components_single_line(self):
        """Verify single line returns full address for line 1 and empty for lines 2 & 3."""
        cand = {
            "address": "123 Main St, Apt 4, City, State, Country",
            "address_2_line1": "123 Main St",
            "address_2_line2": "Apt 4",
            "address_3_line1": "123 Main",
            "address_3_line2": "St",
            "address_3_line3": "Apt 4",
        }
        l1, l2, l3 = resolve_address_components(has_line2=False, has_line3=False, cand=cand)
        self.assertEqual(l1, "123 Main St, Apt 4, City, State, Country")
        self.assertEqual(l2, "")
        self.assertEqual(l3, "")

    def test_resolve_address_components_two_lines_from_env(self):
        """Verify 2-line resolution respects explicit address_2_line1 and line2."""
        cand = {
            "address": "Full Address",
            "address_2_line1": "Line 1 Content",
            "address_2_line2": "Line 2 Content",
        }
        l1, l2, l3 = resolve_address_components(has_line2=True, has_line3=False, cand=cand)
        self.assertEqual(l1, "Line 1 Content")
        self.assertEqual(l2, "Line 2 Content")
        self.assertEqual(l3, "")

    def test_resolve_address_components_two_lines_fallback_split(self):
        """Verify 2-line fallback splitting when line1/line2 keys are not explicitly set."""
        cand = {
            "address": "Part A, Part B, Part C, Part D, Part E",
        }
        l1, l2, l3 = resolve_address_components(has_line2=True, has_line3=False, cand=cand)
        self.assertEqual(l1, "Part A, Part B, Part C")
        self.assertEqual(l2, "Part D, Part E")
        self.assertEqual(l3, "")

    def test_resolve_address_components_three_lines_from_env(self):
        """Verify 3-line resolution respects explicit address_3_line1, line2, line3."""
        cand = {
            "address": "Full Address",
            "address_3_line1": "L1",
            "address_3_line2": "L2",
            "address_3_line3": "L3",
        }
        l1, l2, l3 = resolve_address_components(has_line2=True, has_line3=True, cand=cand)
        self.assertEqual(l1, "L1")
        self.assertEqual(l2, "L2")
        self.assertEqual(l3, "L3")

    def test_resolve_address_components_three_lines_fallback_split(self):
        """Verify 3-line fallback splitting when line1/line2/line3 are not explicitly set."""
        cand = {
            "address": "Part 1, Part 2, Part 3, Part 4, Part 5",
        }
        l1, l2, l3 = resolve_address_components(has_line2=True, has_line3=True, cand=cand)
        self.assertEqual(l1, "Part 1, Part 2")
        self.assertEqual(l2, "Part 3")
        self.assertEqual(l3, "Part 4")

    def test_default_candidate_contains_address_keys(self):
        """Verify DEFAULT_CANDIDATE has all address hierarchy keys."""
        expected_keys = [
            "address",
            "address_2_line1",
            "address_2_line2",
            "address_3_line1",
            "address_3_line2",
            "address_3_line3",
            "city",
            "state",
            "country",
            "pincode",
        ]
        for k in expected_keys:
            self.assertIn(k, DEFAULT_CANDIDATE, f"Missing key {k} in DEFAULT_CANDIDATE")


if __name__ == "__main__":
    unittest.main()
